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

# IMPORTANTE: Asegúrate de que la ruta 'chatbot.models' sea correcta
# Si tus modelos están en otra app (ej. sga.models), cambia esto.
from chatbot.models import SgaPersona, SgaPerfilusuario, BusinessProcess

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. CONFIGURACIÓN Y CALENDARIO
# ==============================================================================

def get_process_response_from_db(trigger_name):
    """
    Busca en la base de datos el proceso asociado al nombre de la función
    que devolvió la IA (ej: 'change_career', 'drop_subject').
    Valida fechas y retorna el mensaje correspondiente.
    """
    try:
        # 1. Buscar el proceso activo por su trigger_function
        process = BusinessProcess.objects.filter(trigger_function=trigger_name, status=True).first()
        
        if not process:
            return {
                "text": f"No encontré información configurada para el proceso '{trigger_name}'. Por favor contacta a secretaría.",
                "status": "error"
            }

        # 2. Verificar si es infinito
        if process.is_infinite:
            return {
                "text": process.active_message, # Mensaje de Instrucción (Afirmación)
                "status": "success"
            }

        # 3. Validar fechas (Solo si no es infinito)
        today = datetime.now().date()
        
        # Asegurar que existan fechas
        if not process.start_date or not process.end_date:
            return {"text": "Error en la configuración de fechas del proceso.", "status": "error"}

        if process.start_date <= today <= process.end_date:
            # DENTRO DEL RANGO -> Mensaje de Instrucción
            return {
                "text": process.active_message,
                "status": "success"
            }
        else:
            # FUERA DEL RANGO -> Mensaje de Rechazo
            return {
                "text": process.closed_message,
                "status": "closed"
            }

    except Exception as e:
        logger.error(f"Error validando proceso: {e}")
        return {"text": "Ocurrió un error interno validando el proceso.", "status": "error"}

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
    """
    Devuelve únicamente al usuario con la cédula específica 0706191558,
    con todos sus perfiles detallados y una descripción legible.
    """
    data = []
    try:
        # 1. Filtramos por la cédula específica
        personas = SgaPersona.objects.filter(cedula='0706191558')
        
        for p in personas:
            # 2. Buscamos sus perfiles activos
            perfiles_qs = SgaPerfilusuario.objects.filter(persona=p, status=True)
            perfiles_list = []
            
            for perf in perfiles_qs:
                # 3. Mapeo completo de todos los campos de roles en el modelo
                roles_map = [
                    ('inscripcion', 'es_estudiante', 'Estudiante'),
                    ('profesor', 'es_profesor', 'Profesor'),
                    ('administrativo', 'es_administrativo', 'Administrativo'),
                    ('externo', 'es_externo', 'Externo'),
                    ('empleador', 'es_empleador', 'Empleador'),
                    ('instructor', 'es_instructor', 'Instructor'),
                    ('inscripcionaspirante', 'es_aspirante', 'Aspirante'),
                    ('inscripcionpostulante', 'es_postulante_inscripcion', 'Inscripción Postulante'),
                    ('postulante', 'es_postulante', 'Postulante'),
                    ('postulanteempleo', 'es_postulante_empleo', 'Postulante Empleo'),
                    ('inscripcionadmision', 'es_admision', 'Admisión'),
                    ('instructorejecutiva', 'es_instructor_ejecutiva', 'Instructor Ejecutiva'),
                    ('inscritoejecutivo', 'es_inscrito_ejecutivo', 'Inscrito Ejecutivo'),
                    ('instructorformacionejecutiva', 'es_instructor_formacion', 'Instructor Formación')
                ]

                perf_data = {"id": perf.id}
                roles_activos = []

                # Iteramos para llenar los booleanos y detectar los nombres para la descripción
                for field_name, json_key, label in roles_map:
                    # getattr obtiene el valor del campo dinámicamente (ej: perf.inscripcion)
                    # Si es un ID (entero > 0), bool() devolverá True. Si es None, False.
                    valor = getattr(perf, field_name, None)
                    es_activo = bool(valor)
                    
                    perf_data[json_key] = es_activo
                    
                    if es_activo:
                        roles_activos.append(label)

                # 4. Generamos la descripción final uniendo los roles encontrados
                # Ejemplo: "Estudiante / Profesor"
                perf_data["descripcion"] = " / ".join(roles_activos) if roles_activos else "Sin Rol Definido"

                perfiles_list.append(perf_data)

            # 5. Armamos la respuesta final
            data.append({
                "cedula": p.cedula,
                "persona": {
                    "nombres": p.nombres,
                    "apellido1": p.apellido1,
                    "apellido2": p.apellido2,
                    # Extra: Nombre completo para facilitar visualización
                    "nombre_completo": f"{p.nombres} {p.apellido1} {p.apellido2}".strip()
                },
                "perfiles": perfiles_list
            })
            
    except Exception as e:
        logger.error(f"Error obteniendo usuario: {e}")
        return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse(data, safe=False)
    

@require_http_methods(["GET"])
def health(request):
    pgpt_status = False
    try:
        # Verifica conexión con PrivateGPT
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

        # --- 1. ROLES Y PERFIL (USANDO MODELOS) ---
        roles = ["general"]
        persona = None
        
        if cedula:
            # Buscar la persona en la base de datos
            persona = SgaPersona.objects.filter(cedula=cedula, status=True).first()
            
            if persona:
                # Obtener el ID del perfil seleccionado desde la sesión
                target_pid = None
                if session.get(cedula, {}).get('perfiles'):
                    target_pid = session[cedula]['perfiles'][0].get('id')
                
                # Buscar el perfil específico
                perfil = None
                if target_pid:
                    perfil = SgaPerfilusuario.objects.filter(id=target_pid, persona=persona, status=True).first()
                
                # Fallback: Si no hay perfil seleccionado, tomar el primero activo
                if not perfil:
                     perfil = SgaPerfilusuario.objects.filter(persona=persona, status=True).first()

                if perfil:
                    # Determinar roles basados en campos del modelo
                    if perfil.inscripcion: roles.append("es_estudiante")
                    if perfil.profesor: roles.append("es_profesor")
                    if perfil.administrativo: roles.append("es_administrativo")
                    if perfil.externo: roles.append("es_externo")
                    if perfil.inscripcionaspirante: roles.append("es_inscripcionaspirante")
                    if perfil.inscripcionpostulante: roles.append("es_inscripcionpostulante")
                    if perfil.postulante: roles.append("es_postulante")
                    if perfil.postulanteempleo: roles.append("es_postulanteempleo")
                    if perfil.inscripcionadmision: roles.append("es_inscripcionadmision")

        # --- 2. FILTRO DOCS ---
        doc_ids = []
        try:
            r = requests.get(f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/list", timeout=5)
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

            yield json.dumps({"type": "status", "text": "Consultando reglamento y procesos..."}) + "\n"
            
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
                # Timeout None para esperar a que Ollama/PrivateGPT procese sin cortar la conexión
                with requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", json=payload, stream=True, timeout=600) as r:
                    full_text = ""
                    api_sources = [] 
                    
                    for line in r.iter_lines():
                        if line:
                            try:
                                line_str = line.decode('utf-8')
                                if not line_str.startswith('data: '): continue
                                line_str = line_str.replace('data: ', '')
                                if line_str == "[DONE]": break
                                
                                chunk = json.loads(line_str)
                                
                                # Texto acumulativo
                                if "choices" in chunk:
                                    delta = chunk["choices"][0].get("delta", {})
                                    full_text += delta.get("content", "")
                                
                                # Sources (Manejo de diferentes formatos de respuesta)
                                incoming_sources = None
                                if "sources" in chunk:
                                    incoming_sources = chunk["sources"]
                                elif "x_sources" in chunk:
                                    incoming_sources = chunk["x_sources"]
                                elif "choices" in chunk and chunk["choices"] and "sources" in chunk["choices"][0]:
                                    incoming_sources = chunk["choices"][0]["sources"]
                                
                                if isinstance(incoming_sources, list):
                                    api_sources = incoming_sources

                            except: continue
                    
                    # --- PROCESAMIENTO FINAL ---
                    
                    # 1. Limpiar Sources (Eliminar duplicados)
                    real_sources = []
                    seen_files = set()
                    
                    if api_sources and isinstance(api_sources, list):
                        for src in api_sources:
                            if not isinstance(src, dict): continue
                            doc = src.get("document", {})
                            meta = doc.get("doc_metadata", {})
                            file_name = meta.get("file_name", "Documento")
                            
                            if file_name not in seen_files:
                                real_sources.append({
                                    "title": file_name,
                                    "article": ""
                                })
                                seen_files.add(file_name)

                    # 2. Parsear JSON de respuesta de la IA
                    ai_data = {}
                    try:
                        # Intentar extraer JSON si la IA devolvió texto alrededor
                        match = re.search(r"\{[\s\S]*\}", full_text)
                        if match:
                            ai_data = json.loads(match.group(0))
                        else:
                            # Si no hay JSON válido, asumir que es texto plano
                            ai_data = {"action": "ANSWER", "response": full_text}
                    except:
                        ai_data = {"action": "ANSWER", "response": full_text}

                    # 3. Lógica de Function Calling (Validación Dinámica)
                    action = ai_data.get("action", "ANSWER")
                    func_name = ai_data.get("function_name")
                    
                    if action == "FUNCTION" and func_name:
                        
                        # CASO A: Datos Personales (Lógica dura existente)
                        if func_name == "search_data":
                             ai_resp = "Procesando solicitud de datos..."
                             p_data = {}
                             if persona:
                                 nombres_completos = f"{persona.nombres} {persona.apellido1} {persona.apellido2}".strip()
                                 p_data = {
                                     "status": "success", 
                                     "nombres": persona.nombres,
                                     "apellidos": f"{persona.apellido1} {persona.apellido2}".strip(),
                                     "nombre_completo": nombres_completos
                                 }
                                 ai_resp = f"Hola {nombres_completos}, aquí tienes tus datos."
                             else:
                                 p_data = {"status": "error", "message": "No se encontraron datos de la persona."}
                             
                             yield json.dumps({
                                "type": "final", 
                                "data": {
                                    "type": "function_call", 
                                    "function": func_name, 
                                    "text": ai_resp, 
                                    "payload": p_data
                                }
                            }) + "\n"

                        # CASO B: Procesos de Negocio Dinámicos (Consultar BD)
                        else:
                            # Llamada a la función helper definida arriba en views.py
                            process_result = get_process_response_from_db(func_name)
                            
                            yield json.dumps({
                                "type": "final", 
                                "data": {
                                    "type": "function_call", 
                                    "function": func_name,
                                    # El texto será el mensaje de 'activo' o 'cerrado' según las fechas
                                    "text": process_result["text"], 
                                    "payload": {
                                        "status": process_result["status"],
                                        "is_process_validation": True
                                    }
                                }
                            }) + "\n"

                    # CASO C: Respuesta RAG normal (Basada en documentos PDF)
                    else:
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
                yield json.dumps({"type": "error", "text": "Error de comunicación con el servidor de IA."}) + "\n"

# ==============================================================================
# 4. GESTIÓN DOCUMENTAL
# ==============================================================================

def document_manager(request):
    # --- Lógica de Documentos ---
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

    # --- AGREGADO: Lógica de Procesos (Para que se vean en la pestaña 2) ---
    processes = BusinessProcess.objects.filter(status=True).order_by('-fecha_creacion')

    # Enviamos ambas cosas al template 'document_manager.html' que ya tiene las pestañas
    return render(request, 'chatbot/document_manager.html', {
        'documents': documents, 
        'role_choices': role_choices,
        'processes': processes # <--- IMPORTANTE: Enviamos los procesos
    })

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
                r = requests.post(url, files={'file': (f.name, f.read(), f.content_type)}, timeout=600)
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

# ==============================================================================
# 5. GESTIÓN DE PROCESOS (BUSINESS PROCESSES)
# ==============================================================================

@require_http_methods(["GET"])
def process_manager(request):
    """ 
    Redirige a la vista principal de gestión. 
    Como document_manager.html ya tiene la pestaña de procesos, no necesitamos
    un html separado.
    """
    return redirect('chatbot:document_manager')

@require_http_methods(["POST"])
def create_process(request):
    """ Crea un nuevo proceso en la BD """
    try:
        name = request.POST.get('name')
        trigger = request.POST.get('trigger_function')
        is_infinite = request.POST.get('is_infinite') == 'on'
        
        # Manejo de fechas (si es infinito, ponemos null o la fecha de hoy por defecto para evitar errores)
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if is_infinite:
            # Si es infinito, usamos fechas dummy o None si el modelo lo permite. 
            # Como definimos DateField sin null=True, usaremos la fecha actual.
            start_date = datetime.now().date()
            end_date = datetime.now().date()
            
        active_msg = request.POST.get('active_message')
        closed_msg = request.POST.get('closed_message')

        BusinessProcess.objects.create(
            name=name,
            trigger_function=trigger,
            is_infinite=is_infinite,
            start_date=start_date,
            end_date=end_date,
            active_message=active_msg,
            closed_message=closed_msg,
            status=True # Activo por defecto
            # usuario_creacion se llena solo gracias a ModeloBase y ADMINISTRADOR_ID
        )
        messages.success(request, "Proceso creado correctamente.")
        
    except Exception as e:
        messages.error(request, f"Error al crear: {e}")
        
    return redirect('chatbot:process_manager')

@require_http_methods(["POST"])
def delete_process(request, process_id):
    """ Soft delete de un proceso """
    try:
        proc = BusinessProcess.objects.get(id=process_id)
        proc.status = False # Soft delete
        proc.save()
        messages.success(request, "Proceso eliminado.")
    except BusinessProcess.DoesNotExist:
        messages.error(request, "Proceso no encontrado.")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        
    return redirect('chatbot:process_manager')