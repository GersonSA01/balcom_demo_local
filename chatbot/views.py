import json
import re
import requests
import logging
import os
import time
import unicodedata
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from django.views.decorators.http import require_POST
import difflib
from chatbot.models import (
    SgaPersona, SgaPerfilusuario, BusinessProcess, RagDocument, 
    ChatbotRol, SgaCarrera, SgaInscripcion,
)
logger = logging.getLogger(__name__)
from django.db.models import ForeignKey

def get_dynamic_sga_roles():
    """
    Devuelve los roles del modelo y añade un rol virtual 'General'.
    """
    # 1. Roles reales de la base de datos
    roles_permitidos = {
        'inscripcion': 'Estudiante (Pregrado)',
        'profesor': 'Docente / Profesor',
        'administrativo': 'Administrativo',
        'externo': 'Usuario Externo',
    }

    roles_detectados = []

    # 2. Recorremos el modelo
    for field in SgaPerfilusuario._meta.get_fields():
        if field.name in roles_permitidos:
            roles_detectados.append({
                'id': field.name,
                'nombre': roles_permitidos[field.name]
            })
    
    # --- CAMBIO AQUÍ: Añadimos el rol virtual General ---
    roles_detectados.append({
        'id': 'general', 
        'nombre': 'General / Todos (Cualquier usuario logueado)'
    })
    # ----------------------------------------------------
    
    return sorted(roles_detectados, key=lambda x: x['nombre'])

# ==============================================================================
# 1. CONFIGURACIÓN Y CALENDARIO
# ==============================================================================



def normalize_text(text):
    if not text: return ""
    # Normaliza a minúsculas y quita tildes (NFD)
    text = text.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def get_process_response_from_db(process_name):
    try:
        # Buscamos el proceso activo
        process = BusinessProcess.objects.filter(nombre=process_name, status=True).first()
        
        if not process:
            return {"text": f"Por ahora no tengo información disponible sobre el proceso {process_name}.", "status": "error", "need_documentation": False}

        friendly_text = (
            "Hola 👋, para continuar con tu solicitud necesito que me compartas la documentación requerida:"
            f"\n{process.active_message}\n"
            "También necesitaré que me des de nuevo los detalles de tu solicitud."
        )

        if process.process_type == "informativo":
            friendly_text = process.active_message or process.business_context
            process.need_documentation = False

        base_response = {
            "text": friendly_text,
            "need_documentation": process.need_documentation,
            "source_url": process.source_url
        }
        
        return base_response 

    except Exception as e:
        logger.error(f"Error validando proceso: {e}")
        return {"text": "Error interno.", "status": "error", "need_documentation": False}
# ==============================================================================
# 2. ENDPOINTS API DE USUARIOS
# ==============================================================================

@require_POST
def create_chatbot_role(request):
    try:
        nombre = request.POST.get('nombre')
        campo_sga = request.POST.get('tipo_usuario_id')
        carreras_ids = request.POST.getlist('carreras')

        rol = ChatbotRol.objects.create(
            nombre=nombre,
            campo_sga=campo_sga
        )
        if carreras_ids:
            rol.carreras.set(carreras_ids)
            
        messages.success(request, "Rol creado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al crear rol: {str(e)}")
        
    return redirect('chatbot:document_manager')

@require_POST
def delete_chatbot_role(request, role_id):
    rol = get_object_or_404(ChatbotRol, id=role_id)
    try:
        rol.delete()
        messages.success(request, "Rol eliminado correctamente.")
    except Exception as e:
        messages.error(request, "No se pudo eliminar el rol (puede estar en uso).")
        
    return redirect('chatbot:document_manager')

@require_POST
def edit_chatbot_role(request, role_id):
    rol = get_object_or_404(ChatbotRol, id=role_id)
    
    try:
        rol.nombre = request.POST.get('nombre')
        # Si permites editar el campo SGA:
        rol.campo_sga = request.POST.get('tipo_usuario_id')
        
        carreras_ids = request.POST.getlist('carreras')
        if carreras_ids:
            rol.carreras.set(carreras_ids)
        else:
            rol.carreras.clear()
            
        rol.save()
        messages.success(request, "Rol actualizado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al editar: {str(e)}")
        
    return redirect('chatbot:document_manager')
    


# En views.py

@require_http_methods(["GET"])
def get_users_list(request):
    TARGET_CEDULA = '0940153000' 
    
    roles_configurados = get_dynamic_sga_roles()

    mapa_frontend = {
        'inscripcion': 'es_estudiante',
        'profesor': 'es_profesor',
        'administrativo': 'es_administrativo',
        'externo': 'es_externo',
        'general': 'es_general' 
    }

    data = []
    try:
        personas = SgaPersona.objects.filter(cedula=TARGET_CEDULA)
        
        if not personas.exists():
            return JsonResponse({"mensaje": "Persona no encontrada"}, status=404)

        for p in personas:
            perfiles_qs = SgaPerfilusuario.objects.filter(persona=p, status=True)
            perfiles_list = []
            
            for perf in perfiles_qs:
                perf_data = {"id": perf.id}
                roles_detectados_nombres = []

                for rol_info in roles_configurados:
                    campo_bd = rol_info['id']
                    nombre_legible = rol_info['nombre']
                    
                    if campo_bd == 'general':
                        valor = True
                    else:
                        valor = getattr(perf, campo_bd, None)
                    
                    # --- AQUÍ FALTABAN LOS DOS PUNTOS ---
                    if valor: 
                        roles_detectados_nombres.append(nombre_legible)
                        
                        key_frontend = mapa_frontend.get(campo_bd)
                        if key_frontend:
                            perf_data[key_frontend] = True
                
                perf_data["descripcion"] = " / ".join(roles_detectados_nombres) if roles_detectados_nombres else "Sin Rol Configurado"
                
                for k in mapa_frontend.values():
                    if k not in perf_data:
                        perf_data[k] = False

                perfiles_list.append(perf_data)

            data.append({
                "cedula": p.cedula,
                "nombre_completo": f"{p.nombres} {p.apellido1} {p.apellido2}".strip(),
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
        if requests.get(f"{settings.PRIVATE_GPT_API_URL}/health", timeout=5).status_code == 200:
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

        # 1. ATAJO HANDOFF (Soporte Humano)
        is_handoff_confirmation = False
        if history:
            last_msg = history[-1]
            if last_msg.get('role') == 'assistant':
                content = last_msg.get('content', '')
                if "Voy a derivar tu caso" in content or "adjunta evidencia" in content:
                    is_handoff_confirmation = True

        def event_stream():
            try:
                # --- RESPUESTA RÁPIDA HANDOFF ---
                if is_handoff_confirmation:
                    time.sleep(1.0)
                    yield json.dumps({
                        "type": "final",
                        "data": {
                            "response": "¡Listo! He derivado tu caso. ¿Necesitas algo más?",
                            "sources": [],
                            "is_function": False,
                            "action": "ANSWER",
                            "payload": {"status": "success"},
                            "offer_human_handoff": False
                        }
                    }) + "\n"
                    return 

                # --- RESPUESTA AL RECHAZO DE RAG ---
                if user_msg == "RAG_REJECTED":
                     yield json.dumps({
                        "type": "final",
                        "data": {
                            "response": "Entendido. Por favor reformula tu pregunta intentando ser más específico. 🙏",
                            "action": "ANSWER",
                            "is_function": False,
                            "sources": []
                        }
                    }) + "\n"
                     return

                # --- DETECCIÓN DE BYPASS (Confirmación del Usuario) ---
                bypass_router = False
                real_query_for_processing = user_msg
                bypass_process_name = None

                if user_msg.startswith("RAG_CONFIRMED||"):
                    parts = user_msg.split("||")
                    if len(parts) > 1:
                        real_query_for_processing = parts[1] # Usamos la query limpia/reformulada
                        bypass_router = True # Saltaremos todas las validaciones
                    
                    if len(parts) > 2:
                        bypass_process_name = parts[2]

# -------------------------------------------------------------
                # 1. DETERMINAR PERFIL Y CARRERA DEL USUARIO
                # -------------------------------------------------------------
                user_matched_role_ids = set() # Usamos un SET para evitar duplicados
                user_carrera_ids = set()

                if cedula:
                    persona = SgaPersona.objects.filter(cedula=cedula).first()
                    # Lógica para obtener el perfil activo
                    target_pid = session.get(cedula, {}).get('perfiles', [{}])[0].get('id')
                    perfil = None
                    if target_pid:
                        perfil = SgaPerfilusuario.objects.filter(id=target_pid, persona=persona, status=True).first()
                    if not perfil:
                        perfil = SgaPerfilusuario.objects.filter(persona=persona, status=True).first()

                    if perfil:
                        # Guardamos datos de sesión básicos
                        request.session['user_cedula'] = cedula
                        request.session['user_name'] = str(persona)

                        # --- LÓGICA DE MATCHING DE ROLES Y CARRERA ---
                        # 1. Obtenemos todos los roles configurados en el sistema (ChatbotRol)
                        all_system_roles = ChatbotRol.objects.filter(status=True).prefetch_related('carreras')
                        
                        # 2. Obtenemos la configuración dinámica para saber qué campos mirar en el perfil
                        # ej: [{'id': 'inscripcion', 'nombre': 'Estudiante'}, ...]
                        campos_posibles = get_dynamic_sga_roles()
                        
                        # 3. Recorremos cada Rol configurado en el Admin del Chatbot
                        for chatbot_rol in all_system_roles:
                            campo_sga_requerido = chatbot_rol.campo_sga # ej: 'inscripcion' o 'general'
                            
                            # --- NUEVA LÓGICA: ROL GENERAL ---
                            if campo_sga_requerido == 'general':
                                # Si el rol es 'general', se le asigna a CUALQUIER usuario que tenga perfil.
                                # No validamos carreras para el rol general (es global por definición).
                                user_matched_role_ids.add(chatbot_rol.id)
                                continue 
                            # ---------------------------------

                            # Lógica estándar para roles específicos (Estudiante, Profesor, etc.)
                            # Verificamos si este campo existe en el perfil del usuario
                            objeto_relacionado = getattr(perfil, campo_sga_requerido, None)

                            if objeto_relacionado:
                                # ¡El usuario tiene este rol base!
                                
                                # AHORA VALIDAMOS LA CARRERA
                                carreras_del_rol = chatbot_rol.carreras.all()
                                
                                if not carreras_del_rol.exists():
                                    # CASO A: El Rol es Genérico (sin carreras marcadas)
                                    user_matched_role_ids.add(chatbot_rol.id)
                                else:
                                    # CASO B: El Rol es Específico (tiene filtro de carreras)
                                    carrera_obj = getattr(objeto_relacionado, 'carrera', None)
                                    
                                    if carrera_obj and carrera_obj.id in [c.id for c in carreras_del_rol]:
                                        user_matched_role_ids.add(chatbot_rol.id)
                                        user_carrera_ids.add(carrera_obj.id)

                        request.session['user_roles'] = list(user_matched_role_ids)

                yield json.dumps({"type": "status", "text": "Analizando..."}) + "\n"

                # -------------------------------------------------------------
                # 2. FILTRAR DOCUMENTOS (RAG)
                # -------------------------------------------------------------
                # Solo enviamos a PrivateGPT los IDs de los documentos que el usuario PUEDE ver.
                
                # Traemos documentos con sus roles permitidos
                all_docs = RagDocument.objects.filter(status=True, is_indexed=True).prefetch_related('roles_permitidos')
                
                doc_ids_for_pgpt = [] # Lista final de IDs (nombres de archivo) para la IA
                today = datetime.now().date()

                for doc in all_docs:
                    # 1. Validación de Fechas
                    if not doc.is_infinite:
                        if doc.valid_from and today < doc.valid_from: continue
                        if doc.valid_to and today > doc.valid_to: continue

                    is_allowed = False
                    
                    # 2. Validación de Permisos
                    roles_doc = doc.roles_permitidos.all()
                    
                    if not roles_doc.exists():
                        # Si el documento no tiene roles marcados, es PÚBLICO
                        is_allowed = True
                    else:
                        # Si tiene roles, el usuario debe tener AL MENOS UNO de ellos
                        # Como ya calculamos 'user_matched_role_ids' arriba considerando carrera,
                        # aquí solo hacemos una intersección de conjuntos simple.
                        doc_roles_ids = set(r.id for r in roles_doc)
                        
                        # Intersección: ¿Tienen elementos en común?
                        if not user_matched_role_ids.isdisjoint(doc_roles_ids):
                            is_allowed = True
                    
                    # 3. Agregado final
                    if is_allowed and doc.doc_id_pgpt:
                        # PrivateGPT usa el 'file_name' o el 'doc_id' UUID para filtrar.
                        # En tu código anterior usabas 'doc.nombre'. Asegúrate que esto coincida 
                        # con lo que guardaste en PrivateGPT (normalmente el file_name).
                        doc_ids_for_pgpt.append(doc.nombre) 

                # Debug en consola para que veas qué está pasando
                print(f"DEBUG: Usuario Roles IDs: {user_matched_role_ids}")
                print(f"DEBUG: Docs enviados a IA: {doc_ids_for_pgpt}")

                # -------------------------------------------------------------
                # 3. FILTRAR PROCESOS (BusinessProcess)
                # -------------------------------------------------------------
                all_processes = BusinessProcess.objects.filter(status=True).prefetch_related('roles_permitidos', 'roles_permitidos__carreras')
                valid_process_details = []
                
                for proc in all_processes:
                    is_proc_allowed = False
                    if not proc.roles_permitidos.exists():
                        is_proc_allowed = True
                    else:
                        for rol_config in proc.roles_permitidos.all():
                            # 1. Chequeo de Tipo de Usuario (CORREGIDO: user_matched_role_ids)
                            if rol_config.id in user_matched_role_ids:
                                # 2. Chequeo de Carreras
                                carreras_del_rol = rol_config.carreras.all()
                                if not carreras_del_rol:
                                    is_proc_allowed = True; break
                                else:
                                    # CORREGIDO: user_carrera_ids
                                    if any(c.id in user_carrera_ids for c in carreras_del_rol):
                                        is_proc_allowed = True; break
                    
                    if is_proc_allowed:
                        desc = proc.business_context.replace("\n", " ").strip() if proc.business_context else "Sin descripción"
                        item_str = f'FUNCTION_NAME: "{proc.nombre}"\nSCOPE: "{desc}"\n\n'
                        valid_process_details.append(item_str)

                # =============================================================
                # A. FLUJO 1: BYPASS ROUTER (RAG CONFIRMADO)
                # =============================================================
                if bypass_router:
                    yield json.dumps({"type": "status", "text": "Consultando normativa experta..."}) + "\n"
                    
                    rag_payload = {
                        "messages": [
                            {"role": "system", "content": "RAG_EXPERT_MODE"},
                            {"role": "user", "content": real_query_for_processing}
                        ],
                        "use_context": True, 
                        # CORREGIDO: doc_ids_for_pgpt (antes doc_ids)
                        "context_filter": {"docs_ids": doc_ids_for_pgpt} if doc_ids_for_pgpt else None,
                        "stream": False
                    }
                    r_rag = requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", json=rag_payload, timeout=None)
                    
                    final_response_text = "Error consultando el conocimiento."
                    api_sources = []
                    
                    if r_rag.status_code == 200:
                        rag_resp = r_rag.json()
                        raw_rag_text = rag_resp["choices"][0]["message"]["content"]
                        api_sources = rag_resp.get("sources", [])

                        # Limpieza JSON
                        try:
                            clean_text = raw_rag_text.replace("```json", "").replace("```", "").strip()
                            if "{" in clean_text:
                                start = clean_text.find("{")
                                end = clean_text.rfind("}") + 1
                                if start != -1 and end != -1:
                                    json_data = json.loads(clean_text[start:end])
                                    first_pass = json_data.get("response", "")
                                    if isinstance(first_pass, str) and "{" in first_pass and "response" in first_pass:
                                        inner = json.loads(first_pass)
                                        final_response_text = inner.get("response", first_pass)
                                    else:
                                        final_response_text = first_pass
                                else: final_response_text = raw_rag_text
                            else: final_response_text = raw_rag_text
                        except: final_response_text = raw_rag_text

                        # 2. INYECCIÓN DEL MENSAJE CERRADO
                        if bypass_process_name and bypass_process_name != "null":
                            try:
                                # CORREGIDO: filter(nombre=...)
                                proc_obj = BusinessProcess.objects.filter(nombre=bypass_process_name, status=True).first()
                                if proc_obj:
                                    # CORREGIDO: proc_obj.nombre
                                    msg_bd = proc_obj.closed_message if (proc_obj.closed_message and proc_obj.closed_message.strip()) else f"El proceso {proc_obj.nombre} no está disponible."
                                    final_response_text = f"⚠️ **AVISO: {proc_obj.nombre}**\n{msg_bd}\n\nℹ️ **Información de la Normativa:**\n{final_response_text}"
                            except Exception as e:
                                logger.error(f"Error pegando mensaje proceso cerrado: {e}")

                    # Extracción de Sources
                    final_sources = []
                    seen = set()
                    for src in api_sources:
                        meta = src.get("document", {}).get("doc_metadata", {})
                        fname = meta.get("file_name") or "Documento"
                        if fname not in seen:
                            final_sources.append({"title": fname, "url": None})
                            seen.add(fname)

                    yield json.dumps({
                        "type": "final",
                        "data": {
                            "response": final_response_text,
                            "sources": final_sources,
                            "is_function": False, "action": "ANSWER", "payload": {}, "offer_human_handoff": False
                        }
                    }) + "\n"
                    return

# =============================================================
                # B. FLUJO 2: ROUTER NORMAL
                # =============================================================
                action = "ANSWER"
                found_process_name = None
                
                # 1. PREPARACIÓN: Incluimos [TOOLS_LIST] para activar _detect_intent en chat_service
                if valid_process_details:
                    system_instruction = "[TOOLS_LIST]\n" + "\n".join(valid_process_details) + "\n[END_TOOLS_LIST]"
                else:
                    system_instruction = "NO_TOOLS_AVAILABLE"

                payload_router = {
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": real_query_for_processing}
                    ],
                    "use_context": False, # Esto fuerza al chat_service a usar la lógica de Router
                    "stream": False
                }
                
                try:
                    # --- PETICIÓN AL ROUTER (Esta línea faltaba o estaba mal indentada) ---
                    r = requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", json=payload_router, timeout=300)
                    raw_content = r.json()["choices"][0]["message"]["content"]
                    
                    # 2. LÓGICA DE INTERPRETACIÓN BLINDADA
                    try:
                        clean_json_str = raw_content.replace("```json", "").replace("```", "").strip()
                        data_router = json.loads(clean_json_str)
                        
                        if isinstance(data_router, dict):
                            # CASO A: Respuesta procesada por ChatService (tiene 'action')
                            if "action" in data_router:
                                server_action = data_router.get("action")
                                server_func = data_router.get("function_name")
                                server_response = data_router.get("response", "")

                                if server_action == "FUNCTION":
                                    action = "FUNCTION"
                                    found_process_name = server_func
                                elif server_action == "ANSWER" and server_func == "OFF_TOPIC":
                                    action = "OFF_TOPIC"
                                elif server_action == "ANSWER" and "Hola" in server_response:
                                    action = "GREETING"
                                else:
                                    action = "ANSWER"
                            
                            # CASO B: Respuesta cruda del LLM (tiene 'classification')
                            elif "classification" in data_router:
                                cls = data_router.get("classification")
                                func = data_router.get("function_name")
                                
                                if cls == "GREETING":
                                    action = "GREETING"
                                elif cls == "OFF_TOPIC":
                                    action = "OFF_TOPIC"
                                elif cls == "FUNCTION":
                                    action = "FUNCTION"
                                    found_process_name = func
                                else:
                                    action = "ANSWER" # RAG
                            
                            else:
                                action = "ANSWER"

                    except Exception as e:
                        logger.error(f"Error parseando router JSON: {e}")
                        action = "ANSWER"

                except Exception as e:
                    logger.error(f"Error router connection: {e}")
                    action = "ANSWER"
                    
                # DECISIÓN REFORMULACIÓN Y EJECUCIÓN
                # -------------------------------------------------------------
                must_reformulate = False
                detected_proc_for_frontend = None 
                
                # --- CORRECCIÓN: Inicializar variables por defecto AQUÍ ---
                final_sources = [] 
                final_response_text = ""
                is_function = False
                payload_data = {}
                # ----------------------------------------------------------

                if action == "GREETING":
                    must_reformulate = False
                    final_response_text = "¡Hola! 👋 Soy el asistente virtual de la UNEMI. ¿En qué puedo ayudarte hoy?"
                
                elif action == "OFF_TOPIC":
                    must_reformulate = False
                    final_response_text = "Lo siento, solo estoy entrenado para responder dudas académicas y administrativas de la UNEMI. No puedo ayudarte con eso."

                elif action == "ANSWER":
                    must_reformulate = True
                    
                elif action == "FUNCTION":
                    if found_process_name == "HUMAN_HANDOFF":
                        must_reformulate = False 
                    else:
                        # Validación de vigencia del proceso
                        proc = BusinessProcess.objects.filter(nombre=found_process_name, status=True).first()
                        
                        if proc:
                            today = datetime.now().date()
                            is_active = True
                            if not proc.is_infinite:
                                if not (proc.start_date <= today <= proc.end_date):
                                    is_active = False
                            
                            if not is_active:
                                must_reformulate = True
                                detected_proc_for_frontend = found_process_name
                        else:
                            must_reformulate = True

                # -------------------------------------------------------------
                # EJECUCIÓN 1: REFORMULACIÓN (SI ES NECESARIO)
                # -------------------------------------------------------------
                if must_reformulate:
                    yield json.dumps({"type": "status", "text": "Analizando consulta..."}) + "\n"
                    
                    reform_payload = {
                        "messages": [{"role": "system", "content": "REFORMULATE_QUERY_MODE"}, {"role": "user", "content": user_msg}],
                        "stream": False, "temperature": 0.1, "use_context": False
                    }
                    reformulated_q = user_msg
                    try:
                        r_ref = requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", json=reform_payload, timeout=None)
                        if r_ref.status_code == 200:
                            content = r_ref.json()["choices"][0]["message"]["content"]
                            clean_content = content.strip().replace('"', '').replace("Here is the reformulated query:", "")
                            if len(clean_content) > 5: reformulated_q = clean_content
                    except: pass

                    msg_text = f"Entendí: {reformulated_q}. ¿Es correcto?"
                    
                    yield json.dumps({
                        "type": "final",
                        "data": {
                            "response": msg_text,
                            "action": "RAG_CONFIRMATION", 
                            "payload": {
                                "reformulated_query": reformulated_q,
                                "detected_process": detected_proc_for_frontend
                            },
                            "sources": [], "is_function": False, "offer_human_handoff": False
                        }
                    }) + "\n"
                    return

                # -------------------------------------------------------------
                # EJECUCIÓN 2: RESPUESTA DIRECTA (SI NO HUBO REFORMULACIÓN)
                # -------------------------------------------------------------
                elif action == "FUNCTION": 
                    if found_process_name == "HUMAN_HANDOFF":
                         final_response_text = "Voy a derivar tu caso con mis compañeros humanos..."
                         is_function = True
                         payload_data = {"status": "success", "need_documentation": True, "upload_optional": True}
                    else:
                        res = get_process_response_from_db(found_process_name)
                        final_response_text = res["text"]
                        is_function = True
                        payload_data = res
                        if res.get("source_url"):
                             # AQUI FALLABA ANTES: final_sources ahora ya existe como []
                             final_sources.append({"title": f"{found_process_name}", "url": res.get("source_url")})

                # RESPUESTA FINAL
                yield json.dumps({
                    "type": "final",
                    "data": {
                        "response": final_response_text,
                        "sources": final_sources,
                        "is_function": is_function,        
                        "action": action,                  
                        "payload": payload_data,            
                        "offer_human_handoff": False
                    }
                }) + "\n"

            except Exception as e:
                logger.error(f"Error stream: {e}")
                yield json.dumps({"type": "error", "text": "Error interno."}) + "\n"

        return StreamingHttpResponse(event_stream(), content_type='application/x-ndjson')
# ==============================================================================
# 4. GESTIÓN DOCUMENTAL
# ==============================================================================

def document_manager(request):
    # 1. Documentos (Igual que antes)
    documents = RagDocument.objects.filter(status=True).order_by('-fecha_creacion')
    
    try:
        r = requests.get(f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/list", timeout=3)
        if r.status_code == 200:
            pgpt_data = r.json().get('data', [])
            real_pgpt_ids = {item['doc_id'] for item in pgpt_data}
            docs_changed = False
            for doc in documents:
                if doc.doc_id_pgpt:
                    if doc.doc_id_pgpt not in real_pgpt_ids and doc.is_indexed:
                        doc.is_indexed = False; doc.save(); docs_changed = True
                    elif doc.doc_id_pgpt in real_pgpt_ids and not doc.is_indexed:
                        doc.is_indexed = True; doc.save(); docs_changed = True
            if docs_changed: documents = RagDocument.objects.filter(status=True).order_by('-fecha_creacion')
    except: pass

    # 2. CONSULTAS A BASE DE DATOS (LO NUEVO)
    
    # 1. Roles ya configurados (ej: "Estudiantes Derecho")
    chatbot_roles = ChatbotRol.objects.filter(status=True).prefetch_related('carreras')    # 2. Tipos Base (ej: "Estudiante", "Profesor") -> ESTO VIENE DE BDD AHORA
    tipos_catalogo = get_dynamic_sga_roles()
    
    # 3. Carreras (ej: "Ing. Software") -> ESTO VIENE DE BDD
    carreras_reales = SgaCarrera.objects.all().values('id', 'nombre').order_by('nombre')
    
    # 3. Procesos
    documents = RagDocument.objects.filter(status=True).order_by('-fecha_creacion')
    processes = BusinessProcess.objects.filter(status=True).order_by('-fecha_creacion')

    return render(request, 'chatbot/document_manager.html', {
        'documents': documents,
        'processes': processes,
        'chatbot_roles': chatbot_roles,
        'tipos_base': tipos_catalogo,  # <--- Pasamos la lista dinámica
        'carreras_list': carreras_reales,
    })

def upload_document(request):
    if request.method == 'POST':
        files = request.FILES.getlist('file')
        
        # Recoger datos del formulario
        # AHORA 'roles' SERÁ UNA LISTA DE IDs (números), NO DE STRINGS
        role_ids = request.POST.getlist('roles') 
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
                    # roles=roles,  <--- ELIMINA ESTO DEL CONSTRUCTOR
                    is_infinite=is_inf,
                    valid_from=v_from,
                    valid_to=v_to,
                    is_indexed=False 
                )
                doc_db.save(request) # Pasamos request para que ModeloBase guarde el usuario_creacion
                
                # ASIGNAR LA RELACIÓN MANY-TO-MANY DESPUÉS DE GUARDAR
                if role_ids:
                    doc_db.roles_permitidos.set(role_ids) # Usamos .set() con los IDs

                # 2. ENVIAR A PRIVATE-GPT (Sincronización)
                try:
                    # Abrimos el archivo que Django ya guardó en disco
                    with doc_db.archivo.open('rb') as local_file:
                        r = requests.post(
                            ingest_url, 
                            files={'file': (doc_db.nombre, local_file, 'application/pdf')}, # Ajustar content-type si varía
                            timeout=None
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
                                "roles": role_ids, "is_infinite": is_inf, 
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
            role_ids = request.POST.getlist('roles') # IDs de ChatbotRol
            is_inf = request.POST.get('is_infinite') == 'on'
            v_from = request.POST.get('valid_from') or None
            v_to = request.POST.get('valid_to') or None

            # 2. Actualizar BD Local
            doc = RagDocument.objects.get(id=doc_id)
            
            # Actualizamos la relación M2M
            doc.roles_permitidos.set(role_ids) 
            
            doc.is_infinite = is_inf
            doc.valid_from = v_from
            doc.valid_to = v_to
            doc.save(request) # Pasa request para auditoría ModeloBase

            # 3. Sincronizar con PrivateGPT
            if doc.doc_id_pgpt:
                payload = {
                    "roles": role_ids, 
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
        # 1. Recuperar variables del formulario
        name_input = request.POST.get('name')
        process_type = request.POST.get('process_type', 'informativo')
        source_url = request.POST.get('source_url')
        business_context = request.POST.get('business_context')
        active_msg = request.POST.get('active_message')
        
        # Checkboxes
        # En HTML los checkbox envían 'on' si están marcados, o nada si no.
        is_infinite = request.POST.get('is_infinite') == 'on'
        
        # Documentación solo si es operativo
        need_documentation = False
        if process_type == 'operativo':
            need_documentation = request.POST.get('need_documentation') == 'on'

        # Fechas
        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None
        
        # Si es infinito, ponemos fecha de hoy por defecto para que no falle la BD (aunque no se usen)
        if is_infinite:
            now = datetime.now().date()
            start_date = now
            end_date = now
            
        # Mensaje de cerrado
        has_closed = request.POST.get('has_closed_message') == 'on'
        closed_msg = request.POST.get('closed_message') if has_closed else None
        
        # Roles
        role_ids = request.POST.getlist('roles')

        # 2. Crear el objeto
        proc = BusinessProcess.objects.create(
            nombre=name_input,
            process_type=process_type,
            source_url=source_url,
            is_infinite=is_infinite,
            business_context=business_context,
            closed_message=closed_msg,
            need_documentation=need_documentation, 
            start_date=start_date,
            end_date=end_date,
            active_message=active_msg,
            status=True
        )
        
        # 3. Asignar relación ManyToMany
        if role_ids:
            proc.roles_permitidos.set(role_ids)
            
        messages.success(request, "Proceso creado correctamente.")
        
    except Exception as e:
        messages.error(request, f"Error al crear: {e}")
        logger.error(f"Error create_process: {e}")
        
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
        
        # CORRECCIÓN: Usar .nombre
        proc.nombre = request.POST.get('name') 
        
        proc.business_context = request.POST.get('business_context')
        proc.process_type = request.POST.get('process_type', proc.process_type)
        proc.source_url = request.POST.get('source_url') or None
        
        # Checkbox: Is Infinite
        raw_infinite = request.POST.get('is_infinite')
        proc.is_infinite = raw_infinite in ['on', 'true', '1', 'True']
        
        # Checkbox: Need Documentation
        if proc.process_type == "operativo":
            raw_docs = request.POST.get('need_documentation')
            proc.need_documentation = raw_docs in ['on', 'true', '1', 'True']
        else:
            proc.need_documentation = False
        
        # Fechas
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if proc.is_infinite:
            proc.start_date = datetime.now().date()
            proc.end_date = datetime.now().date()
        else:
            if start_date: proc.start_date = start_date
            if end_date: proc.end_date = end_date
            
        proc.active_message = request.POST.get('active_message')
        
        # --- LÓGICA DE MENSAJE CERRADO ---
        has_closed_msg = request.POST.get('has_closed_message') == 'on'
        if has_closed_msg:
            # Guardamos lo que venga en el textarea
            proc.closed_message = request.POST.get('closed_message')
        else:
            # Si desmarcó el checkbox, borramos el mensaje anterior
            proc.closed_message = None
        # ---------------------------------
        
        role_ids = request.POST.getlist('roles')
        proc.roles_permitidos.set(role_ids)
        
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
        
        logger.info(f"Archivo subido desde chatbot: {filename} | Detalles: {extra_details}")

        # --- SIMULACIÓN DE PROCESAMIENTO ---
        time.sleep(2) # Simula un pequeño retraso de procesamiento

        # Definimos el mensaje que el Chatbot mostrará al usuario
        mensaje_para_usuario = (
            "Perfecto, he recibido tu documento correctamente. "
            "He derivado tu solicitud a mis compañeros humanos, por favor "
            "esté atento a su correo institucional para futuras notificaciones. "
            "¿Hay algo mas en que te pueda ayudar?"
        )

        return JsonResponse({
            'status': 'success', 
            'message': 'Archivo recibido correctamente.',
            'file_url': file_url,
            'ai_response': mensaje_para_usuario # <--- Enviamos el texto desde aquí
        })
        
    except Exception as e:
        logger.error(f"Error subiendo documentación: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)