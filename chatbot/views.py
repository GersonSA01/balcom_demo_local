import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .intent_parser import procesar_mensaje_usuario
from .rag_service import rag_service


class ChatView(APIView):
    """
    Endpoint principal para el chatbot.
    Procesa mensajes del usuario y enruta a RAG o agente según el tipo de intención.
    Soporta múltiples roles con mapeo granular de permisos.
    """
    
    # Diccionario de Mapeo: { "campo_booleano_db": "nombre_carpeta_faiss" }
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
    
    def _determinar_categorias_permitidas(self, session_data):
        """
        Extrae los roles activos del session_data y mapea a carpetas FAISS.
        
        Returns:
            tuple: (categorias_permitidas, nombre_roles_str)
        """
        categorias_permitidas = ["general"]  # Base para todos
        roles_detectados = []
        
        if not isinstance(session_data, dict):
            return categorias_permitidas, "Visitante"
        
        # Iterar sobre todos los usuarios en la sesión
        for cedula, datos in session_data.items():
            if not isinstance(datos, dict):
                continue
                
            perfiles = datos.get("perfiles", [])
            
            # Revisar cada perfil activo
            for perfil in perfiles:
                if not isinstance(perfil, dict):
                    continue
                    
                # Solo nos importan los perfiles activos
                if perfil.get("status") is not True:
                    continue
                
                # Revisar cada bandera booleana contra el mapa de roles
                for flag_db, carpeta_faiss in self.MAPA_ROLES.items():
                    if perfil.get(flag_db) is True:
                        # Agregar categoría si no está ya
                        if carpeta_faiss not in categorias_permitidas:
                            categorias_permitidas.append(carpeta_faiss)
                        
                        # Nombre bonito para logs (remover prefijo "es_" y capitalizar)
                        nombre_rol = flag_db.replace("es_", "").replace("inscripcion", "").replace("postulante", "")
                        nombre_rol = nombre_rol.replace("_", " ").strip()
                        if nombre_rol:
                            roles_detectados.append(nombre_rol.title())
        
        # Limpiar duplicados y formatear
        categorias_permitidas = list(set(categorias_permitidas))
        nombre_roles_str = ", ".join(sorted(set(roles_detectados))) or "Visitante"
        
        return categorias_permitidas, nombre_roles_str
    
    def post(self, request):
        user_message = request.data.get('message', '')
        if not user_message:
            return Response({"error": "Mensaje vacío"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. OBTENER LA SESIÓN COMPLETA Y DETERMINAR PERMISOS
        session_data = request.data.get('session_data', {})
        categorias_permitidas, nombre_roles_str = self._determinar_categorias_permitidas(session_data)

        # 2. PROCESAR INTENCIÓN (QWEN 3B)
        intent_data = procesar_mensaje_usuario(user_message)
        
        # CASO A: OPERATIVO (Handoff a Agente)
        if intent_data.get("answer_type") == "operational":
            return Response({
                "type": "agent_handoff",
                "text": intent_data.get("system_response", "Un agente se pondrá en contacto contigo."),
                "intent_debug": intent_data
            }, status=status.HTTP_200_OK)

        # CASO B: INFORMATIVO (RAG con Filtros de Roles)
        if intent_data.get("answer_type") == "informational" and intent_data.get("intent_code") != "saludo":
            
            rag_response = rag_service.consultar(
                query=user_message,
                categorias_permitidas=categorias_permitidas,  # <--- AQUÍ SE APLICA EL FILTRO GRANULAR
                user_role_name=nombre_roles_str
            )
            
            return Response({
                "type": "rag_response",
                "text": rag_response["response"],
                "sources": rag_response.get("sources", []),
                "need_contact": rag_response.get("need_contact", False),
                "has_information": rag_response.get("has_information", False),
                "intent_debug": intent_data,
                "debug_info": {
                    "roles_detectados": nombre_roles_str,
                    "carpetas_consultadas": categorias_permitidas
                }
            }, status=status.HTTP_200_OK)
            
        # CASO C: SALUDO / OTROS
        return Response({
            "type": "simple_text",
            "text": intent_data.get("system_response", "No entendí tu consulta."),
            "intent_debug": intent_data
        }, status=status.HTTP_200_OK)


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
