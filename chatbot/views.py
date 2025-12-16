import json
import re
import requests
import logging
import os
import time
import unicodedata
from django.utils import timezone
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
    ChatbotRol, SgaCarrera, SgaInscripcion, BusinessProcessType,
    SgaMatricula, SgaInscripcion, BalconProceso, BalconCategoria, 
    BalconCategoriaCoordinaciones, SgaCoordinacionCarrera
)
logger = logging.getLogger(__name__)
from django.db.models import ForeignKey, Case, When, Value, IntegerField

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
    
    return sorted(roles_detectados, key=lambda x: (0 if x['id'] == 'general' else 1, x['nombre']))

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
        process = BusinessProcess.objects.filter(nombre=process_name, status=True).select_related("process_type").first()

        if not process:
            return {
                "text": f"Por ahora no tengo información disponible sobre el proceso {process_name}.",
                "status": "error",
                "need_documentation": False
            }

        # Mensaje base (para procesos operativos que requieren documentación)
        friendly_text = (
            "Hola 👋, para continuar con tu solicitud necesito que me compartas la documentación requerida:"
            f"\n{process.active_message}\n"
            "También necesitaré que me des de nuevo los detalles de tu solicitud."
        )

        # ✅ CORRECCIÓN: process_type es FK, así que se compara por el nombre del tipo
        tipo_nombre = (process.process_type.nombre or "").strip().lower() if process.process_type else ""

        if tipo_nombre == "informativo":
            # Para procesos informativos, NO pedimos documentación
            friendly_text = (process.active_message or process.business_context or "").strip()
            process.need_documentation = False

        base_response = {
            "text": friendly_text if friendly_text else "Por ahora no tengo un mensaje configurado para este proceso.",
            "need_documentation": bool(process.need_documentation),
            "source_url": process.source_url
        }

        return base_response

    except Exception as e:
        logger.error(f"Error validando proceso: {e}")
        return {"text": "Error interno.", "status": "error", "need_documentation": False}

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
    
@require_http_methods(["GET"])
def get_users_list(request):
    TARGET_CEDULAS = ['0940153000', '0706191558'] 
    
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
        personas = SgaPersona.objects.filter(cedula__in=TARGET_CEDULAS)
        
        if not personas.exists():
            # Si no hay personas, devolvemos lista vacía o mensaje, según prefieras
            pass 

        for p in personas:
            perfiles_qs = SgaPerfilusuario.objects.filter(persona=p, status=True)
            perfiles_list = []
            
            for perf in perfiles_qs:
                perf_data = {"id": perf.id}
                roles_detectados_nombres = []

                # 1. Nombre de Carrera
                nombre_carrera = ""
                # Verificamos si tiene inscripción y carrera asociada
                if perf.inscripcion and getattr(perf.inscripcion, 'carrera', None):
                    nombre_carrera = perf.inscripcion.carrera.nombre
                
                perf_data["carrera_nombre"] = nombre_carrera

                # 2. Detectar Roles
                for rol_info in roles_configurados:
                    campo_bd = rol_info['id']
                    nombre_legible = rol_info['nombre']
                    
                    if campo_bd == 'general':
                        valor = True
                    else:
                        valor = getattr(perf, campo_bd, None)
                    
                    if valor: 
                        roles_detectados_nombres.append(nombre_legible)
                        key_frontend = mapa_frontend.get(campo_bd)
                        if key_frontend:
                            perf_data[key_frontend] = True
                
                perf_data["descripcion"] = " / ".join(roles_detectados_nombres) if roles_detectados_nombres else "Sin Rol Configurado"
                
                for k in mapa_frontend.values():
                    if k not in perf_data:
                        perf_data[k] = False

                # ==========================================================
                # 3. LÓGICA DE PERIODOS (CORREGIDA)
                # ==========================================================
                perf_data["periodos"] = []

                if perf.inscripcion:
                    try:
                        # CORRECCIÓN AQUÍ:
                        # Cambiamos 'status=True' por 'retiradomatricula=False'
                        matriculas = SgaMatricula.objects.filter(
                            inscripcion=perf.inscripcion,
                            retiradomatricula=False 
                        ).select_related('nivel__periodo')

                        periodos_dict = {}

                        for m in matriculas:
                            # Validar que existan relaciones
                            if m.nivel and m.nivel.periodo:
                                per = m.nivel.periodo
                                if per.id not in periodos_dict:
                                    periodos_dict[per.id] = {
                                        "id": per.id,
                                        "nombre": per.nombre,
                                        "activo": per.activo,
                                        "inicio": per.inicio 
                                    }
                        
                        lista_periodos = list(periodos_dict.values())
                        # Ordenar por fecha inicio descendente
                        lista_periodos.sort(key=lambda x: x['inicio'], reverse=True)

                        perf_data["periodos"] = lista_periodos
                    
                    except Exception as ex_periodos:
                        # Log detallado del error para depurar si vuelve a pasar
                        logger.error(f"Error obteniendo periodos para perfil {perf.id}: {ex_periodos}")
                
                # ==========================================================

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




def get_servicios_para_estudiante(django_user):
    """
    Retorna un diccionario estructurado con las categorías y procesos del Balcón
    disponibles para el estudiante basado en su Coordinación (Facultad).
    """
    response_data = {
        "estudiante": None,
        "coordinacion": None,
        "categorias": []
    }

    try:
        # 1. Obtener Persona ligada al usuario logueado
        persona = SgaPersona.objects.filter(usuario=django_user).first()
        if not persona:
            print("El usuario no tiene una Persona asociada en SGA.")
            return response_data

        # 2. Obtener la Inscripción ACTIVA para saber su carrera y coordinación
        # Nota: Un estudiante podría tener más de una inscripción, tomamos la primera activa.
        inscripcion = SgaInscripcion.objects.filter(
            persona=persona, 
            activo=True
        ).select_related('carrera').first()

        if not inscripcion:
            print("El usuario no tiene inscripción activa.")
            return response_data

        # Datos básicos para el frontend
        rel = SgaCoordinacionCarrera.objects.filter(
            carrera=inscripcion.carrera
        ).select_related('coordinacion').first()

        if not rel or not rel.coordinacion:
            print("No se pudo determinar la coordinación de la carrera del estudiante.")
            return response_data

        coordinacion_estudiante = rel.coordinacion
        response_data["estudiante"] = f"{persona.nombres} {persona.apellido1}"
        response_data["coordinacion"] = coordinacion_estudiante.nombre

        # 3. Identificar Categorías permitidas para esta Coordinación
        # Usamos la tabla intermedia 'BalconCategoriaCoordinaciones'
        categorias_permitidas_ids = BalconCategoriaCoordinaciones.objects.filter(
            coordinacion=coordinacion_estudiante
        ).values_list('categoria_id', flat=True)

        # 4. Traer las Categorías con sus Procesos activos
        categorias = BalconCategoria.objects.filter(
            id__in=categorias_permitidas_ids,
            estado=True
        )

        for cat in categorias:
            # Buscar procesos activos de esta categoría
            procesos = BalconProceso.objects.filter(
                categoria=cat,
                activo=True
            ).select_related('tipo')

            lista_procesos = []
            for proc in procesos:
                lista_procesos.append({
                    "id": proc.id,
                    "nombre": proc.descripcion,
                    "tipo": proc.tipo.descripcion if proc.tipo else "General",
                    "tiempo_estimado": proc.tiempoestimado
                })

            # Solo agregamos la categoría si tiene procesos disponibles
            if lista_procesos:
                response_data["categorias"].append({
                    "id": cat.id,
                    "nombre": cat.descripcion,
                    "procesos": lista_procesos
                })

    except Exception as e:
        print(f"Error obteniendo servicios: {e}")

    return response_data


def api_get_servicios_estudiante(request):
    # Validamos por Cédula (que es lo que tiene el SessionData del frontend)
    target_cedula = request.GET.get('cedula') 
    
    if not target_cedula:
        # Fallback por si envían user_id (retrocompatibilidad)
        target_user_id = request.GET.get('user_id')
        if target_user_id:
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=target_user_id)
                return JsonResponse(get_servicios_para_estudiante(user))
            except Exception:
                pass
        return JsonResponse({'error': 'No cedula provided'}, status=400)

    try:
        # Buscamos la Persona por Cédula
        persona = SgaPersona.objects.filter(cedula=target_cedula).first()
        if not persona:
             return JsonResponse({'categorias': [], 'message': 'Persona no encontrada'})
             
        # Si la persona existe, necesitamos su usuario de Django para reusar la función get_servicios_para_estudiante,
        # O (mejor aún) refactorizamos get_servicios... para usar persona, pero por ahora mantengamos la firma.
        if persona.usuario:
            data = get_servicios_para_estudiante(persona.usuario)
        else:
            # Caso raro: Persona sin usuario AuthUser. Intentamos simular.
            # Como get_servicios_para_estudiante busca la persona por usuario, aquí fallaría.
            # Haremos un pequeño "hack" o refactor rápido si fuera necesario. 
            # Pero para no tocar get_servicios_para_estudiante, asumimos que tiene usuario.
            return JsonResponse({'categorias': [], 'message': 'Persona sin usuario vinculado'})

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        
# ==============================================================================
# 3. CLASE PRINCIPAL DEL CHATBOT (LÓGICA RAG + PROCESOS)
# ==============================================================================


class ChatView(APIView):
    
    def post(self, request):
        if not request.data: return JsonResponse({"error": "Empty"}, status=400)
        
        # DEBUG: Incoming JSON
        print(f"\nDEBUG: INCOMING REQUEST BODY:\n{json.dumps(request.data, indent=2, ensure_ascii=False)}\n")

        
        # 1. Obtener datos del Request
        user_msg = request.data.get('message', '')
        history = request.data.get('history', [])
        
        # --- NEW: Explicit handoff state sent by frontend (Option A)
        handoff_mode = bool(request.data.get('handoff_mode', False))
        
        # Lógica consolidada:
        is_handoff_confirmation = handoff_mode

        # (Opcional) Mantener compatibilidad con texto antiguo por si acaso, 
        # pero el booleano tiene prioridad absoluta.
        if not is_handoff_confirmation and user_msg:
             # Solo si NO vino el booleano, miramos el texto (fallback)
             trigger_phrases = ["sí, contactar a un humano", "contactar a un humano"]
             if any(phrase in user_msg.lower() for phrase in trigger_phrases):
                 is_handoff_confirmation = True
        # --- PARSEO DE SESIÓN (CRÍTICO PARA SQL) ---
        raw_session = request.data.get('session_data', {})
        cedula = None
        perfil_id = None
        periodo_id = None
        
        if raw_session:
            try:
                # El formato es { "CEDULA": { perfiles: [...], periodo_id: "..." } }
                cedula = list(raw_session.keys())[0]
                user_data = raw_session[cedula]
                periodo_id = user_data.get('periodo_id')
                
                # Obtener el ID del perfil seleccionado (el primero de la lista)
                perfiles = user_data.get('perfiles', [])
                if perfiles and len(perfiles) > 0:
                    perfil_id = perfiles[0].get('id')
            except Exception as e:
                logger.error(f"Error parseando sesión: {e}")

        # -------------------------------------------

        # (Lógica de Handoff movida al inicio del método)

        def event_stream():
            try:
                # =============================================================
                # 0. DEFINICIÓN DE FUNCIÓN RAG REUTILIZABLE (CORREGIDA)
                # =============================================================
                
                def execute_rag(query_text, allowed_ids=None, original_query=None, forced_intro_text=None):
                    """
                    Ejecuta RAG enviando solo DATOS al servicio.
                    El servicio se encarga de las instrucciones mediante RAG_EXPERT_MODE.
                    """
                    yield json.dumps({"type": "status", "text": "Consultando normativa institucional..."}) + "\n"

                    # 1. Bandera para activar el RAG_EXPERT_PROMPT en chat_service.py
                    messages_payload = [{"role": "system", "content": "RAG_EXPERT_MODE"}]
                    
                    # 2. Construcción limpia del mensaje del usuario
                    # NO agregamos instrucciones aquí. Solo contexto.
                    if original_query and original_query != query_text:
                        # Concatenamos para que la búsqueda vectorial tenga palabras clave (query_text)
                        # pero el LLM tenga el contexto emocional/completo (original_query).
                        # Send the ORIGINAL user query as chat history (so the LLM can preserve intent),
                        # but use the optimized query as the *last* user message so retrieval embeds the right text.
                        if original_query:
                            messages_payload.append({"role": "user", "content": f"CONSULTA DEL USUARIO: {original_query}"})
                        messages_payload.append({"role": "user", "content": (query_text or original_query)})

                        # NOTE: The last user message is what PrivateGPT/LlamaIndex will embed & retrieve with.
# B. PREPARAR FILTRO (White List)
                    context_filter_payload = None
                    if allowed_ids and len(allowed_ids) > 0:
                        context_filter_payload = {"docs_ids": [str(x) for x in allowed_ids]}

                    rag_payload = {
                        "messages": messages_payload,
                        "use_context": True, 
                        "stream": False,
                        "context_filter": context_filter_payload
                    }

                    final_response_text = "Lo siento, no pude obtener información normativa..."
                    final_sources = []
                    
                    try:
                        print(f"🌐 RAG Request (Filter count: {len(allowed_ids) if allowed_ids else 0})")
                        r_rag = requests.post(
                            f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", 
                            json=rag_payload, 
                            timeout=None
                        )
                        
                        if r_rag.status_code == 200:
                            rag_resp = r_rag.json()
                            raw_rag_text = rag_resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                            
                            # --- PARSEO DEL JSON (robusto) ---
                            try:
                                clean_text = raw_rag_text.strip().replace("```json", "").replace("```", "").strip()
                                try:
                                    data_json = json.loads(clean_text)
                                except Exception:
                                    # Si llegan DOS JSON concatenados (p.ej. por modo refine), tomamos el ÚLTIMO objeto.
                                    last_open = clean_text.rfind("{")
                                    last_close = clean_text.rfind("}")
                                    candidate = clean_text
                                    if last_open != -1 and last_close != -1 and last_close > last_open:
                                        candidate = clean_text[last_open:last_close + 1].strip()
                                    data_json = json.loads(candidate)
                                final_response_text = data_json.get("response", raw_rag_text)
                                answer_found = data_json.get("answer_found", True)
                                if isinstance(answer_found, str):
                                    answer_found = answer_found.lower() == "true"
                                raw_ids = data_json.get("source_ids", [])
                                cited_db_ids = [int(x) for x in raw_ids if str(x).isdigit()]
                            except Exception:
                                # Fallback simple si el JSON falla
                                final_response_text = raw_rag_text
                                cited_db_ids = []
                                answer_found = False

                            if not answer_found:
                                final_response_text = "Lo siento, en los documentos consultados no encontré información específica. ¿Deseas que te contacte con mis compañeros humanos?"
                                cited_db_ids = []

                            # --- LÓGICA DE FUENTES MEJORADA (FALLBACK) ---
                            seen_ids = set()

                            # 1. Intentar buscar por ID en BD Local (Lo ideal)
                            if cited_db_ids:
                                docs_from_db = RagDocument.objects.filter(id__in=cited_db_ids)
                                for doc in docs_from_db:
                                    full_url = request.build_absolute_uri(doc.archivo.url) if doc.archivo else None
                                    final_sources.append({"title": doc.nombre, "url": full_url})
                                    seen_ids.add(doc.id)

                            # 2. Fallback: Si BD vacía, usar metadata directa de la IA (Para evitar sources: [])
                            if not final_sources: 
                                api_sources = rag_resp.get("sources", [])
                                for src in api_sources:
                                    meta = src.get("document", {}).get("doc_metadata", {})
                                    # Intentar sacar nombre del archivo
                                    fname = meta.get("file_name") or meta.get("file_name_") or "Documento Normativo"
                                    # Intentar sacar URL si la guardaste en metadata, si no, null
                                    furl = meta.get("access_url") 
                                    
                                    # Evitamos duplicados por nombre si ya procesamos IDs
                                    if fname not in [s["title"] for s in final_sources]:
                                        final_sources.append({"title": fname, "url": furl})

                    except Exception as e:
                        logger.error(f"Error en RAG request: {e}")
                    
                    # Inyección de intro forzada (para procesos cerrados)
                    if forced_intro_text:
                        final_response_text = f"{forced_intro_text}\n\n{final_response_text}"

                    rag_response_payload = {
                        "type": "final",
                        "data": {
                            "response": final_response_text,
                            "sources": final_sources, 
                            "is_function": False,
                            "action": "ANSWER", 
                            "offer_human_handoff": not answer_found if 'answer_found' in locals() else False
                        }
                    }
                    yield json.dumps(rag_response_payload) + "\n" 
                # =============================================================
                # A. HANDOFF INMEDIATO
                # =============================================================
                if is_handoff_confirmation:
                    # NO LLAMAMOS A LA IA NI AL ROUTER.
                    # Respondemos directo con la estructura FUNCTION para abrir el modal.
                    
                    time.sleep(0.5) # Pequeña pausa UX
                    
                    payload_data = {
                        "status": "success", 
                        "need_documentation": True, 
                        "upload_optional": True, 
                        "handoff_mode": True
                    }
                    
                    msg_text = "Entendido. Para derivarte con mis compañeros, por favor descríbeme de nuevo tu caso y adjunta evidencia si es necesario."

                    yield json.dumps({
                        "type": "final",
                        "data": {
                            "response": msg_text,
                            "sources": [],
                            "is_function": True,      # <--- ESTO ABRE EL MODAL
                            "action": "FUNCTION",
                            "payload": payload_data,
                            "offer_human_handoff": False
                        }
                    }) + "\n"
                    return # <--- IMPORTANTE: Return para salir y no ejecutar nada más 

                # =============================================================
                # A. LIMPIEZA: ELIMINAMOS EL BLOQUE DE "RAG_REJECTED" Y "CONFIRMED"
                # =============================================================
                # Antes verificábamos si user_msg empezaba con RAG_CONFIRMED. 
                # AHORA YA NO. El mensaje siempre es "nuevo" para nosotros.
                real_query_for_processing = user_msg

# --              -----------------------------------------------------------
                # 1. DETERMINAR PERFIL Y CARRERA DEL USUARIO
                # -------------------------------------------------------------
                user_matched_role_ids = set() # Usamos un SET para evitar duplicados
                user_carrera_ids = set()

                if cedula:
                    persona = SgaPersona.objects.filter(cedula=cedula).first()
                    # Lógica para obtener el perfil activo
                    target_pid = raw_session.get(cedula, {}).get('perfiles', [{}])[0].get('id')
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

                        request.session.save()

                        request.session.modified = False

                yield json.dumps({"type": "status", "text": "Analizando..."}) + "\n"

                # -------------------------------------------------------------
                # 2. FILTRAR DOCUMENTOS (RAG)
                # -------------------------------------------------------------
                # Solo enviamos a PrivateGPT los IDs de los documentos que el usuario PUEDE ver.
                
                # Traemos documentos con sus roles permitidos
                all_docs = RagDocument.objects.filter(
                    status=True, 
                    is_indexed=True
                ).prefetch_related(
                    'roles_permitidos', 
                    'roles_permitidos__carreras'
                )
                
                doc_ids_for_pgpt = [] 
                debug_docs_log = [] # <--- Lista para guardar info detallada
                
                today = timezone.now().date()

                for doc in all_docs:
                    # 1. Validación de Fechas
                    if not doc.is_infinite:
                        if doc.valid_from and today < doc.valid_from: continue
                        if doc.valid_to and today > doc.valid_to: continue

                    is_allowed = False
                    matched_reason = "" # <--- Para saber por qué pasó
                    
                    roles_doc = doc.roles_permitidos.all()
                    
                    if not roles_doc.exists():
                        is_allowed = True
                        matched_reason = "PÚBLICO (Sin roles)"
                    else:
                        for rol_config in roles_doc:
                            # A. ¿Usuario tiene Rol Base?
                            if rol_config.id in user_matched_role_ids:
                                
                                # B. ¿Rol tiene restricción de Carreras?
                                carreras_del_rol = rol_config.carreras.all()
                                
                                if not carreras_del_rol.exists():
                                    is_allowed = True
                                    matched_reason = f"ROL: {rol_config.nombre} (Global)"
                                    break 
                                else:
                                    if any(c.id in user_carrera_ids for c in carreras_del_rol):
                                        is_allowed = True
                                        matched_reason = f"ROL: {rol_config.nombre} (Carrera Match)"
                                        break
                                    # else: pass (Tiene rol base pero falla carrera)

                    # 3. Agregado final
                    if is_allowed and doc.doc_id_pgpt:
                        doc_ids_for_pgpt.append(str(doc.id))
                        # Guardamos datos bonitos para el log
                        debug_docs_log.append(f"  ✅ [ID: {doc.id}] {doc.nombre}  --->  {matched_reason}")

                # --- IMPRESIÓN TIPO LISTA ---
                print(f"\nDEBUG: === 📂 DOCUMENTOS AUTORIZADOS ({len(debug_docs_log)}) ===")
                if debug_docs_log:
                    for line in debug_docs_log:
                        print(line)
                else:
                    print("  ❌ Ningún documento autorizado para este perfil.")
                print("DEBUG: ===============================================\n")
                # -------------------------------------------------------------
                # 3. FILTRAR PROCESOS (BusinessProcess)
                # -------------------------------------------------------------
                all_processes = BusinessProcess.objects.filter(status=True).prefetch_related('roles_permitidos', 'roles_permitidos__carreras')
                valid_process_details = []
                
                for proc in all_processes:
                    print(f"DEBUG: Analizando proceso '{proc.nombre}' (ID: {proc.id})") # DEBUG
                    is_proc_allowed = False
                    if not proc.roles_permitidos.exists():
                        print(f"  -> Permitido: Publico (sin roles)") # DEBUG
                        is_proc_allowed = True
                    else:
                        print(f"  -> Requiere roles: {[r.nombre for r in proc.roles_permitidos.all()]}") # DEBUG
                        for rol_config in proc.roles_permitidos.all():
                            # 1. Chequeo de Tipo de Usuario (CORREGIDO: user_matched_role_ids)
                            if rol_config.id in user_matched_role_ids:
                                print(f"    -> MATCH ROL: {rol_config.nombre}") # DEBUG
                                # 2. Chequeo de Carreras
                                carreras_del_rol = rol_config.carreras.all()
                                if not carreras_del_rol:
                                    print(f"      -> OK: Rol sin restricción de carrera") # DEBUG
                                    is_proc_allowed = True; break
                                else:
                                    # CORREGIDO: user_carrera_ids
                                    if any(c.id in user_carrera_ids for c in carreras_del_rol):
                                        print(f"      -> MATCH CARRERA OK") # DEBUG
                                        is_proc_allowed = True; break
                                    else:
                                        print(f"      -> FALLO CARRERA: Necesita carrera del rol, usuario tiene {user_carrera_ids}") # DEBUG
                            else:
                                pass 
                                # print(f"    -> NO MATCH ROL: {rol_config.nombre}") # DEBUG (Opcional, muy verboso)
                    
                    # NUEVA LÓGICA DE FECHAS (AGREGADA)
                    if is_proc_allowed:
                         is_active_date = True
                         if not proc.is_infinite:
                            # Asegurarse que today exista (ya se definió arriba, pero por seguridad)
                            # today = timezone.now().date() 
                            if not (proc.start_date <= today <= proc.end_date):
                                is_active_date = False
                                print(f"      -> FECHA: INACTIVO (fuera de rango: {proc.start_date} - {proc.end_date})") # DEBUG
                            else:
                                print(f"      -> FECHA: ACTIVO ({proc.start_date} - {proc.end_date})") # DEBUG
                         else:
                             print(f"      -> FECHA: ACTIVO (Infinito)") # DEBUG
                    
                    final_status_log = "DENEGADO"
                    if is_proc_allowed:
                        if is_active_date:
                            final_status_log = "PERMITIDO (ACTIVO)"
                        else:
                            final_status_log = "PERMITIDO (INACTIVO - Para mensaje de cierre)"

                    print(f"  -> Resultado Final: {final_status_log}") # DEBUG

                    if is_proc_allowed:
                        desc = proc.business_context.replace("\n", " ").strip() if proc.business_context else "Sin descripción"
                        valid_process_details.append(f'FUNCTION_NAME: "{proc.nombre}"\nSCOPE: "{desc}"\n\n')
                
                valid_process_details.append(
                    'FUNCTION_NAME: "HUMAN_HANDOFF"\n'
                    'SCOPE: "Use when the user asks to contact/support with a human agent, advisor, or staff."\n\n'
                )



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
                    # DEBUG: Ver qué enviamos
                    print("DEBUG: --- PAYLOAD ROUTER ---")
                    # print(f"DEBUG: System Instruction:\n{system_instruction}") 
                    print(f"DEBUG: Tools count: {len(valid_process_details)}")
                    
                    # --- PETICIÓN AL ROUTER (Esta línea faltaba o estaba mal indentada) ---
                    r = requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", json=payload_router, timeout=None)
                    raw_content = r.json()["choices"][0]["message"]["content"]
                    print(f"DEBUG: --- RESPUESTA ROUTER RAW ---\n{raw_content}\n-------------------------------") # DEBUG
                    
                    # 2. LÓGICA DE INTERPRETACIÓN BLINDADA
                    try:
                        def safe_parse_router_output(raw_content: str) -> dict:
                            clean = raw_content.replace("```json", "").replace("```", "").strip()

                            # 1) Intento normal
                            try:
                                obj = json.loads(clean)
                                if isinstance(obj, dict):
                                    return obj
                            except Exception:
                                pass

                            # 2) Fallback: extraer campos aunque el JSON esté roto por comillas internas
                            action_m = re.search(r'"action"\s*:\s*"([^"]+)"', clean)
                            func_m = re.search(r'"function_name"\s*:\s*(null|"[^"]*")', clean)

                            action = action_m.group(1) if action_m else "ANSWER"
                            func_raw = func_m.group(1) if func_m else "null"
                            function_name = None if func_raw == "null" else func_raw.strip('"')

                            # Rescatar response “a mano” cortando antes de ,"action":
                            response_text = clean
                            parts = re.split(r'"\s*,\s*"action"\s*:\s*', clean, maxsplit=1)
                            if len(parts) == 2:
                                left = parts[0]
                                m = re.search(r'"response"\s*:\s*"', left)
                                if m:
                                    response_text = left[m.end():]  # todo lo que venga después de "response":" (aunque tenga comillas)

                            return {"response": response_text, "action": action, "function_name": function_name}

                        data_router = safe_parse_router_output(raw_content)

                        
                        if isinstance(data_router, dict):
                            # CASO A: Respuesta procesada por ChatService (tiene 'action')
                            if "action" in data_router:
                                server_action = data_router.get("action")
                                server_func = data_router.get("function_name")
                                server_response = data_router.get("response", "")

                                if server_action == "FUNCTION":
                                    action = "FUNCTION"
                                    found_process_name = server_func

                                elif server_action == "ANSWER":
                                    # Checkeos especiales
                                    if server_func == "OFF_TOPIC":
                                        action = "OFF_TOPIC"
                                    elif "RAG_MODE" in server_response:
                                        action = "ANSWER" # Flujo normal RAG
                                    else:
                                        # === CASO AMBIGUO O SALUDO ===
                                        # Si no es RAG_MODE, pero action es ANSWER, significa que 
                                        # el Router mandó un texto directo (Saludo o Aclaración de Ambigüedad)
                                        # Renderizamos ese texto directamente y cortamos la ejecución.
                                        
                                        yield json.dumps({
                                            "type": "final",
                                            "data": {
                                                "response": server_response, # Aquí va "¿Te refieres a X o Y?"
                                                "sources": [],
                                                "action": "ANSWER",
                                                "is_function": False,
                                                "offer_human_handoff": False
                                            }
                                        }) + "\n"
                                        return # <--- IMPORTANTE: Terminamos aquí para no hacer RAG ni nada más.

                    except Exception as e:
                        logger.error(f"Error parseando router JSON: {e}")
                        action = "ANSWER"

                except Exception as e:
                    logger.error(f"Error router connection: {e}")
                    action = "ANSWER"
                    
                # =============================================================
                # C. EJECUCIÓN (Lógica Nueva y Limpia)
                # =============================================================
                
                final_response_text = ""
                final_sources = []
                is_function = False
                payload_data = {}

                if action == "GREETING":
                    final_response_text = "¡Hola! 👋 Soy el asistente virtual de la UNEMI. ¿En qué puedo ayudarte hoy?"
                    yield json.dumps({
                        "type": "final",
                        "data": {"response": final_response_text, "sources": [], "action": "ANSWER", "is_function": False, "offer_human_handoff": False}
                    }) + "\n"
                
                elif action == "OFF_TOPIC":
                    final_response_text = "Lo siento, solo estoy entrenado para responder dudas académicas y administrativas."
                    yield json.dumps({
                        "type": "final",
                        "data": {"response": final_response_text, "sources": [], "action": "ANSWER", "is_function": False, "offer_human_handoff": False}
                    }) + "\n"

                elif action == "FUNCTION":
                    if found_process_name == "HUMAN_HANDOFF":
                         final_response_text = "Entendido 😊 Enviaré tu solicitud a mis compañeros humanos. Por favor cuéntame tu caso de nuevo y, si tienes evidencia, adjúntala (opcional)."
                         is_function = True
                         payload_data = {"status": "success", "need_documentation": True, "upload_optional": True, "handoff_mode": True}
                         
                         yield json.dumps({
                            "type": "final",
                            "data": {
                                "response": final_response_text,
                                "sources": [],
                                "is_function": True,
                                "action": "FUNCTION",
                                "payload": payload_data,
                                "offer_human_handoff": False
                            }
                         }) + "\n"
                    else:
                        proc = BusinessProcess.objects.filter(nombre=found_process_name, status=True).first()
                        if proc:
                            # Validar fechas
                            today = timezone.now().date()
                            is_active = True
                            if not proc.is_infinite:
                                if not (proc.start_date <= today <= proc.end_date):
                                    is_active = False
                            
                            if not is_active:
                                # PROCESO CERRADO: RAG FORCEJADO CON AVISO
                                msg_bd = proc.closed_message if (proc.closed_message and proc.closed_message.strip()) else f"El proceso {proc.nombre} no se encuentra habilitado en el rango de fechas actual."
                                header_msg = f"⚠️ AVISO: {proc.nombre}\n{msg_bd}"
                                
                                # Cambio de planes: Ejecutamos RAG directamnete
                                # Para simplificar y no duplicar lógica de traducción:
                                yield json.dumps({"type": "status", "text": "Interpretando consulta..."}) + "\n"
                                yield from execute_rag(real_query_for_processing, forced_intro_text=header_msg)
                                return

                            else:
                                # PROCESO ABIERTO
                                res = get_process_response_from_db(found_process_name)
                                final_response_text = res["text"]
                                is_function = True
                                payload_data = res
                                if res.get("source_url"):
                                    final_sources.append({"title": f"{found_process_name}", "url": res.get("source_url")})
                                
                                yield json.dumps({
                                    "type": "final",
                                    "data": {
                                        "response": final_response_text,
                                        "sources": final_sources,
                                        "is_function": True,
                                        "action": "FUNCTION",
                                        "payload": payload_data,
                                        "offer_human_handoff": False
                                    }
                                }) + "\n"
                        else:
                            # Si el router falló y dio un nombre que no existe, forzamos RAG
                            action = "ANSWER" 

                # =============================================================
                # D. RAG DIRECTO CON REFORMULACIÓN INTERNA
                # =============================================================
                if action == "ANSWER":
                    
                    # 1. Validación de Seguridad: Si no hay docs, no llamar a la IA
                    if not doc_ids_for_pgpt:
                        yield json.dumps({
                            "type": "final",
                            "data": {
                                "response": "Lo siento, no se encontraron normativas habilitadas para tu perfil en este momento.",
                                "sources": [],
                                "action": "ANSWER", 
                                "is_function": False,
                                "offer_human_handoff": False
                            }
                        }) + "\n"
                        return

                    # 2. Reformulación
                    yield json.dumps({"type": "status", "text": "Interpretando consulta..."}) + "\n"
                    
                    optimized_query = real_query_for_processing # Por defecto usamos la original (que es user_msg limpiecito)
                    
                    reform_payload = {
                        "messages": [
                            {"role": "system", "content": "REFORMULATE_QUERY_MODE"}, 
                            {"role": "user", "content": real_query_for_processing}
                        ],
                        "stream": False, 
                        "temperature": 0.1, 
                        "use_context": False
                    }
                    
                    try:
                        r_ref = requests.post(f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions", json=reform_payload, timeout=600)
                        if r_ref.status_code == 200:
                            content = r_ref.json()["choices"][0]["message"]["content"]
                            clean_content = content.strip().replace('"', '').replace("Output:", "")
                            
                            # Validar que no haya devuelto vacío
                            if len(clean_content) > 5:
                                optimized_query = clean_content
                                print(f"🔄 REFORMULACIÓN INTERNA: '{real_query_for_processing}' -> '{optimized_query}'")
                    except Exception as e:
                        logger.error(f"Error reformulación silenciosa: {e}")
                    
                    # 3. EJECUCIÓN FINAL (Aquí está el cambio clave)
                    yield from execute_rag(
                        query_text=optimized_query, 
                        allowed_ids=doc_ids_for_pgpt, 
                        original_query=real_query_for_processing
                    )

            except Exception as e:
                logger.error(f"Error stream: {e}")
                yield json.dumps({"type": "error", "text": "Error interno."}) + "\n"

        return StreamingHttpResponse(event_stream(), content_type='application/x-ndjson')
# ==============================================================================
# 4. GESTIÓN DOCUMENTAL
# ==============================================================================

def document_manager(request):
    documents = RagDocument.objects.filter(status=True).order_by('-fecha_creacion')
    
    # Optimizamos la consulta con select_related para traer el nombre del tipo en una sola query
    processes = BusinessProcess.objects.filter(status=True).select_related('process_type').order_by('-fecha_creacion')
    
    chatbot_roles = ChatbotRol.objects.filter(status=True).prefetch_related('carreras').annotate(
        is_general=Case(
            When(nombre__icontains='General', then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('is_general', 'nombre')
    tipos_catalogo = get_dynamic_sga_roles()
    carreras_reales = SgaCarrera.objects.all().values('id', 'nombre').order_by('nombre')

    # NUEVO: Traer los tipos de procesos activos para el select
    process_types = BusinessProcessType.objects.filter(status=True).order_by('nombre')

    return render(request, 'chatbot/document_manager.html', {
        'documents': documents,
        'processes': processes,
        'chatbot_roles': chatbot_roles,
        'tipos_base': tipos_catalogo, 
        'carreras_list': carreras_reales,
        'process_types': process_types,
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


                is_ok, info = validate_pdf_has_text(f, sample_pages=10)

                if not is_ok:
                    reason = info.get("reason", "PDF inválido.")
                    checked = info.get("checked_pages")
                    avg = info.get("avg_words_per_page")
                    messages.error(
                        request,
                        f"'{f.name}' no es válido para RAG: {reason} "
                        f"(muestreo {checked} pág, prom {avg:.1f} palabras/pág)."
                    )
                    skip += 1
                    continue



                
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
                        print(f"📡 Enviando archivo a IA: {ingest_url}")

                        target_url_with_id = f"{ingest_url}?db_id={doc_db.id}"
                        r = requests.post(
                            target_url_with_id, 
                            files={'file': (doc_db.nombre, local_file, 'application/pdf')}, # Ajustar content-type si varía
                            timeout=None
                        )
                    print(f"Respuesta IA Status: {r.status_code}")
                    
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
                except requests.exceptions.ConnectTimeout:
                    logger.error("❌ Error: La IA tardó demasiado en responder (Timeout).")
                    messages.warning(request, f"El archivo {f.name} se guardó localmente, pero la IA no respondió a tiempo.")
                except requests.exceptions.ConnectionError:
                    logger.error(f"❌ Error: No se puede conectar a {settings.PRIVATE_GPT_API_URL}. ¿Está encendido el contenedor?")
                    messages.error(request, f"Error de conexión con la IA para {f.name}.")
                except Exception as e:
                    logger.error(f"Error indexando en IA: {e}")
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
    # doc_id es el ID numérico de Django (Base de datos SQL local)
    if request.method == 'POST':
        try:
            # 1. Obtener el objeto de la BD Local
            doc = RagDocument.objects.get(id=doc_id)
            
            # 2. BORRAR DE LA IA PRIMERO (Usando el ID de PGPT)
            if doc.doc_id_pgpt:
                try:
                    # Llamamos al endpoint que ejecuta el código "agresivo" que te di arriba
                    api_url = f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{doc.doc_id_pgpt}"
                    response = requests.delete(api_url, timeout=None)
                    
                    if response.status_code == 200:
                        logger.info(f"Borrado exitoso en IA para: {doc.nombre}")
                    else:
                        logger.warning(f"La IA respondió {response.status_code} al borrar.")
                except Exception as e:
                    # Importante: Si la IA está caída, ¿queremos borrar localmente?
                    # Generalmente sí, para no bloquear al usuario, pero logueamos el error.
                    logger.error(f"Error de conexión al borrar de IA: {e}")

            # 3. BORRAR ARCHIVO FÍSICO Y REGISTRO LOCAL (Solo después de intentar con la IA)
            if doc.archivo:
                doc.archivo.delete(save=False) # Borra del disco duro / media
            
            doc.delete() # Borra la fila de la tabla SQL de Django
            
            messages.success(request, f"Documento '{doc.nombre}' eliminado completamente.")
            
        except RagDocument.DoesNotExist:
            messages.error(request, "El documento no existe.")
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
                    "db_id": doc.id,                 # <- CLAVE para que no se pierdan sources
                    "file_name": doc.nombre,         # <- opcional pero recomendado
                    "roles": role_ids,
                    "is_infinite": is_inf,
                    "valid_from": v_from,
                    "valid_to": v_to,
                    "access_url": doc.archivo.url if doc.archivo else None,
                }
                requests.post(
                    f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{doc.doc_id_pgpt}/metadata",
                    json=payload,
                    timeout=None
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
        name_input = request.POST.get('name')
        
        # AHORA RECIBIMOS EL ID DEL TIPO
        type_id = request.POST.get('process_type') 
        process_type_obj = get_object_or_404(BusinessProcessType, id=type_id)

        source_url = request.POST.get('source_url')
        business_context = request.POST.get('business_context')
        active_msg = request.POST.get('active_message')
        is_infinite = request.POST.get('is_infinite') == 'on'
        
        # Validamos documentación basado en input (el front ya sugiere según el tipo, pero el usuario decide)
        need_documentation = request.POST.get('need_documentation') == 'on'

        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None
        
        if is_infinite:
            now = timezone.now().date()
            start_date = now; end_date = now;
            
        has_closed = request.POST.get('has_closed_message') == 'on'
        closed_msg = request.POST.get('closed_message') if has_closed else None
        role_ids = request.POST.getlist('roles')

        proc = BusinessProcess.objects.create(
            nombre=name_input,
            process_type=process_type_obj, # Asignamos el objeto
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
        
        if role_ids: proc.roles_permitidos.set(role_ids)
            
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
        proc.nombre = request.POST.get('name') 
        proc.business_context = request.POST.get('business_context')
        
        # Actualizar Tipo
        type_id = request.POST.get('process_type')
        if type_id:
            proc.process_type = get_object_or_404(BusinessProcessType, id=type_id)

        proc.source_url = request.POST.get('source_url') or None
        
        raw_infinite = request.POST.get('is_infinite')
        proc.is_infinite = raw_infinite in ['on', 'true', '1', 'True']
        
        # Checkbox docs
        raw_docs = request.POST.get('need_documentation')
        proc.need_documentation = raw_docs in ['on', 'true', '1', 'True']
        
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
        
        has_closed_msg = request.POST.get('has_closed_message') == 'on'
        proc.closed_message = request.POST.get('closed_message') if has_closed_msg else None
        
        role_ids = request.POST.getlist('roles')
        proc.roles_permitidos.set(role_ids)
        
        proc.save()
        messages.success(request, "Proceso actualizado.")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        
    return redirect('chatbot:process_manager')

# ==============================================================================
# 6. SUBIDA DE DOCUMENTACIÓN (CHATBOT)
# ==============================================================================

import re

def validate_pdf_has_text(uploaded_file, *,
                          sample_pages=10,
                          min_words_per_page=20,
                          min_text_pages_ratio=0.30):
    """
    Retorna: (is_valid: bool, details: dict)
    - sample_pages: analiza solo las primeras N páginas (para no demorar en PDFs gigantes)
    - min_words_per_page: umbral para considerar que una página "tiene texto"
    - min_text_pages_ratio: % mínimo de páginas con texto para aceptar el PDF
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return False, {"reason": "Falta instalar PyMuPDF (pymupdf)."}

    # Lee bytes (IMPORTANTE: luego hacemos seek(0) para no romper el guardado)
    try:
        pdf_bytes = uploaded_file.read()
        uploaded_file.seek(0)
    except Exception:
        return False, {"reason": "No se pudo leer el archivo subido."}

    # Abrir PDF
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return False, {"reason": "El archivo no parece un PDF válido o está corrupto."}

    if doc.page_count <= 0:
        return False, {"reason": "El PDF no tiene páginas."}

    pages_to_check = min(doc.page_count, sample_pages)
    word_counts = []
    img_counts = []

    word_re = re.compile(r"\b\w+\b", re.UNICODE)

    for i in range(pages_to_check):
        page = doc.load_page(i)

        text = (page.get_text("text") or "").strip()
        words = len(word_re.findall(text))
        word_counts.append(words)

        # Conteo de imágenes (si hay muchas páginas con imágenes y sin texto, es escaneado)
        imgs = page.get_images(full=True) or []
        img_counts.append(len(imgs))

    text_pages = sum(1 for w in word_counts if w >= min_words_per_page)
    text_ratio = text_pages / pages_to_check

    total_words = sum(word_counts)
    total_imgs = sum(img_counts)

    details = {
        "page_count": doc.page_count,
        "checked_pages": pages_to_check,
        "total_words_in_sample": total_words,
        "avg_words_per_page": (total_words / pages_to_check) if pages_to_check else 0,
        "text_pages": text_pages,
        "text_ratio": text_ratio,
        "total_images_in_sample": total_imgs,
    }

    # Regla principal: si casi no hay texto, rechazamos
    if text_ratio < min_text_pages_ratio:
        # Mensaje más específico si además hay imágenes
        if total_imgs > 0:
            return False, {
                **details,
                "reason": "Parece un PDF escaneado (solo imágenes) o sin texto seleccionable."
            }
        return False, {**details, "reason": "El PDF casi no contiene texto seleccionable."}

    return True, details



@csrf_exempt
@require_http_methods(["POST"])
def upload_documentation(request):
    try:
        if 'file' not in request.FILES:
            return JsonResponse(
                {'status': 'error', 'message': 'No se recibió ningún archivo.'},
                status=400
            )

        uploaded_file = request.FILES['file']
        extra_details = (request.POST.get('details', '') or '').strip()

        storage = FileSystemStorage(
            location=os.path.join(settings.MEDIA_ROOT, 'balcon_docs'),
            base_url=settings.MEDIA_URL + 'balcon_docs/'
        )

        filename = storage.save(uploaded_file.name, uploaded_file)
        file_url = request.build_absolute_uri(storage.url(filename))

        logger.info(f"Archivo subido desde chatbot: {filename} | Detalles: {extra_details}")
        
        mensaje_para_usuario = (
            "Perfecto. Ya envié tu solicitud a mis compañeros humanos. "
            "Por favor revisa tu correo institucional para futuras notificaciones. "
            "¿Hay algo más en lo que te pueda ayudar?"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Archivo recibido correctamente.',
            'file_url': file_url,
            'ai_response': mensaje_para_usuario
        })

    except Exception as e:
        logger.error(f"Error subiendo documentación: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# --- GESTIÓN DE TIPOS DE PROCESO ---

@require_POST
def create_process_type(request):
    try:
        nombre = request.POST.get('nombre')

        req_docs = request.POST.get('requiere_documentacion') == 'on'

        BusinessProcessType.objects.create(
            nombre=nombre,
            requiere_documentacion_por_defecto=req_docs
        )
        messages.success(request, "Tipo de proceso creado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al crear tipo: {e}")
        
    return redirect('chatbot:document_manager')

@require_POST
def edit_process_type(request, type_id):
    pt = get_object_or_404(BusinessProcessType, id=type_id)
    try:
        pt.nombre = request.POST.get('nombre')
        pt.requiere_documentacion_por_defecto = request.POST.get('requiere_documentacion') == 'on'
        pt.save()
        messages.success(request, "Tipo actualizado.")
    except Exception as e:
        messages.error(request, f"Error al actualizar: {e}")
        
    return redirect('chatbot:document_manager')

@require_POST
def delete_process_type(request, type_id):
    pt = get_object_or_404(BusinessProcessType, id=type_id)
    try:
        pt.delete() # Esto fallará si hay procesos usándolo (on_delete=PROTECT)
        messages.success(request, "Tipo eliminado.")
    except Exception as e:
        messages.error(request, "No se puede eliminar este tipo porque hay procesos que lo utilizan.")
        
    return redirect('chatbot:document_manager')
