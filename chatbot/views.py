import json
import re
import requests
import logging
import os
import time
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# --- CARGAR "BASE DE DATOS" JSON ---
def load_db():
    """Carga la base de datos JSON de usuarios en memoria al iniciar."""
    json_path = os.path.join(settings.BASE_DIR, 'chatbot', 'data', 'data_unemi.json')
    try:
        if not os.path.exists(json_path):
            logger.warning(f"⚠️ Archivo de datos no encontrado en: {json_path}")
            return {}
            
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"❌ Error: El archivo {json_path} tiene un formato JSON inválido.")
        return {}
    except Exception as e:
        logger.error(f"❌ Error crítico cargando DB: {e}")
        return {}

# Cargamos la DB en memoria una sola vez
UNEMI_DB = load_db()

class ChatView(APIView):
    def post(self, request):
        # Validación básica de entrada
        if not request.data:
            return JsonResponse({"type": "error", "text": "Solicitud vacía"}, status=400)

        user_message = request.data.get('message', '')
        history = request.data.get('history', [])
        session_data = request.data.get('session_data', {})
        
        # Recuperación segura de la cédula
        current_cedula = list(session_data.keys())[0] if session_data and isinstance(session_data, dict) else None

        # ---------------------------------------------------------
        # 🕵️ LOGICA DE ROLES ESTRICTA (Solo Perfil Seleccionado)
        # ---------------------------------------------------------
        roles_permitidos = ["general"] # El rol 'general' siempre va incluido
        nombre_usuario_debug = "Anónimo"
        perfil_seleccionado_debug = "Ninguno detectado"

        # 1. Obtener el ID del perfil que el usuario seleccionó en el Frontend
        target_perfil_id = None
        if current_cedula and session_data.get(current_cedula):
            try:
                # El frontend envía un array 'perfiles' con 1 solo elemento (el seleccionado)
                perfiles_session = session_data[current_cedula].get('perfiles', [])
                if perfiles_session:
                    target_perfil_id = perfiles_session[0].get('id')
            except Exception as e:
                logger.warning(f"Error leyendo ID de perfil de sesión: {e}")

        # 2. Buscar ese ID en la base de datos real para sacar los flags
        if current_cedula and current_cedula in UNEMI_DB:
            user_data = UNEMI_DB[current_cedula]
            nombre_usuario_debug = user_data.get('persona', {}).get('nombres', 'Usuario')
            
            lista_perfiles_db = user_data.get('perfiles', [])
            perfil_activo = None

            # Buscamos el perfil exacto por ID
            if target_perfil_id:
                for p in lista_perfiles_db:
                    # Comparamos como string para evitar errores de tipo (int vs str)
                    if str(p.get('id')) == str(target_perfil_id):
                        perfil_activo = p
                        break
            
            # 3. Si encontramos el perfil, extraemos SOLO sus roles
            if perfil_activo:
                perfil_seleccionado_debug = f"ID {target_perfil_id} - {perfil_activo.get('tipo', 'Unknown')}"
                
                KEYS_A_VERIFICAR = [
                    "es_estudiante", "es_profesor", "es_administrativo", "es_externo",
                    "es_inscripcionaspirante", "es_inscripcionpostulante", "es_postulante",
                    "es_postulanteempleo", "es_inscripcionadmision"
                ]
                
                for key in KEYS_A_VERIFICAR:
                    if perfil_activo.get(key) is True:
                        roles_permitidos.append(key)
            else:
                perfil_seleccionado_debug = f"ID {target_perfil_id} NO ENCONTRADO en DB"

        # ---------------------------------------------------------
        # 2. FILTRADO INTELIGENTE (Evita error 422)
        # Django pide la lista de docs y filtra los IDs permitidos
        # ---------------------------------------------------------
        docs_ids_filtrados = []
        total_docs_encontrados = 0
        
        try:
            ingest_url = f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/list"
            resp_ingest = requests.get(ingest_url, timeout=2)
            
            if resp_ingest.status_code == 200:
                todos_docs = resp_ingest.json().get('data', [])
                
                for doc in todos_docs:
                    meta = doc.get('doc_metadata', {})
                    doc_role = meta.get('role', 'general') # Default 'general'
                    
                    # Si el rol del documento está en los roles del usuario, lo permitimos
                    if doc_role in roles_permitidos:
                        docs_ids_filtrados.append(doc.get('doc_id'))
                
                total_docs_encontrados = len(todos_docs)
            else:
                logger.error(f"Error obteniendo lista de docs: {resp_ingest.status_code}")

        except Exception as e:
            logger.error(f"Error conectando con servicio de ingesta: {e}")

        # --- 🖨️ PRINTS PARA VER EN CONSOLA ---
        print("\n" + "="*50)
        print(f"👤 [DEBUG] Usuario: {nombre_usuario_debug} (Cédula: {current_cedula})")
        print(f"🎯 [DEBUG] Perfil Seleccionado: {perfil_seleccionado_debug}")
        print(f"🛡️ [DEBUG] Roles del Perfil: {roles_permitidos}")
        print(f"📚 [DEBUG] Documentos Totales: {total_docs_encontrados}")
        print(f"✅ [DEBUG] Documentos Autorizados (IDs): {len(docs_ids_filtrados)}")
        print("="*50 + "\n")

        # 1. DEFINICIÓN DE HERRAMIENTAS
        tools_definition = """
        HERRAMIENTAS DISPONIBLES (Prioridad ALTA para datos personales):
        - "search_data": ÚSALA SIEMPRE que el usuario pregunte por SU información personal o estado actual.
           Ejemplos: "¿En qué materias estoy?", "Quiero ver mis notas", "¿Tengo deudas?", "¿Cuál es mi horario?", "Mi asistencia", "Mis datos".
        - "change_career": Iniciar proceso de cambio de carrera.
        - "drop_subject": Retirar asignatura.
        """

        # 2. SYSTEM PROMPT MAESTRO
        INDUSTRIAL_SYSTEM_PROMPT = f"""
        Eres el Asistente Inteligente de la UNEMI.
        Tu misión es distinguir entre una CONSULTA GENERAL (Reglamento) y una CONSULTA PERSONAL (Base de Datos).

        {tools_definition}

        REGLA DE ORO "GENERAL vs PERSONAL":
        1. CONSULTA GENERAL (RAG - ANSWER):
           - Si la respuesta está explícita en los documentos (ej: calendarios académicos generales, fechas de matriculación globales, reglamentos), USA LA INFORMACIÓN DEL CONTEXTO y marca "ANSWER".
           - Ejemplo: "¿Cuándo son los exámenes?", "¿Cuándo inician clases?", "¿Qué dice el reglamento?".

        2. CONSULTA PERSONAL (DB - FUNCTION):
           - Solo si el usuario pregunta por SU caso específico, SU horario personal, SUS notas o SU estado.
           - Ejemplo: "¿Cuándo me toca A MÍ rendir examen?", "¿Cuáles son MIS materias?", "¿Estoy matriculado?".
           - Si el documento tiene fechas generales, pero el usuario pregunta "cuándo me toca a mí", ahí sí usa "search_data".

        FORMATO DE SALIDA (JSON ESTRICTO):
        Responde SIEMPRE con este objeto JSON:
        {{{{
            "response": "Texto breve confirmando la acción o respondiendo...",
            "action": "ANSWER" | "FUNCTION" | "HANDOFF",
            "function_name": "search_data" | "change_career" | "drop_subject" | null,
            "sources": []
        }}}}

        EJEMPLOS DE COMPORTAMIENTO:

        Caso 1: Pregunta Personal (El usuario quiere ver SU realidad)
        User: "¿En qué materias estoy matriculado?"
        Contexto RAG: (Puede contener 'Reglamento de Matriculación Art 5...') -> IGNORAR
        Output: {{{{
            "response": "Consultando tus asignaturas matriculadas actualmente...",
            "action": "FUNCTION",
            "function_name": "search_data",
            "sources": []
        }}}}

        Caso 2: Pregunta General (El usuario quiere saber el proceso)
        User: "¿Cuántas materias puedo coger máximo?"
        Contexto RAG: "Art 10. El máximo de créditos..."
        Output: {{{{
            "response": "Según el artículo 10, el máximo permitido es...",
            "action": "ANSWER",
            "function_name": null,
            "sources": [{{{{ "title": "Reglamento Académico", "article": "Art. 10" }}}}]
        }}}}

        Caso 3: Pregunta de Calendario General (RAG)
        User: "¿Cuándo son los exámenes finales?"
        Contexto RAG: "Calendario Académico: Exámenes del 24 al 29 de Noviembre."
        Output: {{{{
            "response": "Según el calendario académico, los exámenes finales son del 24 al 29 de noviembre.",
            "action": "ANSWER",
            "function_name": null,
            "sources": [{{{{ "title": "Calendario Académico", "article": "Fechas" }}}}]
        }}}}
        """

        def event_stream():
            if not docs_ids_filtrados:
                # Opcional: Mandar un estado primero para que el usuario vea "Verificando..."
                yield json.dumps({"type": "status", "text": "Pensando..."}) + "\n"
                
                # --- EL MINI DELAY (1.5 a 2 segundos es ideal) ---
                time.sleep(1) 
                # -------------------------------------------------

                yield json.dumps({
                    "type": "final", 
                    "data": {
                        "type": "rag_response",
                        "text": "Lo siento, no tengo información disponible para tu perfil actual en mi base de conocimientos.",
                        "sources": []
                    }
                }) + "\n"
                return

            
            try:
                yield json.dumps({"type": "status", "text": "Consultando..."}) + "\n"
                
                messages_payload = [{"role": "system", "content": INDUSTRIAL_SYSTEM_PROMPT}]
                
                if isinstance(history, list):
                    for msg in history:
                        if isinstance(msg, dict) and msg.get('role') in ['user', 'assistant'] and msg.get('content'):
                            messages_payload.append({"role": msg['role'], "content": str(msg['content'])})
                
                messages_payload.append({"role": "user", "content": str(user_message)})

                # --- LOGICA DE SEGURIDAD CRITICA ---
                # Si el usuario no tiene docs permitidos, enviamos un ID falso para bloquear la búsqueda global
                safe_docs_ids = docs_ids_filtrados if docs_ids_filtrados else ["non_existent_id"]

                payload = {
                    "messages": messages_payload,
                    "use_context": True, 
                    "include_sources": True,
                    "stream": True,
                    "temperature": 0.0,
                    "context_filter": {
                        "docs_ids": safe_docs_ids
                    }
                }

                url = f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions"
                
                # --- LLAMADA A PRIVATE-GPT PROTEGIDA ---
                try:
                    # Timeout elevado a 300s para CPUs lentas
                    with requests.post(url, json=payload, stream=True, timeout=300) as r:
                        if r.status_code != 200:
                            error_msg = f"Error {r.status_code} en PrivateGPT: {r.text}"
                            logger.error(error_msg)
                            yield json.dumps({"type": "error", "text": "El cerebro de la IA no respondió correctamente."}) + "\n"
                            return

                        full_response_text = ""
                        for line in r.iter_lines():
                            if line:
                                try:
                                    line_str = line.decode('utf-8').replace('data: ', '')
                                    if line_str == "[DONE]": break
                                    chunk = json.loads(line_str)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    full_response_text += content
                                except json.JSONDecodeError:
                                    continue
                                except Exception as e:
                                    logger.warning(f"Error procesando chunk: {e}")
                                    continue

                        # --- PROCESAMIENTO DE LA RESPUESTA (JSON PARSING) ---
                        try:
                            match = re.search(r"\{[\s\S]*\}", full_response_text)
                            if match:
                                json_str = match.group(0)
                                ai_data = json.loads(json_str)
                            else:
                                logger.warning("No se encontró JSON en respuesta IA. Usando texto crudo.")
                                ai_data = {
                                    "action": "ANSWER",
                                    "response": full_response_text,
                                    "sources": []
                                }
                            
                            action = ai_data.get("action", "ANSWER")

                            if action == "FUNCTION":
                                func_name = ai_data.get("function_name")
                                payload_data = None
                                ai_response_text = ai_data.get("response", "Procesando tu solicitud...")

                                if func_name == "search_data":
                                    if not UNEMI_DB:
                                        payload_data = {"status": "error", "message": "Base de datos no disponible."}
                                        ai_response_text = "Lo siento, no puedo acceder a la base de datos."
                                    elif current_cedula and current_cedula in UNEMI_DB:
                                        user_info = UNEMI_DB[current_cedula]
                                        # Intentamos usar el perfil activo detectado arriba
                                        perfil_data = {}
                                        if target_perfil_id:
                                            for p in user_info.get('perfiles', []):
                                                if str(p.get('id')) == str(target_perfil_id):
                                                    perfil_data = p
                                                    break
                                        if not perfil_data and user_info.get('perfiles'):
                                            perfil_data = user_info.get('perfiles')[0]

                                        payload_data = {
                                            "status": "success",
                                            "nombres": user_info.get('persona', {}).get('nombres', 'Estudiante'),
                                            "carrera": perfil_data.get('carrera_nombre', 'No registrada'),
                                            "tipo": perfil_data.get('tipo', 'N/A'),
                                            "nivel": perfil_data.get('nivel', 'N/A')
                                        }
                                        ai_response_text = f"He consultado tus datos de {payload_data['tipo']}."
                                    else:
                                        payload_data = {"status": "error", "message": "Debes seleccionar un usuario válido."}
                                        ai_response_text = "No puedo ver tus datos porque no has seleccionado un perfil válido."

                                yield json.dumps({
                                    "type": "final",
                                    "data": {
                                        "type": "function_call",
                                        "function": func_name,
                                        "text": ai_response_text,
                                        "payload": payload_data,
                                        "status": "executing"
                                    }
                                }) + "\n"
                                
                            elif action == "HANDOFF":
                                yield json.dumps({
                                    "type": "final",
                                    "data": {
                                        "type": "agent_handoff",
                                        "text": ai_data.get("response", "Te derivaré con un asesor."),
                                        "reason": "RAG_MISSING_INFO"
                                    }
                                }) + "\n"
                            else:
                                yield json.dumps({
                                    "type": "final",
                                    "data": {
                                        "type": "rag_response",
                                        "text": ai_data.get("response", "No pude generar una respuesta."),
                                        "sources": ai_data.get("sources", []),
                                        "has_information": True
                                    }
                                }) + "\n"

                        except json.JSONDecodeError:
                            logger.error(f"JSON corrupto de IA: {full_response_text}")
                            yield json.dumps({
                                "type": "final",
                                "data": {
                                    "type": "rag_response",
                                    "text": full_response_text,
                                    "sources": [],
                                    "warning": "Respuesta no estructurada"
                                }
                            }) + "\n"

                except requests.exceptions.ReadTimeout:
                    logger.error("PrivateGPT Timeout (más de 300s)")
                    yield json.dumps({"type": "error", "text": "El modelo está tardando demasiado en responder. Intenta de nuevo."}) + "\n"
                except requests.exceptions.ConnectionError:
                    logger.error("PrivateGPT Connection Refused")
                    yield json.dumps({"type": "error", "text": "No se pudo conectar con el cerebro de IA (PrivateGPT caído)."}) + "\n"
                except Exception as e:
                    logger.error(f"Error inesperado en request: {e}")
                    yield json.dumps({"type": "error", "text": f"Error de comunicación: {str(e)}"}) + "\n"

            except Exception as e:
                logger.error(f"Error crítico en view: {e}", exc_info=True)
                yield json.dumps({"type": "error", "text": "Error interno del servidor."}) + "\n"

        response = StreamingHttpResponse(event_stream(), content_type="application/x-ndjson")
        response['X-Accel-Buffering'] = 'no'
        return response

# --- NUEVO ENDPOINT PARA EL FRONTEND (UserSelector) ---
@require_http_methods(["GET"])
def get_users_list(request):
    if not UNEMI_DB:
        return JsonResponse({"error": "Base de datos no disponible"}, status=503)
    return JsonResponse(UNEMI_DB, safe=False)


@require_http_methods(["GET"])
def health(request):
    pgpt_status = False
    pgpt_error = None
    
    try:
        pgpt_url = f"{settings.PRIVATE_GPT_API_URL}/health"
        try:
            r = requests.get(pgpt_url, timeout=3)
            if r.status_code == 200:
                pgpt_status = True
        except requests.exceptions.ConnectionError:
            pgpt_error = "Connection Refused"
        except Exception as e:
            pgpt_error = str(e)

        return JsonResponse({
            'status': 'ok',
            'service': 'balcon_chatbot_frontend',
            'private_gpt_connected': pgpt_status,
            'db_loaded': bool(UNEMI_DB),
            'private_gpt_error': pgpt_error
        })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)