import json
import requests
import logging
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .intent_parser import procesar_mensaje_usuario
from .rag_service import rag_service

logger = logging.getLogger(__name__)


class ChatView(APIView):
    # Mapeo exacto de tu base de datos a las carpetas del disco
    MAPA_ROLES = {
        "es_estudiante": "estudiantes",
        "es_profesor": "docentes",
        "es_administrativo": "administrativos",
        "es_externo": "externos",
        "es_inscripcionaspirante": "aspirantes",
        "es_inscripcionpostulante": "postulantes",
        "es_postulante": "postulantes",
        "es_postulanteempleo": "empleo",
        "es_inscripcionadmision": "admision"
    }

    def _obtener_permisos(self, session_data):
        """
        Analiza el JSON de sesión y devuelve las carpetas permitidas.
        """
        categorias = ["general"] # Siempre accesible
        roles_texto = []

        if not session_data or not isinstance(session_data, dict):
            return categorias, "Visitante"

        # Tu JSON tiene la cédula como clave principal: {"070...": {}}
        # Iteramos sobre todas las personas en la sesión (usualmente una)
        for cedula, datos in session_data.items():
            perfiles = datos.get("perfiles", [])
            
            for perfil in perfiles:
                # Verificamos que el perfil esté activo
                if perfil.get("status") is True:
                    
                    # Revisamos cada bandera del mapa
                    for flag_db, carpeta in self.MAPA_ROLES.items():
                        if perfil.get(flag_db) is True:
                            categorias.append(carpeta)
                            # Guardar nombre para debug (ej: "Estudiante")
                            nombre = flag_db.replace("es_", "").replace("inscripcion", "").capitalize()
                            roles_texto.append(nombre)

        return list(set(categorias)), ", ".join(set(roles_texto)) or "Visitante"
    
    def post(self, request):
        # Envolvemos toda la lógica en un generador
        def event_stream():
            try:
                # 1. Fase Inicial
                yield json.dumps({"type": "status", "text": "Entendiendo tu intención"}) + "\n"
                
                user_message = request.data.get('message', '')
                session_data = request.data.get('session_data', {})
                
                #  (Tu lógica de obtención de permisos) 
                categorias_permitidas, rol_usuario = self._obtener_permisos(session_data)

                # 2. Intent Parsing
                intent_data = procesar_mensaje_usuario(user_message)
                
                # CASO 0: AMBIGÜEDAD DETECTADA (Pedimos aclaración)
                if intent_data.get("is_ambiguous"):
                    yield json.dumps({
                        "type": "final",
                        "data": {
                            "type": "clarification",
                            "text": intent_data["system_response"],
                            "intent_debug": intent_data
                        }
                    }) + "\n"
                    return  # Cortamos aquí. No gastamos RAG.
                
                # CASO 1: OPERATIVO (Agent Handoff)
                if intent_data.get("answer_type") == "operational":
                    yield json.dumps({
                        "type": "final",
                        "data": {
                            "type": "agent_handoff",
                            "text": intent_data["system_response"],
                            "intent_debug": intent_data
                        }
                    }) + "\n"
                    return

                # CASO 2: INFORMATIVO (RAG)
                if intent_data.get("answer_type") == "informational":
                    yield json.dumps({"type": "status", "text": "Buscando documentos"}) + "\n"

                    rag_response = rag_service.consultar(
                        query=user_message,
                        intent_data=intent_data,
                        categorias_permitidas=categorias_permitidas,
                        user_role_name=rol_usuario
                    )
                    
                    yield json.dumps({"type": "status", "text": "Generando respuesta"}) + "\n"

                    yield json.dumps({
                        "type": "final",
                        "data": {
                            "type": "rag_response",
                            "text": rag_response["response"],
                            "sources": rag_response["sources"],
                            "need_contact": rag_response.get("need_contact", False),
                            "intent_debug": intent_data,
                            "debug_context": {
                                "rol_detectado": rol_usuario,
                                "carpetas_acceso": categorias_permitidas
                            }
                        }
                    }) + "\n"
                else:
                    # Respuesta default
                    yield json.dumps({
                        "type": "final",
                        "data": {"type": "simple", "text": intent_data["system_response"]}
                    }) + "\n"

            except Exception as e:
                yield json.dumps({"type": "error", "text": str(e)}) + "\n"

        # Retornamos el Streaming
        response = StreamingHttpResponse(event_stream(), content_type="application/x-ndjson")
        response['X-Accel-Buffering'] = 'no'  # Vital para Nginx/Producción
        return response


@require_http_methods(["GET"])
def health(request):
    """
    Endpoint para verificar el estado de Ollama y el servicio
    """
    try:
        ollama_url = f'{settings.OLLAMA_BASE_URL}/api/tags'
        response = requests.get(ollama_url, timeout=5)
        
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_available = any(settings.OLLAMA_MODEL in model.get('name', '') for model in models)
            
            return JsonResponse({
                'status': 'ok',
                'service': 'balcon_chatbot',
                'ollama_connected': True,
                'model_available': model_available,
                'model_configured': settings.OLLAMA_MODEL,
                'models': [model.get('name') for model in models]
            })
        else:
            return JsonResponse({
                'status': 'error',
                'ollama_connected': False,
                'error': f'Ollama respondió con código {response.status_code}'
            }, status=500)
            
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'status': 'error',
            'ollama_connected': False,
            'error': 'No se pudo conectar con Ollama'
        }, status=503)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'ollama_connected': False,
            'error': str(e)
        }, status=500)


class DocumentUploadView(APIView):
    """
    Endpoint para carga de documentos multi-formato con batch processing y soporte de roles.
    
    Soporta: PDF, DOCX, TXT, MD
    Lógica: Batch processing en memoria (auto_save=False) y commit único al final.
    """
    
    def get(self, request):
        """
        Lista los documentos organizados por categoría (rol).
        Response: { "general": [{"name": "doc.pdf", "size_mb": 2.5}], ... }
        """
        try:
            base_dir = Path(settings.BASE_DIR) / "documentos_unemi"
            
            if not base_dir.exists():
                return Response({'categories': {}}, status=status.HTTP_200_OK)
            
            categories = {}
            supported_extensions = {'.pdf', '.docx', '.txt', '.md'}
            
            for category_dir in base_dir.iterdir():
                if category_dir.is_dir():
                    files = []
                    for file_path in category_dir.iterdir():
                        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                            file_size_mb = file_path.stat().st_size / (1024 * 1024)
                            files.append({
                                'name': file_path.name,
                                'size_mb': round(file_size_mb, 2),
                                'type': file_path.suffix.lower().lstrip('.')
                            })
                    
                    if files:
                        categories[category_dir.name] = sorted(files, key=lambda x: x['name'])
            
            total_files = sum(len(f) for f in categories.values())
            return Response({
                'categories': categories,
                'stats': {
                    'total_categories': len(categories),
                    'total_files': total_files
                }
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error listando documentos: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """
        Procesa archivos subidos. 
        Parámetros: 
          - files: Lista de archivos
          - categoria: (Opcional) Rol asociado (default: 'general')
        """
        try:
            files = request.FILES.getlist('files')
            if not files:
                return Response({'error': 'No se proporcionaron archivos'}, status=status.HTTP_400_BAD_REQUEST)
            
            categoria = request.POST.get('categoria', 'general')
            
            # Configuración
            max_size_mb = getattr(settings, 'RAG_MAX_FILE_SIZE_MB', 50)
            base_dir = Path(settings.BASE_DIR) / "documentos_unemi"
            category_dir = base_dir / categoria
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # Métricas
            processed_files = []
            errors = []
            total_chunks = 0
            file_details = []
            
            # --- FASE 1: Procesamiento en Lote (Memoria) ---
            for file in files:
                try:
                    # 1. Validación de Tamaño
                    file_size_mb = file.size / (1024 * 1024)
                    if file_size_mb > max_size_mb:
                        errors.append({'file': file.name, 'error': f'Excede {max_size_mb}MB'})
                        continue
                    
                    # 2. Guardado en Disco (Permanente)
                    final_path = category_dir / file.name
                    with open(final_path, 'wb+') as destination:
                        for chunk in file.chunks():
                            destination.write(chunk)
                    
                    # 3. Ingesta (Sin guardar índice todavía)
                    # auto_save=False es la clave de la velocidad
                    success, msg = rag_service.ingerir_documento(
                        str(final_path),
                        categoria=categoria,
                        auto_save=False 
                    )
                    
                    if success:
                        # Extraer métricas del mensaje (ej: "Ingestado: 25 fragmentos")
                        import re
                        match = re.search(r'(\d+)\s+fragmentos', msg)
                        chunks_count = int(match.group(1)) if match else 0
                        
                        total_chunks += chunks_count
                        processed_files.append(file.name)
                        
                        file_details.append({
                            'filename': file.name,
                            'chunks': chunks_count,
                            'size_mb': round(file_size_mb, 2),
                            'type': Path(file.name).suffix
                        })
                    else:
                        errors.append({'file': file.name, 'error': msg})
                        # Opcional: Borrar archivo si falló la ingesta
                        # final_path.unlink(missing_ok=True) 
                
                except Exception as e:
                    errors.append({'file': file.name, 'error': str(e)})
            
            # --- FASE 2: Guardado del Índice (Commit Único) ---
            if processed_files:
                if not rag_service.guardar_indice():
                    logger.warning("⚠️ Advertencia: No se pudo persistir el índice en disco.")
            
            # Respuesta
            response_data = {
                'message': f'Procesados {len(processed_files)} de {len(files)} archivos.',
                'files_processed': processed_files,
                'total_chunks_added': total_chunks,
                'details': file_details
            }
            
            if errors:
                response_data['errors'] = errors
                status_code = status.HTTP_207_MULTI_STATUS if processed_files else status.HTTP_400_BAD_REQUEST
            else:
                status_code = status.HTTP_200_OK
                
            return Response(response_data, status=status_code)
        
        except Exception as e:
            logger.error(f"Error crítico en upload: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)