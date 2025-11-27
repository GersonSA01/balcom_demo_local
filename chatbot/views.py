import json
import re
import requests
import logging
import os
import time
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. CARGA DE DATOS Y CONFIGURACIÓN
# ==============================================================================

def load_db():
    """Carga la base de datos JSON de usuarios en memoria."""
    json_path = os.path.join(settings.BASE_DIR, 'chatbot', 'data', 'data_unemi.json')
    try:
        if not os.path.exists(json_path):
            logger.warning(f"⚠️ Archivo no encontrado: {json_path}")
            return {}
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Error cargando DB: {e}")
        return {}

UNEMI_DB = load_db()

ACADEMIC_CALENDAR = {
    "change_career": {
        "start": "2025-01-01", "end": "2025-05-30",
        "error_msg": "El proceso de Cambio de Carrera no está activo actualmente."
    },
    "drop_subject": {
        "start": "2025-06-01", "end": "2025-07-15",
        "error_msg": "El proceso de Retiro de Asignatura está cerrado.",
        "classes_start_date": "2025-06-01"
    }
}

# ==============================================================================
# 2. LÓGICA DE NEGOCIO
# ==============================================================================

def check_process_dates(process_name):
    config = ACADEMIC_CALENDAR.get(process_name)
    if not config: return False, "Proceso no definido."
    
    today = datetime.now().date()
    try:
        start = datetime.strptime(config["start"], "%Y-%m-%d").date()
        end = datetime.strptime(config["end"], "%Y-%m-%d").date()
        if start <= today <= end:
            return True, f"✅ Proceso ACTIVO (hasta {end})."
        return False, f"❌ {config['error_msg']}"
    except ValueError:
        return False, "Error de fechas."

def get_drop_subject_message():
    config = ACADEMIC_CALENDAR.get("drop_subject")
    if not config: return "Error calendario."
    today = datetime.now().date()
    try:
        start = datetime.strptime(config["classes_start_date"], "%Y-%m-%d").date()
        days = (today - start).days
        if days < 0: return "Clases no iniciadas."
        if days <= 15: return f"Estás en el plazo (día {days}/15) para retiro voluntario."
        return "Plazo de 15 días finalizado. Solo retiro por fuerza mayor."
    except: return "Error fechas."

# ==============================================================================
# 3. ENDPOINTS API
# ==============================================================================

@require_http_methods(["GET"])
def get_users_list(request):
    if not UNEMI_DB: return JsonResponse({"error": "DB no disponible"}, status=503)
    return JsonResponse(UNEMI_DB, safe=False)

@require_http_methods(["GET"])
def health(request):
    pgpt_status = False
    try:
        if requests.get(f"{settings.PRIVATE_GPT_API_URL}/health", timeout=10).status_code == 200:
            pgpt_status = True
    except: pass
    return JsonResponse({'status': 'ok', 'private_gpt_connected': pgpt_status})

class ChatView(APIView):
    def post(self, request):
        if not request.data: return JsonResponse({"error": "Empty"}, status=400)
        
        user_msg = request.data.get('message', '')
        history = request.data.get('history', [])
        session = request.data.get('session_data', {})
        cedula = list(session.keys())[0] if session else None

        # --- 1. ROLES ---
        roles = ["general"]
        target_pid = None
        if cedula and session.get(cedula, {}).get('perfiles'):
            target_pid = session[cedula]['perfiles'][0].get('id')

        if cedula and cedula in UNEMI_DB:
            user_data = UNEMI_DB[cedula]
            perfil = next((p for p in user_data.get('perfiles', []) if str(p.get('id')) == str(target_pid)), None)
            if perfil:
                KEYS = ["es_estudiante", "es_profesor", "es_administrativo", "es_externo",
                        "es_inscripcionaspirante", "es_inscripcionpostulante", "es_postulante",
                        "es_postulanteempleo", "es_inscripcionadmision"]
                for k in KEYS:
                    if perfil.get(k) is True: roles.append(k)

        # --- 2. FILTRO DOCS ---
        doc_ids = []
        try:
            r = requests.get(f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/list", timeout=3)
            if r.status_code == 200:
                for doc in r.json().get('data', []):
                    meta = doc.get('doc_metadata', {})
                    doc_roles = meta.get('role', ['general'])
                    if isinstance(doc_roles, str): doc_roles = [doc_roles]
                    
                    role_match = any(r in roles for r in doc_roles)
                    
                    date_match = True
                    if meta.get('is_infinite') is False:
                        try:
                            today_str = datetime.now().strftime("%Y-%m-%d")
                            v_from = meta.get('valid_from')
                            v_to = meta.get('valid_to')
                            if v_from and today_str < v_from: date_match = False
                            if v_to and today_str > v_to: date_match = False
                        except: pass

                    if role_match and date_match:
                        doc_ids.append(doc.get('doc_id'))
        except Exception as e:
            logger.error(f"Error filtro docs: {e}")

        # --- 3. STREAMING ---
        def event_stream():
            if not doc_ids:
                yield json.dumps({"type": "final", "data": {"type": "rag_response", "text": "No hay documentos vigentes disponibles para tu perfil.", "sources": []}}) + "\n"
                return

            yield json.dumps({"type": "status", "text": "Consultando..."}) + "\n"
            
            messages_payload = [{"role": "user", "content": user_msg}]
            if history:
                for msg in history[-4:]:
                    messages_payload.insert(0, {"role": msg['role'], "content": str(msg['content'])})

            payload = {
                "messages": messages_payload,
                "use_context": True,
                "include_sources": True,
                "stream": True,
                "context_filter": {"docs_ids": doc_ids},
                "temperature": 0.0
            }

            try:
                # Timeout None para esperar a que Ollama piense
                with requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", json=payload, stream=True, timeout=None) as r:
                    full_text = ""
                    api_sources = [] # Inicializado vacío
                    
                    for line in r.iter_lines():
                        if line:
                            try:
                                line_str = line.decode('utf-8')
                                if not line_str.startswith('data: '): continue
                                line_str = line_str.replace('data: ', '')
                                if line_str == "[DONE]": break
                                
                                chunk = json.loads(line_str)
                                
                                # Texto
                                if "choices" in chunk:
                                    delta = chunk["choices"][0].get("delta", {})
                                    full_text += delta.get("content", "")
                                
                                # --- CAPTURA SEGURA DE SOURCES ---
                                # Verificamos que sea una lista antes de asignarlo
                                incoming_sources = None
                                if "sources" in chunk:
                                    incoming_sources = chunk["sources"]
                                elif "x_sources" in chunk:
                                    incoming_sources = chunk["x_sources"]
                                elif "choices" in chunk and chunk["choices"] and "sources" in chunk["choices"][0]:
                                    incoming_sources = chunk["choices"][0]["sources"]
                                
                                # Solo actualizamos si lo que llegó es una lista válida
                                if isinstance(incoming_sources, list):
                                    api_sources = incoming_sources

                            except: continue
                    
                    # --- PROCESAMIENTO FINAL ---
                    
                    # 1. Limpiar Sources (NO REPETIDOS, SOLO NOMBRE)
                    real_sources = []
                    seen_files = set()
                    
                    # Validación extra para evitar el error 'NoneType not iterable'
                    if api_sources and isinstance(api_sources, list):
                        for src in api_sources:
                            if not isinstance(src, dict): continue
                            
                            doc = src.get("document", {})
                            meta = doc.get("doc_metadata", {})
                            file_name = meta.get("file_name", "Documento")
                            
                            # Lógica: Solo 1 vez por archivo, sin páginas
                            if file_name not in seen_files:
                                real_sources.append({
                                    "title": file_name,
                                    "article": "" # Vacío para que el frontend no muestre páginas
                                })
                                seen_files.add(file_name)

                    # 2. Parsear JSON
                    ai_data = {}
                    try:
                        match = re.search(r"\{[\s\S]*\}", full_text)
                        if match:
                            ai_data = json.loads(match.group(0))
                        else:
                            ai_data = {"action": "ANSWER", "response": full_text}
                    except:
                        ai_data = {"action": "ANSWER", "response": full_text}

                    # Function calling logic (Search Data, etc)
                    action = ai_data.get("action", "ANSWER")
                    func_name = ai_data.get("function_name")
                    
                    if action == "FUNCTION" and func_name:
                        # ... (lógica de funciones igual que antes) ...
                        ai_resp = "Procesando..."
                        p_data = {}
                        
                        if func_name == "search_data":
                             # (Lógica simplificada para brevedad)
                             if cedula and cedula in UNEMI_DB:
                                 info = UNEMI_DB[cedula]['persona']
                                 p_data = {"status": "success", "nombres": info.get('nombres', '')}
                                 ai_resp = f"Hola {info.get('nombres')}."
                             else:
                                 p_data = {"status": "error"}
                        
                        yield json.dumps({
                            "type": "final", 
                            "data": {
                                "type": "function_call", 
                                "function": func_name, 
                                "text": ai_resp, 
                                "payload": p_data
                            }
                        }) + "\n"
                    else:
                        # Respuesta RAG Normal
                        yield json.dumps({
                            "type": "final",
                            "data": {
                                "type": "rag_response",
                                "text": json.dumps(ai_data), 
                                "sources": real_sources,
                                "has_information": True
                            }
                        }) + "\n"

            except Exception as e:
                logger.error(f"Error streaming: {e}")
                yield json.dumps({"type": "error", "text": "Error en el servidor de IA."}) + "\n"

        response = StreamingHttpResponse(event_stream(), content_type="application/x-ndjson")
        response['X-Accel-Buffering'] = 'no'
        return response

# ==============================================================================
# 4. GESTIÓN DOCUMENTAL
# ==============================================================================

def document_manager(request):
    documents = []
    try:
        resp = requests.get(f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/list", timeout=5)
        if resp.status_code == 200:
            raw = resp.json().get('data', [])
            uniq = {}
            for d in raw:
                uniq[d.get('doc_metadata', {}).get('file_name')] = d
            documents = list(uniq.values())
            documents.sort(key=lambda x: x['doc_metadata'].get('file_name', ''))
    except: pass

    role_choices = [
        ("general", "General"), ("es_estudiante", "Estudiante"), ("es_profesor", "Profesor"),
        ("es_administrativo", "Administrativo"), ("es_externo", "Externo"),
        ("es_inscripcionaspirante", "Inscripción Aspirante"), ("es_inscripcionpostulante", "Inscripción Postulante"),
        ("es_postulante", "Postulante"), ("es_postulanteempleo", "Postulante Empleo"),
        ("es_inscripcionadmision", "Inscripción Admisión")
    ]
    return render(request, 'chatbot/document_manager.html', {'documents': documents, 'role_choices': role_choices})

def upload_document(request):
    if request.method == 'POST':
        files = request.FILES.getlist('file')
        roles = request.POST.getlist('roles') or ['general']
        is_inf = request.POST.get('is_infinite') == 'on'
        v_from = request.POST.get('valid_from')
        v_to = request.POST.get('valid_to')

        payload = {"roles": roles, "is_infinite": is_inf, "valid_from": v_from if v_from else None, "valid_to": v_to if v_to else None}

        try:
            url = f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/file"
            count = 0
            for f in files:
                r = requests.post(url, files={'file': (f.name, f.read(), f.content_type)}, timeout=None)
                if r.status_code == 200:
                    docs = r.json().get('data', [])
                    for d in docs:
                        requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{d['doc_id']}/metadata", json=payload, timeout=5)
                    count += 1
            messages.success(request, f"Subidos {count} archivos.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('chatbot:document_manager')

def delete_document(request, doc_id):
    if request.method == 'POST':
        try:
            api = settings.PRIVATE_GPT_API_URL
            all_docs = requests.get(f"{api}/v1/ingest/list").json().get('data', [])
            target = next((d['doc_metadata']['file_name'] for d in all_docs if d['doc_id'] == doc_id), None)
            if target:
                for d in all_docs:
                    if d['doc_metadata'].get('file_name') == target:
                        requests.delete(f"{api}/v1/ingest/{d['doc_id']}")
                messages.success(request, f"Eliminado: {target}")
            else:
                messages.error(request, "No encontrado.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('chatbot:document_manager')

def update_document_role(request, doc_id):
    if request.method == 'POST':
        roles = request.POST.getlist('roles') or ['general']
        is_inf = request.POST.get('is_infinite') == 'on'
        v_from = request.POST.get('valid_from')
        v_to = request.POST.get('valid_to')
        payload = {"roles": roles, "is_infinite": is_inf, "valid_from": v_from if v_from else None, "valid_to": v_to if v_to else None}

        try:
            api = settings.PRIVATE_GPT_API_URL
            all_docs = requests.get(f"{api}/v1/ingest/list").json().get('data', [])
            target = next((d['doc_metadata']['file_name'] for d in all_docs if d['doc_id'] == doc_id), None)
            if target:
                for d in all_docs:
                    if d['doc_metadata'].get('file_name') == target:
                        requests.post(f"{api}/v1/ingest/{d['doc_id']}/metadata", json=payload)
                messages.success(request, "Actualizado.")
            else:
                messages.error(request, "No encontrado.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('chatbot:document_manager')