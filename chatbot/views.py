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
from chatbot.models import SgaPersona, SgaPerfilusuario, BusinessProcess, RagDocument

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. CONFIGURACIÓN Y CALENDARIO
# ==============================================================================

def get_process_response_from_db(process_name):
    """
    Busca en la base de datos el proceso y formatea un mensaje amigable.
    """
    try:
        # 1. Buscar el proceso activo
        process = BusinessProcess.objects.filter(name=process_name, status=True).first()
        
        if not process:
            return {
                "text": f"No encontré información configurada para el proceso '{process_name}'. Por favor contacta a secretaría.",
                "status": "error",
                "need_documentation": False
            }

        # --- CAMBIO: CONSTRUCCIÓN DE MENSAJE AMIGABLE ---
        # Envolvemos los requisitos de la BD con el saludo y la instrucción final
        friendly_text = (
            "Hola, para procesar tu solicitud por favor necesito que me ayudes con tu documentación:\n\n"
            f"{process.active_message}\n\n"
            "También necesitaré que me des de nuevo los detalles de tu solicitud."
        )

        # Lógica específica por tipo de proceso
        if process.process_type == "informativo":
            # Si es informativo, usamos el mensaje activo directo o el contexto
            friendly_text = process.active_message or process.business_context
            # Forzamos need_documentation a False
            process.need_documentation = False

        base_response = {
            "text": friendly_text,
            "need_documentation": process.need_documentation,
            "source_url": process.source_url
        }

        # 2. Verificar si es infinito
        if process.is_infinite:
            base_response["status"] = "success"
            return base_response

        # 3. Validar fechas
        today = datetime.now().date()
        
        if not process.start_date or not process.end_date:
            return {
                "text": "Error en configuración de fechas.", 
                "status": "error", 
                "need_documentation": False
            }

        if process.start_date <= today <= process.end_date:
            base_response["status"] = "success"
            return base_response
        else:
            msg_closed = f"El proceso '{process.name}' no se encuentra habilitado actualmente (Vigencia: {process.start_date.strftime('%d/%m/%Y')} - {process.end_date.strftime('%d/%m/%Y')})."
            return {
                "text": msg_closed,
                "status": "closed",
                "need_documentation": False
            }

    except Exception as e:
        logger.error(f"Error validando proceso: {e}")
        return {
            "text": "Ocurrió un error interno validando el proceso.", 
            "status": "error",
            "need_documentation": False
        }

# ==============================================================================
# 2. ENDPOINTS API DE USUARIOS
# ==============================================================================

@require_http_methods(["GET"])
def get_users_list(request):
    """
    Devuelve únicamente al usuario con la cédula específica,
    con todos sus perfiles detallados y una descripción legible.
    """
    data = []
    try:
        # 1. Filtramos por la cédula específica (Puedes cambiar esto según necesidad)
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
                    valor = getattr(perf, field_name, None)
                    es_activo = bool(valor)
                    perf_data[json_key] = es_activo
                    if es_activo:
                        roles_activos.append(label)

                # 4. Generamos la descripción final
                perf_data["descripcion"] = " / ".join(roles_activos) if roles_activos else "Sin Rol Definido"
                perfiles_list.append(perf_data)

            # 5. Armamos la respuesta final
            data.append({
                "cedula": p.cedula,
                "persona": {
                    "nombres": p.nombres,
                    "apellido1": p.apellido1,
                    "apellido2": p.apellido2,
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
        if requests.get(f"{settings.PRIVATE_GPT_API_URL}/health", timeout=10).status_code == 200:
            pgpt_status = True
    except: pass
    return JsonResponse({'status': 'ok', 'private_gpt_connected': pgpt_status})

# ==============================================================================
# 3. CLASE PRINCIPAL DEL CHATBOT (LÓGICA RAG + PROCESOS)
# ==============================================================================

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
            persona = SgaPersona.objects.filter(cedula=cedula, status=True).first()
            if persona:
                # Obtener el ID del perfil seleccionado
                target_pid = None
                if session.get(cedula, {}).get('perfiles'):
                    target_pid = session[cedula]['perfiles'][0].get('id')
                
                perfil = None
                if target_pid:
                    perfil = SgaPerfilusuario.objects.filter(id=target_pid, persona=persona, status=True).first()
                if not perfil:
                     perfil = SgaPerfilusuario.objects.filter(persona=persona, status=True).first()

                if perfil:
                    # Determinar roles basados en campos del modelo
                    if perfil.inscripcion: roles.append("es_estudiante")
                    if perfil.profesor: roles.append("es_profesor")
                    if perfil.administrativo: roles.append("es_administrativo")
                    if perfil.externo: roles.append("es_externo")
                    if perfil.inscripcionaspirante: roles.append("es_inscripcionaspirante")
                    # ... se pueden agregar más mapeos aquí ...

        # --- 2. FILTER DOCUMENTS (RAG) ---
        # OPTIMIZACIÓN: Consultamos la BD Local (SQL) en lugar de la API lenta de PrivateGPT
        doc_ids = []
        try:
            # 1. Obtenemos todos los documentos activos de nuestra BD local
            # Esto es instantáneo (milisegundos) vs los 15s de PrivateGPT
            local_docs = RagDocument.objects.filter(status=True, is_indexed=True)
            
            today = datetime.now().date()

            for doc in local_docs:
                # A. Filtrado por Roles
                # doc.roles es un JSONField, es una lista directa en Python
                doc_roles = doc.roles if isinstance(doc.roles, list) else []
                if not doc_roles: doc_roles = ['general'] # Fallback
                
                # Verificamos si el usuario tiene alguno de los roles del documento
                role_match = any(r in roles for r in doc_roles)
                
                # B. Filtrado por Fechas
                date_match = True
                if not doc.is_infinite:
                    if doc.valid_from and today < doc.valid_from: date_match = False
                    if doc.valid_to and today > doc.valid_to: date_match = False
                
                # C. Si pasa los filtros, agregamos el ID de PrivateGPT a la lista
                if role_match and date_match and doc.doc_id_pgpt:
                    doc_ids.append(doc.doc_id_pgpt)

            logger.info(f"Filtro RAG rápido: {len(doc_ids)} documentos seleccionados de {local_docs.count()} disponibles.")

        except Exception as e:
            logger.error(f"Error filtro docs local: {e}")
            # En caso de error crítico, doc_ids queda vacío y no se usa contexto, pero no


        # Get all active processes
        available_processes = BusinessProcess.objects.filter(status=True)
        
        # Filter processes that match the user's roles AND are currently valid by date
        valid_process_names = []
        valid_process_details = []  # Esto se manda como data_tools al LLM

        today = datetime.now().date()

        for proc in available_processes:
            # 1) Vigencia por fecha
            if not proc.is_infinite:
                # Si no hay fechas configuradas, se salta
                if not proc.start_date or not proc.end_date:
                    continue
                if not (proc.start_date <= today <= proc.end_date):
                    continue

            # 2) Roles permitidos
            proc_roles = getattr(proc, 'roles', ['general'])
            if not isinstance(proc_roles, list):
                proc_roles = ['general']

            if 'general' in proc_roles or any(r in proc_roles for r in roles):
                valid_process_names.append(proc.name)

                business_ctx = (getattr(proc, 'business_context', '') or '').strip()
                vigencia = (
                    "Siempre activo"
                    if proc.is_infinite
                    else f"Vigente del {proc.start_date.strftime('%d/%m/%Y')} al {proc.end_date.strftime('%d/%m/%Y')}"
                )
                roles_text = ", ".join(proc_roles)

                # ESTA LÍNEA ES LO QUE LUEGO LEE EL LLM EN {data_tools}
                valid_process_details.append(
                    f"- {proc.name}: {business_ctx} [Roles: {roles_text}; {vigencia}]"
                )


        # --- 4. MODIFIED STREAMING LOGIC ---
        def event_stream():
            # CRITICAL CHANGE: Only stop if NO docs AND NO processes
            if not doc_ids and not valid_process_names:
                yield json.dumps({"type": "final", "data": {"type": "rag_response", "text": "No tienes permisos para ver documentos ni procesos con tu perfil actual.", "sources": []}}) + "\n"
                return

            status_msg = "Consultando base de conocimiento..."
            if not doc_ids and valid_process_names:
                status_msg = "Consultando procesos disponibles..."

            yield json.dumps({"type": "status", "text": status_msg}) + "\n"
            
            # Preparar Mensajes
            messages_payload = [{"role": "user", "content": user_msg}]
            
            # INYECCIÓN DE CONTEXTO DE PROCESOS (System Prompt Injection)
            # Le decimos al LLM qué herramientas tiene disponibles según el perfil
            system_instruction = ""
            if valid_process_details:
                system_instruction = "\n".join(valid_process_details)

            # Insertamos la instrucción de sistema al principio (solo data_tools)
            messages_payload.insert(0, {"role": "system", "content": system_instruction})

            # Historial
            if history:
                for msg in history[-4:]:
                    messages_payload.insert(1, {"role": msg['role'], "content": str(msg['content'])})

            payload = {
                "messages": messages_payload,
                "use_context": True if doc_ids else False, # Solo usar contexto si hay docs
                "include_sources": True,
                "stream": True,
                "context_filter": {"docs_ids": doc_ids} if doc_ids else None,
                "temperature": 0.0
            }

            try:
                # Timeout alto para procesos largos
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
                                
                                # Sources
                                incoming_sources = None
                                if "sources" in chunk: incoming_sources = chunk["sources"]
                                elif "x_sources" in chunk: incoming_sources = chunk["x_sources"]
                                elif "choices" in chunk and chunk["choices"] and "sources" in chunk["choices"][0]:
                                    incoming_sources = chunk["choices"][0]["sources"]
                                
                                if isinstance(incoming_sources, list):
                                    api_sources = incoming_sources

                            except: continue
                    
                    # --- PROCESAMIENTO FINAL ---
                    
                    # 1. Limpiar Sources y ENRIQUECER con URL local
                    real_sources = []
                    seen_files = set()

                    if api_sources and isinstance(api_sources, list):
                        for src in api_sources:
                            if not isinstance(src, dict): continue
                            
                            doc = src.get("document", {})
                            meta = doc.get("doc_metadata", {})
                            
                            file_name = meta.get("file_name", "Documento")
                            pgpt_id = doc.get("doc_id")  # PrivateGPT devuelve el UUID aquí o en metadata
                            
                            # Si no está directo en doc, busca en metadata
                            if not pgpt_id: 
                                pgpt_id = meta.get("doc_id") 

                            if file_name not in seen_files:
                                # === AQUÍ HACEMOS LA MAGIA ===
                                # Buscamos en nuestra tabla RagDocument el archivo que tenga ese ID
                                doc_url = None
                                if pgpt_id:
                                    local_doc = RagDocument.objects.filter(doc_id_pgpt=pgpt_id).first()
                                    if local_doc and local_doc.archivo:
                                        # Generamos URL absoluta (http://localhost:8000/media/...)
                                        # para que funcione desde el frontend (puerto 5173)
                                        doc_url = request.build_absolute_uri(local_doc.archivo.url)
                                
                                # Agregamos la URL al objeto que enviamos al Svelte
                                real_sources.append({
                                    "title": file_name, 
                                    "article": "",
                                    "url": doc_url  # <--- Nuevo campo
                                })
                                seen_files.add(file_name)

                    if not full_text.strip():
                        full_text = "Lo siento, por el momento no puedo generar respuestas."

                    # 2. Parsear JSON de respuesta de la IA
                    ai_data = {}
                    try:
                        match = re.search(r"\{[\s\S]*\}", full_text)
                        if match:
                            ai_data = json.loads(match.group(0))
                        else:
                            ai_data = {"action": "ANSWER", "response": full_text}
                    except:
                        ai_data = {"action": "ANSWER", "response": full_text}

                    # 3. Lógica de Function Calling (Dynamic Validation)
                    action = ai_data.get("action", "ANSWER")
                    func_name = ai_data.get("function_name")
                    
                    if action == "FUNCTION" and func_name:
                        
                        # --- SECURITY CHECK ---
                        # Verify if the user has permission for this function
                        # search_data is allowed by default usually, unless restricted
                        if func_name not in valid_process_names and func_name != "search_data": 
                             yield json.dumps({
                                "type": "final", 
                                "data": {
                                    "type": "rag_response", # Fallback to text
                                    "text": f"Lo siento, tu perfil ({'/'.join(roles)}) no tiene permisos para ejecutar el trámite: {func_name}.",
                                    "sources": []
                                }
                            }) + "\n"
                             return
                        # ----------------------

                        # CASO A: Datos Personales
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

                        # CASO B: Dynamic Business Processes
                        elif func_name in valid_process_names:
                            # Usuario autorizado -> Consultar BD
                            process_result = get_process_response_from_db(func_name)
                            
                            yield json.dumps({
                                "type": "final", 
                                "data": {
                                    "type": "function_call", 
                                    "function": func_name,
                                    "text": process_result["text"], 
                                    
                                    # --- AQUÍ ESTÁ EL CAMBIO ---
                                    "payload": {
                                        "status": process_result["status"],
                                        "is_process_validation": True,
                                        # Enviamos el flag al frontend para que pinte el botón
                                        "need_documentation": process_result.get("need_documentation", False)
                                    }
                                }
                            }) + "\n"

                    # CASO C: Respuesta RAG normal
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
    
        return StreamingHttpResponse(event_stream(), content_type='application/x-ndjson')

# ==============================================================================
# 4. GESTIÓN DOCUMENTAL
# ==============================================================================

def document_manager(request):
    # Consultamos directo a la BD (Mucho más rápido y permite paginación)
    documents = RagDocument.objects.filter(status=True).order_by('-fecha_creacion')

    role_choices = [
        ("general", "General"), ("es_estudiante", "Estudiante"), ("es_profesor", "Profesor"),
        ("es_administrativo", "Administrativo"), ("es_externo", "Externo"),
        ("es_inscripcionaspirante", "Inscripción Aspirante"), ("es_inscripcionpostulante", "Inscripción Postulante"),
        ("es_postulante", "Postulante"), ("es_postulanteempleo", "Postulante Empleo"),
        ("es_inscripcionadmision", "Inscripción Admisión")
    ]

    # --- AGREGADO: Lógica de Procesos ---
    processes = BusinessProcess.objects.filter(status=True).order_by('-fecha_creacion')

    return render(request, 'chatbot/document_manager.html', {
        'documents': documents, 
        'role_choices': role_choices,
        'processes': processes
    })

def upload_document(request):
    if request.method == 'POST':
        files = request.FILES.getlist('file')
        
        # Recoger datos del formulario
        roles = request.POST.getlist('roles') or ['general']
        is_inf = request.POST.get('is_infinite') == 'on'
        v_from = request.POST.get('valid_from') or None
        v_to = request.POST.get('valid_to') or None

        count = 0
        skip = 0
        
        try:
            ingest_url = f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/file"
            
            for f in files:
                # --- VALIDACIÓN ANTI-DUPLICADOS ---
                # Verificamos si ya existe un documento activo con ese nombre exacto
                if RagDocument.objects.filter(nombre=f.name, status=True).exists():
                    skip += 1
                    continue  # Saltamos al siguiente archivo
                # ----------------------------------

                # 1. GUARDAR EN BD LOCAL (Fuente de la verdad)
                # Esto sube el archivo a 'media/rag_docs/' automáticamente gracias al FileField
                doc_db = RagDocument(
                    archivo=f,
                    nombre=f.name,
                    roles=roles,
                    is_infinite=is_inf,
                    valid_from=v_from,
                    valid_to=v_to,
                    is_indexed=False 
                )
                doc_db.save(request) # Pasamos request para que ModeloBase guarde el usuario_creacion

                # 2. ENVIAR A PRIVATE-GPT (Sincronización)
                try:
                    # Abrimos el archivo que Django ya guardó en disco
                    with doc_db.archivo.open('rb') as local_file:
                        r = requests.post(
                            ingest_url, 
                            files={'file': (doc_db.nombre, local_file, 'application/pdf')}, # Ajustar content-type si varía
                            timeout=600
                        )
                    
                    if r.status_code == 200:
                        resp_data = r.json().get('data', [])
                        if resp_data:
                            # 3. ACTUALIZAR REFERENCIA EXTERNA
                            pgpt_id = resp_data[0]['doc_id']
                            doc_db.doc_id_pgpt = pgpt_id
                            doc_db.is_indexed = True
                            doc_db.save(request)
                            
                            # (Opcional) Subir metadata a PGPT también para que el RAG filtre bien
                            meta_payload = {
                                "roles": roles, "is_infinite": is_inf, 
                                "valid_from": v_from, "valid_to": v_to,
                                "db_id": doc_db.id, # Útil para referencias cruzadas
                                "access_url": doc_db.archivo.url
                            }
                            requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{pgpt_id}/metadata", json=meta_payload)
                            
                    count += 1
                except Exception as e:
                    logger.error(f"Error indexando en IA, pero guardado en BD: {e}")
                    # El archivo existe en BD pero is_indexed=False. Podrías tener un cronjob que reintente luego.

            # Mensaje final más informativo
            msg = f"Se subieron {count} archivos."
            if skip > 0:
                msg += f" (Se omitieron {skip} duplicados)."
            
            messages.success(request, msg)
            
        except Exception as e:
            messages.error(request, f"Error crítico: {e}")

    return redirect('chatbot:document_manager')

def delete_document(request, doc_id):
    # doc_id ahora es el ID (int) de la base de datos local, no el string de PrivateGPT
    if request.method == 'POST':
        try:
            # 1. Buscar en BD local
            doc = RagDocument.objects.get(id=doc_id)
            
            # 2. Eliminar de PrivateGPT (si estaba indexado)
            if doc.doc_id_pgpt:
                try:
                    requests.delete(f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{doc.doc_id_pgpt}", timeout=30)
                except Exception as e:
                    logger.error(f"Error borrando de IA: {e}")

            # 3. Eliminar archivo físico y registro de BD
            # Django elimina el archivo físico automáticamente si el FileField está bien configurado,
            # o puedes forzarlo: doc.archivo.delete()
            doc.archivo.delete(save=False) 
            doc.delete()
            
            messages.success(request, f"Documento '{doc.nombre}' eliminado correctamente.")
            
        except RagDocument.DoesNotExist:
            messages.error(request, "El documento no existe en la base de datos.")
        except Exception as e:
            messages.error(request, f"Error eliminando documento: {e}")
            
    return redirect('chatbot:document_manager')

def update_document_role(request, doc_id):
    if request.method == 'POST':
        try:
            # 1. Obtener datos del form
            roles = request.POST.getlist('roles') or ['general']
            is_inf = request.POST.get('is_infinite') == 'on'
            v_from = request.POST.get('valid_from') or None
            v_to = request.POST.get('valid_to') or None

            # 2. Actualizar BD Local
            doc = RagDocument.objects.get(id=doc_id)
            doc.roles = roles
            doc.is_infinite = is_inf
            doc.valid_from = v_from
            doc.valid_to = v_to
            doc.save(request) # Pasa request para auditoría ModeloBase

            # 3. Sincronizar con PrivateGPT
            if doc.doc_id_pgpt:
                payload = {
                    "roles": roles, 
                    "is_infinite": is_inf, 
                    "valid_from": v_from, 
                    "valid_to": v_to,
                    "access_url": doc.archivo.url # Mantenemos la URL actualizada por si acaso
                }
                requests.post(
                    f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{doc.doc_id_pgpt}/metadata", 
                    json=payload,
                    timeout=30
                )

            messages.success(request, "Documento actualizado.")
            
        except RagDocument.DoesNotExist:
            messages.error(request, "Documento no encontrado.")
        except Exception as e:
            messages.error(request, f"Error actualizando: {e}")
            
    return redirect('chatbot:document_manager')

# ==============================================================================
# 5. GESTIÓN DE PROCESOS (BUSINESS PROCESSES)
# ==============================================================================

@require_http_methods(["GET"])
def process_manager(request):
    return redirect('chatbot:document_manager')

@require_http_methods(["POST"])
def create_process(request):
    try:
        name = request.POST.get('name')
        process_type = request.POST.get('process_type', 'informativo')
        source_url = request.POST.get('source_url') or None
        
        is_infinite = request.POST.get('is_infinite') == 'on'
        
        need_documentation = request.POST.get('need_documentation') == 'on'
        if process_type == "informativo":
            need_documentation = False
            
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        active_msg = request.POST.get('active_message')
        business_context = request.POST.get('business_context') 
        
        roles = request.POST.getlist('roles')
        if not roles: roles = ['general']

        if is_infinite:
            start_date = datetime.now().date()
            end_date = datetime.now().date()

        BusinessProcess.objects.create(
            name=name,
            process_type=process_type,
            source_url=source_url,
            is_infinite=is_infinite,
            business_context=business_context,
            need_documentation=need_documentation, 
            start_date=start_date,
            end_date=end_date,
            active_message=active_msg,
            roles=roles,
            status=True
        )
        messages.success(request, "Proceso creado correctamente.")
        
    except Exception as e:
        messages.error(request, f"Error al crear: {e}")
        
    return redirect('chatbot:process_manager')

@require_http_methods(["POST"])
def delete_process(request, process_id):
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

@require_http_methods(["POST"])
def edit_process(request, process_id):
    try:
        proc = BusinessProcess.objects.get(id=process_id)
        
        proc.name = request.POST.get('name')
        proc.business_context = request.POST.get('business_context')
        proc.process_type = request.POST.get('process_type', proc.process_type)
        proc.source_url = request.POST.get('source_url') or None
        
        proc.is_infinite = request.POST.get('is_infinite') == 'on'
        
        # --- NUEVO: Requiere Documentación ---
        if proc.process_type == "operativo":
            proc.need_documentation = request.POST.get('need_documentation') == 'on'
        else:
            proc.need_documentation = False
        
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if proc.is_infinite:
            proc.start_date = datetime.now().date()
            proc.end_date = datetime.now().date()
        else:
            if start_date: proc.start_date = start_date
            if end_date: proc.end_date = end_date
            
        proc.active_message = request.POST.get('active_message')
        # proc.closed_message eliminado
        
        roles = request.POST.getlist('roles')
        if not roles: roles = ['general']
        proc.roles = roles
        
        proc.save()
        messages.success(request, "Proceso actualizado correctamente.")
        
    except BusinessProcess.DoesNotExist:
        messages.error(request, "Proceso no encontrado.")
    except Exception as e:
        messages.error(request, f"Error al editar: {e}")
        
    return redirect('chatbot:process_manager')

# ==============================================================================
# 6. SUBIDA DE DOCUMENTACIÓN (CHATBOT MODAL)
# ==============================================================================

from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage

@csrf_exempt
@require_http_methods(["POST"])
def upload_documentation(request):
    """
    Endpoint para recibir documentación subida desde el modal del chatbot.
    Guarda el archivo en media/balcon_docs/ y retorna JSON.
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No se recibió ningún archivo.'}, status=400)
        
        uploaded_file = request.FILES['file']
        extra_details = request.POST.get('details', '')
        
        # Guardar archivo
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'balcon_docs'))
        filename = fs.save(uploaded_file.name, uploaded_file)
        file_url = fs.url(filename)
        
        # Aquí podrías guardar un registro en BD si fuera necesario
        # Por ejemplo: DocumentoEntregado.objects.create(...)
        
        logger.info(f"Archivo subido desde chatbot: {filename} | Detalles: {extra_details}")
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Archivo recibido correctamente.',
            'file_url': file_url
        })
        
    except Exception as e:
        logger.error(f"Error subiendo documentación: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)