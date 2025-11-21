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

        # Tu JSON tiene la cédula como clave principal: {"070...": {...}}
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
        # DEBUG: Ver qué datos llegan
        print("\n" + "="*60)
        print("📨 DATOS RECIBIDOS EN VISTA:")
        print(f"Keys en request.data: {list(request.data.keys())}")
        
        user_message = request.data.get('message', '')
        session_data = request.data.get('session_data', {}) # El frontend debe enviar esto
        
        if 'session_data' in request.data:
            print(f"✅ Session Data recibido: {type(session_data)}")
            if isinstance(session_data, dict):
                print(f"   Keys en session_data: {list(session_data.keys())}")
                for cedula, datos in session_data.items():
                    print(f"   Cédula: {cedula}")
                    if isinstance(datos, dict):
                        perfiles = datos.get('perfiles', [])
                        print(f"   Perfiles encontrados: {len(perfiles)}")
                        for p in perfiles:
                            if isinstance(p, dict):
                                flags = [k for k, v in p.items() if isinstance(v, bool) and v is True]
                                print(f"      - Perfil ID {p.get('id')}: {flags}")
            else:
                print(f"   ⚠️ session_data no es dict: {session_data}")
        else:
            print("⚠️ ALERTA: No llegó 'session_data' en request.data")
        
        print("="*60 + "\n")

        if not user_message:
            return Response({"error": "Mensaje vacío"}, status=400)

        # 1. Determinar qué puede ver el usuario
        categorias_permitidas, rol_usuario = self._obtener_permisos(session_data)
        print(f"🔍 Categorías permitidas: {categorias_permitidas}")
        print(f"👤 Rol detectado: {rol_usuario}\n")

        # 2. Analizar intención
        intent_data = procesar_mensaje_usuario(user_message)

        # CASO A: OPERATIVO (Agente)
        if intent_data.get("answer_type") == "operational":
            return Response({
                "type": "agent_handoff",
                "text": intent_data["system_response"],
                "intent_debug": intent_data
            })

        # CASO B: INFORMATIVO (RAG con Filtro de Roles)
        if intent_data.get("answer_type") == "informational":
            rag_response = rag_service.consultar(
                query=user_message,
                categorias_permitidas=categorias_permitidas, # <--- CLAVE
                user_role_name=rol_usuario
            )
            
            return Response({
                "type": "rag_response",
                "text": rag_response["response"],
                "sources": rag_response["sources"],
                "need_contact": rag_response.get("need_contact", False),
                "intent_debug": intent_data,
                # Info útil para ti como desarrollador:
                "debug_context": {
                    "rol_detectado": rol_usuario,
                    "carpetas_acceso": categorias_permitidas
                }
            })

        # CASO C: DEFAULT
        return Response({"type": "simple", "text": intent_data["system_response"]})


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
