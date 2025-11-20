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
    """
    
    def post(self, request):
        user_message = request.data.get('message', '')
        if not user_message:
            return Response({"error": "Vacío"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Procesar Intención
        intent_data = procesar_mensaje_usuario(user_message)
        
        # 2. CASO AGENTE (Operativo)
        # Si el parser dice que es operativo, ya trae el mensaje listo en 'system_response'
        if intent_data.get("answer_type") == "operativo":
            return Response({
                "type": "agent_handoff",
                "text": intent_data.get("system_response", "Un agente se pondrá en contacto contigo."),
                "intent_debug": intent_data
            }, status=status.HTTP_200_OK)

        # 3. CASO RAG (Informativo)
        if intent_data.get("answer_type") == "informativo" and intent_data.get("intent_code") != "saludo":
            rag_response = rag_service.consultar(user_message)
            return Response({
                "type": "rag_response",
                "text": rag_response["response"],
                "sources": rag_response.get("sources", []),
                "intent_debug": intent_data
            }, status=status.HTTP_200_OK)
            
        # 4. CASO SALUDO / OTROS
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
