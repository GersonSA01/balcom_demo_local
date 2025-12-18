# views.py
from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from rest_framework.views import APIView

from chatbot.models import (
    BalconCategoria,
    BalconCategoriaCoordinaciones,
    BalconProceso,
    BusinessProcess,
    BusinessProcessType,
    ChatbotRol,
    RagDocument,
    SgaCarrera,
    SgaCoordinacionCarrera,
    SgaInscripcion,
    SgaMatricula,
    SgaPerfilusuario,
    SgaPersona,
    BalconProcesoservicio
)

logger = logging.getLogger(__name__)

# ==============================================================================
# Helpers generales
# ==============================================================================

HANDOFF_TRIGGER_MESSAGE = "HUMAN_HANDOFF"
SESSION_HANDOFF_PENDING_KEY = "handoff_pending"

ROLES_PERMITIDOS_MAP = {
    "inscripcion": "Estudiante (Pregrado)",
    "profesor": "Docente / Profesor",
    "administrativo": "Administrativo",
    "externo": "Usuario Externo",
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _safe_json_loads_maybe_double(raw: str) -> Optional[dict]:
    """
    Intenta parsear JSON siendo tolerante a bloques markdown, dobles llaves {{ }} 
    y texto basura alrededor.
    """
    if not raw:
        return None

    # 1. Limpieza básica de Markdown
    clean = raw.strip().replace("```json", "").replace("```", "").strip()

    # 2. Limpieza de dobles/triples llaves al inicio y final (La corrección clave)
    # Mientras empiece con {{ lo reducimos a {
    while clean.startswith("{{"):
        clean = clean[1:]
    # Mientras termine con }} lo reducimos a }
    while clean.endswith("}}"):
        clean = clean[:-1]

    # 3. Intento directo
    try:
        obj = json.loads(clean)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # 4. Búsqueda quirúrgica del primer '{' y último '}'
    start = clean.find("{")
    end = clean.rfind("}")
    
    if start != -1 and end != -1 and end > start:
        candidate = clean[start : end + 1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    return None


def _safe_parse_router_output(raw_content: str) -> dict:
    """
    Parsea la respuesta del Router.
    Ahora también extrae 'reformulated_query' si el chat_service lo envió.
    """
    clean = (raw_content or "").replace("```json", "").replace("```", "").strip()

    # 1) Intento JSON directo (Lo ideal)
    obj = _safe_json_loads_maybe_double(clean)
    if isinstance(obj, dict):
        # Normalizamos claves por si acaso
        return {
            "response": obj.get("response", ""),
            "action": obj.get("action", "ANSWER"),
            "function_name": obj.get("function_name"),
            "classification": obj.get("classification"),  # Nueva: clasificación del router
            "clarification": obj.get("clarification"),  # Nueva: aclaración para AMBIGUOUS
            # AQUÍ ESTÁ LA CLAVE: Rescatamos la query optimizada
            "reformulated_query": obj.get("reformulated_query") or obj.get("search_query")
        }

    # 2) Fallback regex (solo si falla el JSON)
    action_m = re.search(r'"action"\s*:\s*"([^"]+)"', clean)
    func_m = re.search(r'"function_name"\s*:\s*(null|"[^"]*")', clean)
    class_m = re.search(r'"classification"\s*:\s*"([^"]+)"', clean)
    clarif_m = re.search(r'"clarification"\s*:\s*"([^"]+)"', clean)
    
    action = action_m.group(1) if action_m else "ANSWER"
    func_raw = func_m.group(1) if func_m else "null"
    function_name = None if func_raw == "null" else func_raw.strip('"')
    classification = class_m.group(1) if class_m else None
    clarification = clarif_m.group(1) if clarif_m else None

    # Intentar rescatar reformulated_query via regex si es necesario
    reform_m = re.search(r'"reformulated_query"\s*:\s*"([^"]+)"', clean)
    reformulated_query = reform_m.group(1) if reform_m else None

    # Rescatar response
    response_text = clean
    # Limpieza básica para no devolver el JSON al usuario si falla todo
    if "{" in clean and "}" in clean:
         parts = re.split(r'"\s*,\s*"action"\s*:\s*', clean, maxsplit=1)
         if len(parts) == 2:
             left = parts[0]
             m = re.search(r'"response"\s*:\s*"', left)
             if m:
                 response_text = left[m.end() :]
    
    return {
        "response": response_text, 
        "action": action, 
        "function_name": function_name,
        "classification": classification,
        "clarification": clarification,
        "reformulated_query": reformulated_query
    }


def _is_process_active_by_date(proc: BusinessProcess, today: Optional[datetime.date] = None) -> bool:
    if today is None:
        today = timezone.now().date()

    if proc.is_infinite:
        return True

    # si faltan fechas, se considera activo (pero lo ideal es que siempre existan)
    if not proc.start_date or not proc.end_date:
        return True

    return proc.start_date <= today <= proc.end_date

@require_http_methods(["GET"])
def api_get_proceso_servicios(request):
    proceso_id = request.GET.get("proceso_id")
    if not proceso_id:
        return JsonResponse({"error": "Missing proceso_id"}, status=400)

    qs = (
        BalconProcesoservicio.objects
        .filter(proceso_id=proceso_id, status=True, servicio__estado=True)
        .select_related("servicio")
        .order_by("id")
    )

    servicios = []
    for ps in qs:
        servicios.append({
            "id": ps.id,  # id de balcon_procesoservicio (es el “servicio del proceso”)
            "nombre": (ps.servicio.nombre or ps.servicio.descripcion or "").strip()[:200],
            "descripcion": (ps.servicio.descripcion or "").strip(),
            "url": ps.url,
        })

    return JsonResponse({"proceso_id": int(proceso_id), "servicios": servicios})

def get_dynamic_sga_roles() -> List[Dict[str, str]]:
    """
    Devuelve los roles reales del modelo y añade un rol virtual 'General'.
    """
    roles_detectados: List[Dict[str, str]] = []

    for field in SgaPerfilusuario._meta.get_fields():
        if field.name in ROLES_PERMITIDOS_MAP:
            roles_detectados.append({"id": field.name, "nombre": ROLES_PERMITIDOS_MAP[field.name]})

    roles_detectados.append(
        {"id": "general", "nombre": "General / Todos (Cualquier usuario logueado)"}
    )

    return sorted(
        roles_detectados, key=lambda x: (0 if x["id"] == "general" else 1, x["nombre"])
    )


def get_process_response_from_db(
    process_name: str, 
    user_role_ids: set[int] = None, 
    user_carrera_ids: set[int] = None
) -> dict:
    """
    Arma la respuesta “FUNCTION” para procesos configurados en BD.
    Valida que el usuario tenga el rol y la carrera requerida.
    """
    if user_role_ids is None:
        user_role_ids = set()
    if user_carrera_ids is None:
        user_carrera_ids = set()

    try:
        # 1. Buscamos el proceso por nombre y status activo
        # Pre-cargamos roles y carreras para no hacer n queries
        process = (
            BusinessProcess.objects.filter(nombre=process_name, status=True)
            .select_related("process_type")
            .prefetch_related("roles_permitidos", "roles_permitidos__carreras")
            .first()
        )

        if not process:
            return {
                "text": f"Por ahora no tengo información disponible sobre el proceso '{process_name}'.",
                "status": "error",
                "need_documentation": False,
            }

        # 2. VALIDACIÓN DE SEGURIDAD (Roles y Carreras)
        is_allowed = False
        roles_proc = process.roles_permitidos.all()

        if not roles_proc.exists():
            # Si no tiene roles asignados, es PÚBLICO
            is_allowed = True
        else:
            # Si tiene roles, verificamos match
            for rol in roles_proc:
                if rol.id in user_role_ids:
                    # El usuario tiene el rol, verificamos si el rol tiene restricción de carrera
                    carreras_del_rol = rol.carreras.all()
                    
                    if not carreras_del_rol.exists():
                        # El rol es global (para todas las carreras), acceso concedido
                        is_allowed = True
                        break
                    
                    # El rol es específico de carreras, verificamos intersección
                    if any(c.id in user_carrera_ids for c in carreras_del_rol):
                        is_allowed = True
                        break
        
        if not is_allowed:
            return {
                "text": "Lo siento, este proceso no está disponible para tu perfil o carrera actual.",
                "status": "unauthorized",
                "need_documentation": False
            }

        # 3. Construcción de respuesta (Igual que antes)
        tipo_nombre = (process.process_type.nombre or "").strip().lower() if process.process_type else ""

        # Informativo: no pedir docs
        if tipo_nombre == "informativo":
            friendly_text = (process.active_message or process.business_context or "").strip()
            need_docs = False
        else:
            friendly_text = (
                "Hola 👋, para continuar con tu solicitud necesito que me compartas la documentación requerida:\n"
                f"{(process.active_message or '').strip()}\n"
                "También necesitaré que me des de nuevo los detalles de tu solicitud."
            ).strip()
            need_docs = bool(process.need_documentation)

        return {
            "text": friendly_text or "Por ahora no tengo un mensaje configurado para este proceso.",
            "need_documentation": need_docs,
            "source_url": process.source_url,
        }

    except Exception as e:
        logger.exception("Error validando proceso: %s", e)
        return {"text": "Error interno al procesar la solicitud.", "status": "error", "need_documentation": False}


# ==============================================================================
# 2. Roles (CRUD) + Users API + Health
# ==============================================================================

@require_POST
def create_chatbot_role(request):
    try:
        nombre = request.POST.get("nombre")
        campo_sga = request.POST.get("tipo_usuario_id")
        carreras_ids = request.POST.getlist("carreras")

        rol = ChatbotRol.objects.create(nombre=nombre, campo_sga=campo_sga)
        if carreras_ids:
            rol.carreras.set(carreras_ids)

        messages.success(request, "Rol creado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al crear rol: {str(e)}")

    return redirect("chatbot:document_manager")


@require_POST
def delete_chatbot_role(request, role_id):
    rol = get_object_or_404(ChatbotRol, id=role_id)
    try:
        rol.delete()
        messages.success(request, "Rol eliminado correctamente.")
    except Exception:
        messages.error(request, "No se pudo eliminar el rol (puede estar en uso).")

    return redirect("chatbot:document_manager")


@require_POST
def edit_chatbot_role(request, role_id):
    rol = get_object_or_404(ChatbotRol, id=role_id)
    try:
        rol.nombre = request.POST.get("nombre")
        rol.campo_sga = request.POST.get("tipo_usuario_id")

        carreras_ids = request.POST.getlist("carreras")
        if carreras_ids:
            rol.carreras.set(carreras_ids)
        else:
            rol.carreras.clear()

        rol.save()
        messages.success(request, "Rol actualizado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al editar: {str(e)}")

    return redirect("chatbot:document_manager")


@require_http_methods(["GET"])
def get_users_list(request):
    TARGET_CEDULAS = ["0940153000", "0706191558", "2300371198"]

    roles_configurados = get_dynamic_sga_roles()
    mapa_frontend = {
        "inscripcion": "es_estudiante",
        "profesor": "es_profesor",
        "administrativo": "es_administrativo",
        "externo": "es_externo",
        "general": "es_general",
    }

    data: List[dict] = []
    try:
        personas = SgaPersona.objects.filter(cedula__in=TARGET_CEDULAS)

        for p in personas:
            perfiles_qs = SgaPerfilusuario.objects.filter(persona=p, status=True)
            perfiles_list = []

            for perf in perfiles_qs:
                perf_data = {"id": perf.id}

                # carrera (si existe)
                nombre_carrera = ""
                if perf.inscripcion and getattr(perf.inscripcion, "carrera", None):
                    nombre_carrera = perf.inscripcion.carrera.nombre
                perf_data["carrera_nombre"] = nombre_carrera

                # roles detectados
                roles_detectados_nombres: List[str] = []
                for rol_info in roles_configurados:
                    campo_bd = rol_info["id"]
                    nombre_legible = rol_info["nombre"]

                    if campo_bd == "general":
                        valor = True
                    else:
                        valor = getattr(perf, campo_bd, None)

                    if valor:
                        roles_detectados_nombres.append(nombre_legible)
                        key_frontend = mapa_frontend.get(campo_bd)
                        if key_frontend:
                            perf_data[key_frontend] = True

                perf_data["descripcion"] = (
                    " / ".join(roles_detectados_nombres)
                    if roles_detectados_nombres
                    else "Sin Rol Configurado"
                )

                for k in mapa_frontend.values():
                    perf_data.setdefault(k, False)

                # periodos
                perf_data["periodos"] = []
                if perf.inscripcion:
                    try:
                        matriculas = (
                            SgaMatricula.objects.filter(
                                inscripcion=perf.inscripcion, retiradomatricula=False
                            )
                            .select_related("nivel__periodo")
                        )

                        periodos_dict: Dict[int, dict] = {}
                        for m in matriculas:
                            if m.nivel and m.nivel.periodo:
                                per = m.nivel.periodo
                                if per.id not in periodos_dict:
                                    periodos_dict[per.id] = {
                                        "id": per.id,
                                        "nombre": per.nombre,
                                        "activo": per.activo,
                                        "inicio": per.inicio,
                                    }

                        lista_periodos = list(periodos_dict.values())
                        lista_periodos.sort(key=lambda x: x["inicio"], reverse=True)
                        perf_data["periodos"] = lista_periodos
                    except Exception as ex:
                        logger.error("Error obteniendo periodos para perfil %s: %s", perf.id, ex)

                perfiles_list.append(perf_data)

            data.append(
                {
                    "cedula": p.cedula,
                    "nombre_completo": f"{p.nombres} {p.apellido1} {p.apellido2}".strip(),
                    "perfiles": perfiles_list,
                }
            )

    except Exception as e:
        logger.exception("Error obteniendo usuario: %s", e)
        return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def health(request):
    pgpt_status = False
    try:
        r = requests.get(f"{settings.PRIVATE_GPT_API_URL}/health", timeout=5)
        pgpt_status = (r.status_code == 200)
    except Exception:
        pgpt_status = False
    return JsonResponse({"status": "ok", "private_gpt_connected": pgpt_status})


# ==============================================================================
# 2.1 Servicios Estudiante
# ==============================================================================

def get_servicios_para_estudiante(django_user, perfil_id: Optional[int] = None, periodo_id: Optional[int] = None):
    """
    Retorna categorías y procesos del Balcón disponibles para el estudiante por coordinación.
    Ahora usa el perfil_id seleccionado para determinar la carrera correcta.
    """
    response_data = {"estudiante": None, "coordinacion": None, "categorias": []}

    try:
        persona = SgaPersona.objects.filter(usuario=django_user).first()
        if not persona:
            print(f"[DEBUG:get_servicios_para_estudiante] ❌ Persona no encontrada para usuario: {django_user}")
            return response_data

        # ✅ CAMBIO CLAVE: Usar el perfil seleccionado si viene
        inscripcion = None
        if perfil_id:
            perfil = SgaPerfilusuario.objects.filter(
                id=perfil_id, persona=persona, status=True
            ).select_related("inscripcion__carrera").first()
            if perfil and perfil.inscripcion:
                inscripcion = perfil.inscripcion
                print(
                    f"[DEBUG:get_servicios_para_estudiante] ✅ Usando inscripcion del PERFIL {perfil_id} "
                    f"(carrera {inscripcion.carrera_id}) para persona {persona.cedula}"
                )

        # Fallback: primera inscripción activa si no hay perfil_id o no tiene inscripción
        if not inscripcion:
            inscripcion = (
                SgaInscripcion.objects.filter(persona=persona, activo=True)
                .select_related("carrera")
                .first()
            )
            if inscripcion:
                print(
                    f"[DEBUG:get_servicios_para_estudiante] ↩️ Fallback a primera inscripcion activa "
                    f"(carrera {inscripcion.carrera_id}) para persona {persona.cedula}"
                )

        if not inscripcion:
            print(f"[DEBUG:get_servicios_para_estudiante] ❌ Sin inscripcion activa para persona {persona.id}")
            return response_data

        rel = (
            SgaCoordinacionCarrera.objects.filter(carrera=inscripcion.carrera)
            .select_related("coordinacion")
            .first()
        )
        if not rel or not rel.coordinacion:
            return response_data

        coordinacion_estudiante = rel.coordinacion
        response_data["estudiante"] = f"{persona.nombres} {persona.apellido1}"
        response_data["coordinacion"] = coordinacion_estudiante.nombre

        categorias_permitidas_ids = BalconCategoriaCoordinaciones.objects.filter(
            coordinacion=coordinacion_estudiante
        ).values_list("categoria_id", flat=True)

        categorias = BalconCategoria.objects.filter(id__in=categorias_permitidas_ids, estado=True)

        for cat in categorias:
            procesos = (
                BalconProceso.objects.filter(categoria=cat, activo=True)
                .select_related("tipo")
            )

            lista_procesos = []
            for proc in procesos:
                lista_procesos.append(
                    {
                        "id": proc.id,
                        "nombre": proc.descripcion,
                        "tipo": proc.tipo.descripcion if proc.tipo else "General",
                        "tiempo_estimado": proc.tiempoestimado,
                    }
                )

            if lista_procesos:
                response_data["categorias"].append(
                    {"id": cat.id, "nombre": cat.descripcion, "procesos": lista_procesos}
                )

    except Exception as e:
        logger.error("Error obteniendo servicios: %s", e)

    return response_data


def api_get_servicios_estudiante(request):
    target_cedula = request.GET.get("cedula")
    perfil_id = request.GET.get("perfil_id")
    periodo_id = request.GET.get("periodo_id")

    if not target_cedula:
        # fallback retrocompat
        target_user_id = request.GET.get("user_id")
        if target_user_id:
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=target_user_id)
                return JsonResponse(get_servicios_para_estudiante(user))
            except Exception:
                pass
        return JsonResponse({"error": "No cedula provided"}, status=400)

    try:
        persona = SgaPersona.objects.filter(cedula=target_cedula).first()
        if not persona:
            return JsonResponse({"categorias": [], "message": "Persona no encontrada"})

        if not persona.usuario:
            return JsonResponse({"categorias": [], "message": "Persona sin usuario vinculado"})

        # Parseo seguro de perfil_id y periodo_id
        perfil_id_int = None
        periodo_id_int = None
        try:
            if perfil_id:
                perfil_id_int = int(perfil_id)
        except (ValueError, TypeError):
            perfil_id_int = None

        try:
            if periodo_id:
                periodo_id_int = int(periodo_id)
        except (ValueError, TypeError):
            periodo_id_int = None

        data = get_servicios_para_estudiante(
            persona.usuario,
            perfil_id=perfil_id_int,
            periodo_id=periodo_id_int,
        )
        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ==============================================================================
# 3. Chat (Router + RAG + Handoff) NDJSON Streaming
# ==============================================================================

class ChatView(APIView):
    def post(self, request):
        if not request.data:
            return JsonResponse({"error": "Empty"}, status=400)

        # DEBUG request body
        try:
            print("\nDEBUG: INCOMING REQUEST BODY:\n" + json.dumps(request.data, indent=2, ensure_ascii=False) + "\n")
        except Exception:
            pass

        user_msg = (request.data.get("message", "") or "").strip()
        _history = request.data.get("history", [])  # por ahora no se usa en router (puedes usarlo luego)

        # flag one-shot del frontend (solo debe enviarse en confirmHandoff)
        handoff_mode = bool(request.data.get("handoff_mode", False))

        # ✅ FIX LOOP: solo es handoff si el mensaje es exactamente el trigger
        is_handoff_confirmation = bool(handoff_mode and user_msg == HANDOFF_TRIGGER_MESSAGE)

        # fallback viejo SOLO si no vino el boolean
        if not handoff_mode and user_msg:
            trigger_phrases = ["sí, contactar a un humano", "contactar a un humano"]
            if any(p in user_msg.lower() for p in trigger_phrases):
                is_handoff_confirmation = True

        # session_data parsing
        raw_session = request.data.get("session_data", {}) or {}
        current_process = request.data.get("current_process")
        cedula = None
        perfil_id = None
        periodo_id = None

        if raw_session:
            try:
                cedula = list(raw_session.keys())[0]
                user_data = raw_session[cedula]
                periodo_id = user_data.get("periodo_id")
                perfiles = user_data.get("perfiles", [])
                if perfiles:
                    perfil_id = perfiles[0].get("id")
            except Exception as e:
                logger.error("Error parseando sesión: %s", e)

        def event_stream():
            try:
                # -------------------------------------------------------------
                # Helper: Normalizar historial de conversación
                # -------------------------------------------------------------
                def _normalize_history(history, max_items=6, max_chars=1200):
                    """Normaliza el historial de conversación para enviarlo al LLM."""
                    if not isinstance(history, list):
                        return []

                    out = []
                    for item in history:
                        if not isinstance(item, dict):
                            continue

                        role = (item.get("role") or "").strip().lower()
                        if role not in ("user", "assistant"):
                            continue

                        content = (item.get("content") or "").strip()
                        if not content:
                            continue

                        if len(content) > max_chars:
                            content = content[:max_chars] + "…"

                        out.append({"role": role, "content": content})

                    return out[-max_items:]

                # -------------------------------------------------------------
                # 0) Handoff inmediato (SIN IA)  ✅ blindado
                # -------------------------------------------------------------
                if is_handoff_confirmation:
                    request.session[SESSION_HANDOFF_PENDING_KEY] = True
                    request.session.modified = True

                    time.sleep(0.2)

                    payload_data = {
                        "status": "success",
                        "need_documentation": True,
                        "upload_optional": True,
                        "handoff_mode": True,  # solo para UI (NO para persistir frontend)
                    }

                    msg_text = (
                        "Entendido. Para derivarte con mis compañeros, por favor descríbeme de nuevo tu caso "
                        "y adjunta evidencia si es necesario (opcional)."
                    )

                    yield json.dumps(
                        {
                            "type": "final",
                            "data": {
                                "response": msg_text,
                                "sources": [],
                                "is_function": True,
                                "action": "FUNCTION",
                                "payload": payload_data,
                                "offer_human_handoff": False,
                            },
                        }
                    ) + "\n"
                    return

                # -------------------------------------------------------------
                # Helpers internos (RAG y filtros)
                # -------------------------------------------------------------
                def execute_rag(
                    query_text: str,
                    allowed_ids: Optional[List[str]] = None,
                    original_query: Optional[str] = None,
                    forced_intro_text: Optional[str] = None,
                ):
                    """
                    Ejecuta RAG en PrivateGPT, devolviendo JSON NDJSON final.
                    - ✅ Siempre incluye un mensaje de usuario (fix crítico).
                    - allowed_ids: lista de db_id (RagDocument.id) permitidos.
                    """
                    yield json.dumps({"type": "status", "text": "Consultando normativa institucional..."}) + "\n"

                    # Normalizar historial para el RAG (más corto que el Router)
                    rag_history = _normalize_history(_history, max_items=4)

                    oq = (original_query or "").strip()
                    qq = (query_text or "").strip()

                    # Construir mensajes con historial
                    if oq and qq and oq != qq:
                        messages_payload = (
                            [{"role": "system", "content": "RAG_EXPERT_MODE"}]
                            + rag_history
                            + [
                                {"role": "user", "content": f"CONSULTA DEL USUARIO: {oq}"},
                                {"role": "user", "content": qq},
                            ]
                        )
                    else:
                        # ✅ FIX: siempre mandar user message
                        messages_payload = (
                            [{"role": "system", "content": "RAG_EXPERT_MODE"}]
                            + rag_history
                            + [{"role": "user", "content": (qq or oq)}]
                        )

                    context_filter_payload = None
                    if allowed_ids:
                        context_filter_payload = {"docs_ids": [str(x) for x in allowed_ids]}

                    rag_payload = {
                        "messages": messages_payload,
                        "use_context": True,
                        "stream": False,
                        "context_filter": context_filter_payload,
                    }

                    final_response_text = "Lo siento, no pude obtener información normativa..."
                    final_sources: List[dict] = []
                    answer_found = True

                    try:
                        print(f"🌐 RAG Request (Filter count: {len(allowed_ids) if allowed_ids else 0})")
                        r_rag = requests.post(
                            f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions",
                            json=rag_payload,
                            timeout=None,
                        )

                        if r_rag.status_code == 200:
                            rag_resp = r_rag.json()
                            raw_rag_text = rag_resp.get("choices", [{}])[0].get("message", {}).get("content", "")

                            data_json = _safe_json_loads_maybe_double(raw_rag_text)
                            cited_db_ids: List[int] = []

                            if data_json:
                                final_response_text = data_json.get("response", raw_rag_text)
                                
                                # ✅ PARSEO ROBUSTO DE answer_found
                                af_raw = data_json.get("answer_found")
                                if af_raw is None:
                                    # Si no viene el campo, asumimos True (respuesta encontrada)
                                    answer_found = True
                                elif isinstance(af_raw, bool):
                                    answer_found = af_raw
                                elif isinstance(af_raw, str):
                                    answer_found = (af_raw.lower().strip() in ("true", "1", "yes", "si", "sí"))
                                else:
                                    # Para números: 1 = True, 0 = False
                                    answer_found = bool(af_raw)
                                
                                logger.info(f"📊 RAG answer_found parsed: {af_raw} -> {answer_found}")

                                raw_ids = data_json.get("source_ids", [])
                                cited_db_ids = [int(x) for x in raw_ids if str(x).isdigit()]
                            else:
                                final_response_text = raw_rag_text
                                answer_found = False
                                logger.warning("⚠️ RAG: No se pudo parsear JSON, answer_found=False")

                            # ✅ USAR EL MENSAJE QUE VIENE DE chat_service (NO reemplazarlo)
                            # El mensaje ya viene con la pregunta sobre contactar humanos si answer_found es False
                            if not answer_found:
                                logger.info("❌ RAG: answer_found=False, usando mensaje de chat_service con pregunta de handoff")
                                # NO modificamos final_response_text, usamos el que viene de chat_service
                            else:
                                logger.info("✅ RAG: answer_found=True, usando respuesta de chat_service")

                            # Sources por BD local (ideal)
                            if cited_db_ids:
                                docs_from_db = RagDocument.objects.filter(id__in=cited_db_ids)
                                for doc in docs_from_db:
                                    full_url = request.build_absolute_uri(doc.archivo.url) if doc.archivo else None
                                    final_sources.append({"title": doc.nombre, "url": full_url})

                            # Fallback sources (metadata de la IA)
                            if not final_sources:
                                api_sources = rag_resp.get("sources", []) or []
                                for src in api_sources:
                                    meta = src.get("document", {}).get("doc_metadata", {}) or {}
                                    fname = meta.get("file_name") or meta.get("file_name_") or "Documento Normativo"
                                    furl = meta.get("access_url")
                                    if fname not in [s["title"] for s in final_sources]:
                                        final_sources.append({"title": fname, "url": furl})

                    except Exception as e:
                        logger.error("Error en RAG request: %s", e)
                        answer_found = False

                    if forced_intro_text:
                        final_response_text = f"{forced_intro_text}\n\n{final_response_text}"

                    # ✅ LÓGICA FINAL: offer_human_handoff SOLO basado en answer_found
                    # Si answer_found es True, NO ofrecemos handoff automático
                    # Si answer_found es False, SÍ ofrecemos handoff
                    offer_handoff = not answer_found
                    
                    print(f"🎯 RAG Final: answer_found={answer_found}, offer_human_handoff={offer_handoff}")

                    yield json.dumps(
                        {
                            "type": "final",
                            "data": {
                                "response": final_response_text,
                                "sources": final_sources,
                                "is_function": False,
                                "action": "ANSWER",
                                "offer_human_handoff": offer_handoff,
                            },
                        }
                    ) + "\n"

                # -------------------------------------------------------------
                # 1) Determinar roles/carrera del usuario
                # -------------------------------------------------------------
                user_matched_role_ids: set[int] = set()
                user_carrera_ids: set[int] = set()

                if cedula:
                    persona = SgaPersona.objects.filter(cedula=cedula).first()
                    perfil = None

                    try:
                        target_pid = (raw_session.get(cedula, {}).get("perfiles", [{}])[0].get("id")) if raw_session.get(cedula) else None
                    except Exception:
                        target_pid = None

                    if persona:
                        if target_pid:
                            perfil = SgaPerfilusuario.objects.filter(id=target_pid, persona=persona, status=True).first()
                        if not perfil:
                            perfil = SgaPerfilusuario.objects.filter(persona=persona, status=True).first()

                    if persona and perfil:
                        request.session["user_cedula"] = cedula
                        request.session["user_name"] = str(persona)

                        all_system_roles = ChatbotRol.objects.filter(status=True).prefetch_related("carreras")

                        for chatbot_rol in all_system_roles:
                            campo_sga_requerido = chatbot_rol.campo_sga

                            if campo_sga_requerido == "general":
                                user_matched_role_ids.add(chatbot_rol.id)
                                continue

                            objeto_relacionado = getattr(perfil, campo_sga_requerido, None)
                            if not objeto_relacionado:
                                continue

                            carreras_del_rol = chatbot_rol.carreras.all()

                            if not carreras_del_rol.exists():
                                user_matched_role_ids.add(chatbot_rol.id)
                            else:
                                carrera_obj = getattr(objeto_relacionado, "carrera", None)
                                if carrera_obj and carrera_obj.id in [c.id for c in carreras_del_rol]:
                                    user_matched_role_ids.add(chatbot_rol.id)
                                    user_carrera_ids.add(carrera_obj.id)

                        request.session["user_roles"] = list(user_matched_role_ids)
                        request.session.modified = True

                yield json.dumps({"type": "status", "text": "Analizando..."}) + "\n"

                # -------------------------------------------------------------
                # 2) Filtrar documentos autorizados para RAG
                # -------------------------------------------------------------
                today = timezone.now().date()

                all_docs = (
                    RagDocument.objects.filter(status=True, is_indexed=True)
                    .prefetch_related("roles_permitidos", "roles_permitidos__carreras")
                )

                doc_ids_for_pgpt: List[str] = []
                debug_docs_log: List[str] = []

                for doc in all_docs:
                    # fechas
                    if not doc.is_infinite:
                        if doc.valid_from and today < doc.valid_from:
                            continue
                        if doc.valid_to and today > doc.valid_to:
                            continue

                    roles_doc = doc.roles_permitidos.all()

                    is_allowed = False
                    matched_reason = ""

                    if not roles_doc.exists():
                        is_allowed = True
                        matched_reason = "PÚBLICO (Sin roles)"
                    else:
                        for rol_config in roles_doc:
                            if rol_config.id not in user_matched_role_ids:
                                continue

                            carreras_del_rol = rol_config.carreras.all()
                            if not carreras_del_rol.exists():
                                is_allowed = True
                                matched_reason = f"ROL: {rol_config.nombre} (Global)"
                                break

                            if any(c.id in user_carrera_ids for c in carreras_del_rol):
                                is_allowed = True
                                matched_reason = f"ROL: {rol_config.nombre} (Carrera Match)"
                                break

                    if is_allowed and doc.doc_id_pgpt:
                        # ⚠️ IMPORTANT: aquí mantenemos tu contrato: docs_ids == RagDocument.id (db_id)
                        doc_ids_for_pgpt.append(str(doc.id))
                        debug_docs_log.append(f"  ✅ [ID: {doc.id}] {doc.nombre}  --->  {matched_reason}")

                print(f"\nDEBUG: === 📂 DOCUMENTOS AUTORIZADOS ({len(debug_docs_log)}) ===")
                if debug_docs_log:
                    for line in debug_docs_log:
                        print(line)
                else:
                    print("  ❌ Ningún documento autorizado para este perfil.")
                print("DEBUG: ===============================================\n")

                # -------------------------------------------------------------
                # 3) Filtrar procesos autorizados (BusinessProcess) para router tools list
                # -------------------------------------------------------------
                all_processes = (
                    BusinessProcess.objects.filter(status=True)
                    .prefetch_related("roles_permitidos", "roles_permitidos__carreras")
                )

                valid_process_details: List[str] = []

                for proc in all_processes:
                    is_proc_allowed = False

                    if not proc.roles_permitidos.exists():
                        is_proc_allowed = True
                    else:
                        for rol_config in proc.roles_permitidos.all():
                            if rol_config.id not in user_matched_role_ids:
                                continue

                            carreras_del_rol = rol_config.carreras.all()
                            if not carreras_del_rol.exists():
                                is_proc_allowed = True
                                break

                            if any(c.id in user_carrera_ids for c in carreras_del_rol):
                                is_proc_allowed = True
                                break

                    if is_proc_allowed:
                        desc = (proc.business_context or "Sin descripción").replace("\n", " ").strip()
                        valid_process_details.append(
                            f'FUNCTION_NAME: "{proc.nombre}"\nSCOPE: "{desc}"\n\n'
                        )

                # Tool humano (siempre)
                valid_process_details.append(
                    'FUNCTION_NAME: "HUMAN_HANDOFF"\n'
                    'SCOPE: "Use when the user asks to contact/support with a human agent, advisor, or staff."\n\n'
                )

                

                # -------------------------------------------------------------
                # 4) Router: decidir acción (FUNCTION / ANSWER / OFF_TOPIC)
                # -------------------------------------------------------------
                action = "ANSWER"
                found_process_name = None

                if valid_process_details:
                    # Inyectamos también el proceso actual (si viene desde el frontend)
                    active_label = (
                        current_process
                        or "MAIN MENU (No specific process selected)"
                    )
                    system_instruction = (
                        f"[ACTIVE_PROCESS]{active_label}[/ACTIVE_PROCESS]\n"
                        "[TOOLS_LIST]\n"
                        + "\n".join(valid_process_details)
                        + "\n[END_TOOLS_LIST]"
                    )
                else:
                    system_instruction = "NO_TOOLS_AVAILABLE"

                # Normalizar historial para el Router
                router_history = _normalize_history(_history, max_items=6)
                
                # Evitar duplicar si el frontend ya incluyó el mismo mensaje actual en history
                if router_history and router_history[-1]["role"] == "user" and router_history[-1]["content"].strip() == user_msg.strip():
                    router_history = router_history[:-1]

                payload_router = {
                    "messages": (
                        [{"role": "system", "content": system_instruction}]
                        + router_history
                        + [{"role": "user", "content": user_msg}]
                    ),
                    "use_context": False,
                    "stream": False,
                }

                try:
                    print("DEBUG: --- PAYLOAD ROUTER ---")
                    print(f"DEBUG: Tools count: {len(valid_process_details)}")

                    r = requests.post(
                        f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions",
                        json=payload_router,
                        timeout=None,
                    )
                    raw_content = r.json()["choices"][0]["message"]["content"]
                    print(f"DEBUG: --- RESPUESTA ROUTER RAW ---\n{raw_content}\n-------------------------------")

                    data_router = _safe_parse_router_output(raw_content)

                    server_action = data_router.get("action", "ANSWER")
                    server_func = data_router.get("function_name")
                    server_response = data_router.get("response", "") or ""
                    
                    # 1. Mapeo explícito de clasificaciones nuevas
                    router_class = data_router.get("classification")
                    if not router_class:
                        # Fallback si el parser usa 'action' o 'function_name'
                        if server_func == "OFF_TOPIC":
                            router_class = "OFF_TOPIC"
                        else:
                            router_class = server_action

                    # Manejo de OFF_TOPIC
                    if router_class == "OFF_TOPIC":
                        action = "OFF_TOPIC"
                    
                    # Manejo de AMBIGUOUS
                    elif router_class == "AMBIGUOUS":
                        # Permitimos la "clarification" porque el prompt ya filtró las tonterías
                        clarification_text = data_router.get("clarification") or server_response
                        yield json.dumps({
                            "type": "final",
                            "data": {
                                "response": clarification_text or "¿Podrías darme más detalles sobre tu consulta académica?",
                                "sources": [],
                                "action": "ANSWER",
                                "is_function": False,
                                "offer_human_handoff": False
                            }
                        }) + "\n"
                        return
                    
                    # Manejo de FUNCTION
                    elif router_class == "FUNCTION" or server_action == "FUNCTION":
                        action = "FUNCTION"
                        found_process_name = server_func

                    # Manejo de RAG o respuestas directas
                    elif router_class == "RAG" or "RAG_MODE" in server_response:
                        action = "ANSWER"  # seguirá a RAG abajo
                    
                    # Respuesta directa del router (saludo / etc)
                    else:
                        yield json.dumps(
                            {
                                "type": "final",
                                "data": {
                                    "response": server_response,
                                    "sources": [],
                                    "action": "ANSWER",
                                    "is_function": False,
                                    "offer_human_handoff": False,
                                },
                            }
                        ) + "\n"
                        return

                except Exception as e:
                    logger.error("Error router connection/parsing: %s", e)
                    action = "ANSWER"

                # -------------------------------------------------------------
                # 5) Ejecutar acción
                # -------------------------------------------------------------
                if action == "OFF_TOPIC":
                    yield json.dumps(
                        {
                            "type": "final",
                            "data": {
                                # Respuesta estándar y cerrada. No le seguimos el juego.
                                "response": "Lo siento, soy un asistente académico de la UNEMI y no tengo información sobre ese tema. ¿Puedo ayudarte con alguna consulta sobre matrículas, procesos o reglamentos?",
                                "sources": [],
                                "action": "ANSWER",
                                "is_function": False,
                                "offer_human_handoff": False,
                            },
                        }
                    ) + "\n"
                    return

                if action == "FUNCTION":
                    # HUMAN_HANDOFF: abre modal
                    if found_process_name == "HUMAN_HANDOFF":
                        request.session[SESSION_HANDOFF_PENDING_KEY] = True
                        request.session.modified = True

                        yield json.dumps(
                            {
                                "type": "final",
                                "data": {
                                    "response": (
                                        "Entendido 😊 Enviaré tu solicitud a mis compañeros humanos. "
                                        "Por favor cuéntame tu caso de nuevo y, si tienes evidencia, adjúntala (opcional)."
                                    ),
                                    "sources": [],
                                    "is_function": True,
                                    "action": "FUNCTION",
                                    "payload": {
                                        "status": "success",
                                        "need_documentation": True,
                                        "upload_optional": True,
                                        "handoff_mode": True,
                                    },
                                    "offer_human_handoff": False,
                                },
                            }
                        ) + "\n"
                        return

                    # Proceso real
                    # Primero validamos que exista en BD
                    proc_check = BusinessProcess.objects.filter(
                        nombre=found_process_name, status=True
                    ).first()

                    if not proc_check:
                        # Si el router alucinó un nombre que no existe, fallback a RAG
                        action = "ANSWER"
                    else:
                        # Validar fechas (misma lógica que tenías antes)
                        if not _is_process_active_by_date(proc_check):
                            closed_msg = (proc_check.closed_message or "").strip() or (
                                f"El proceso {proc_check.nombre} no se encuentra habilitado en el rango de fechas actual."
                            )
                            header_msg = f"⚠️ AVISO: {proc_check.nombre}\n{closed_msg}"

                            yield json.dumps(
                                {"type": "status", "text": "Interpretando consulta..."}
                            ) + "\n"
                            yield from execute_rag(
                                query_text=user_msg,
                                allowed_ids=doc_ids_for_pgpt,
                                original_query=user_msg,
                                forced_intro_text=header_msg,
                            )
                            return

                        # === CAMBIO CLAVE: pasamos roles y carreras detectados ===
                        res = get_process_response_from_db(
                            found_process_name,
                            user_role_ids=user_matched_role_ids,
                            user_carrera_ids=user_carrera_ids,
                        )

                        # Si devolvió unauthorized, mostramos el mensaje y no ejecutamos función
                        if res.get("status") == "unauthorized":
                            yield json.dumps(
                                {
                                    "type": "final",
                                    "data": {
                                        "response": res["text"],
                                        "sources": [],
                                        "action": "ANSWER",
                                        "is_function": False,
                                        "offer_human_handoff": False,
                                    },
                                }
                            ) + "\n"
                            return

                        # Flujo normal si todo está bien
                        sources = []
                        if res.get("source_url"):
                            sources.append(
                                {
                                    "title": f"{found_process_name}",
                                    "url": res.get("source_url"),
                                }
                            )

                        yield json.dumps(
                            {
                                "type": "final",
                                "data": {
                                    "response": res.get("text", ""),
                                    "sources": sources,
                                    "is_function": True,
                                    "action": "FUNCTION",
                                    "payload": res,
                                    "offer_human_handoff": False,
                                },
                            }
                        ) + "\n"
                        return

                # -------------------------------------------------------------
                # 6) RAG (con reformulación silenciosa)
                # -------------------------------------------------------------
                # -------------------------------------------------------------
                # 6) RAG (Optimizado: Sin reformulación extra)
                # -------------------------------------------------------------
                if action == "ANSWER":
                    if not doc_ids_for_pgpt:
                        yield json.dumps(
                            {
                                "type": "final",
                                "data": {
                                    "response": "Lo siento, no se encontraron normativas habilitadas para tu perfil en este momento.",
                                    "sources": [],
                                    "action": "ANSWER",
                                    "is_function": False,
                                    "offer_human_handoff": False,
                                },
                            }
                        ) + "\n"
                        return

                    yield json.dumps({"type": "status", "text": "Interpretando consulta..."}) + "\n"

                    # --- CAMBIO CRÍTICO AQUÍ ---
                    # 1. Intentamos usar la query que ya nos dio el Router (chat_service)
                    # data_router fue parseado más arriba en el paso 4
                    optimized_query = data_router.get("reformulated_query")

                    # 2. Si por alguna razón vino vacía, usamos el mensaje original del usuario
                    if not optimized_query:
                        optimized_query = user_msg
                        print(f"ℹ️ RAG: Usando query original: '{user_msg}'")
                    else:
                        print(f"🚀 RAG: Usando query pre-optimizada: '{optimized_query}'")

                    # 3. ¡Ejecutamos RAG directamente! (Ahorramos 1 minuto de espera)
                    yield from execute_rag(
                        query_text=optimized_query,
                        allowed_ids=doc_ids_for_pgpt,
                        original_query=user_msg,
                    )
                    return

                    yield json.dumps({"type": "status", "text": "Interpretando consulta..."}) + "\n"

                    optimized_query = user_msg
                    reform_payload = {
                        "messages": [
                            {"role": "system", "content": "REFORMULATE_QUERY_MODE"},
                            {"role": "user", "content": user_msg},
                        ],
                        "stream": False,
                        "temperature": 0.1,
                        "use_context": False,
                    }

                    try:
                        r_ref = requests.post(
                            f"{settings.PRIVATE_GPT_API_URL}/v1/chat/completions",
                            json=reform_payload,
                            timeout=600,
                        )
                        if r_ref.status_code == 200:
                            content = r_ref.json()["choices"][0]["message"]["content"]
                            clean_content = (content or "").strip().replace('"', "").replace("Output:", "").strip()
                            if len(clean_content) > 5:
                                optimized_query = clean_content
                                print(f"🔄 REFORMULACIÓN INTERNA: '{user_msg}' -> '{optimized_query}'")
                    except Exception as e:
                        logger.error("Error reformulación silenciosa: %s", e)

                    yield from execute_rag(
                        query_text=optimized_query,
                        allowed_ids=doc_ids_for_pgpt,
                        original_query=user_msg,
                    )
                    return

            except Exception as e:
                logger.exception("Error stream: %s", e)
                yield json.dumps({"type": "error", "text": "Error interno."}) + "\n"

        return StreamingHttpResponse(event_stream(), content_type="application/x-ndjson")


# ==============================================================================
# 4. Gestión documental
# ==============================================================================

def document_manager(request):
    documents = RagDocument.objects.filter(status=True).order_by("-fecha_creacion")
    processes = BusinessProcess.objects.filter(status=True).select_related("process_type").order_by("-fecha_creacion")

    chatbot_roles = (
        ChatbotRol.objects.filter(status=True)
        .prefetch_related("carreras")
        .annotate(
            is_general=Case(
                When(nombre__icontains="General", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("is_general", "nombre")
    )

    tipos_catalogo = get_dynamic_sga_roles()
    carreras_reales = SgaCarrera.objects.all().values("id", "nombre").order_by("nombre")
    process_types = BusinessProcessType.objects.filter(status=True).order_by("nombre")

    return render(
        request,
        "chatbot/document_manager.html",
        {
            "documents": documents,
            "processes": processes,
            "chatbot_roles": chatbot_roles,
            "tipos_base": tipos_catalogo,
            "carreras_list": carreras_reales,
            "process_types": process_types,
        },
    )


def validate_pdf_has_text(
    uploaded_file,
    *,
    sample_pages: int = 10,
    min_words_per_page: int = 20,
    min_text_pages_ratio: float = 0.30,
) -> Tuple[bool, dict]:
    """
    Valida si un PDF tiene texto seleccionable (no solo escaneado).
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return False, {"reason": "Falta instalar PyMuPDF (pymupdf)."}

    try:
        pdf_bytes = uploaded_file.read()
        uploaded_file.seek(0)
    except Exception:
        return False, {"reason": "No se pudo leer el archivo subido."}

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return False, {"reason": "El archivo no parece un PDF válido o está corrupto."}

    if doc.page_count <= 0:
        return False, {"reason": "El PDF no tiene páginas."}

    pages_to_check = min(doc.page_count, sample_pages)
    word_re = re.compile(r"\b\w+\b", re.UNICODE)

    word_counts = []
    img_counts = []

    for i in range(pages_to_check):
        page = doc.load_page(i)
        text = (page.get_text("text") or "").strip()
        words = len(word_re.findall(text))
        word_counts.append(words)

        imgs = page.get_images(full=True) or []
        img_counts.append(len(imgs))

    text_pages = sum(1 for w in word_counts if w >= min_words_per_page)
    text_ratio = text_pages / pages_to_check

    details = {
        "page_count": doc.page_count,
        "checked_pages": pages_to_check,
        "total_words_in_sample": sum(word_counts),
        "avg_words_per_page": (sum(word_counts) / pages_to_check) if pages_to_check else 0,
        "text_pages": text_pages,
        "text_ratio": text_ratio,
        "total_images_in_sample": sum(img_counts),
    }

    if text_ratio < min_text_pages_ratio:
        if details["total_images_in_sample"] > 0:
            return False, {**details, "reason": "Parece un PDF escaneado (solo imágenes) o sin texto seleccionable."}
        return False, {**details, "reason": "El PDF casi no contiene texto seleccionable."}

    return True, details


def upload_document(request):
    if request.method != "POST":
        return redirect("chatbot:document_manager")

    files = request.FILES.getlist("file")
    role_ids = request.POST.getlist("roles")
    is_inf = request.POST.get("is_infinite") == "on"
    v_from = request.POST.get("valid_from") or None
    v_to = request.POST.get("valid_to") or None

    count = 0
    skip = 0

    ingest_url = f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/file"

    try:
        for f in files:
            is_ok, info = validate_pdf_has_text(f, sample_pages=10)
            if not is_ok:
                reason = info.get("reason", "PDF inválido.")
                checked = info.get("checked_pages")
                avg = info.get("avg_words_per_page", 0)
                messages.error(
                    request,
                    f"'{f.name}' no es válido para RAG: {reason} (muestreo {checked} pág, prom {avg:.1f} palabras/pág).",
                )
                skip += 1
                continue

            if RagDocument.objects.filter(nombre=f.name, status=True).exists():
                skip += 1
                continue

            # guardar en BD local
            doc_db = RagDocument(
                archivo=f,
                nombre=f.name,
                is_infinite=is_inf,
                valid_from=v_from,
                valid_to=v_to,
                is_indexed=False,
            )
            doc_db.save(request)

            if role_ids:
                doc_db.roles_permitidos.set(role_ids)

            # enviar a PrivateGPT
            try:
                with doc_db.archivo.open("rb") as local_file:
                    target_url_with_id = f"{ingest_url}?db_id={doc_db.id}"
                    r = requests.post(
                        target_url_with_id,
                        files={"file": (doc_db.nombre, local_file, "application/pdf")},
                        timeout=None,
                    )

                if r.status_code == 200:
                    resp_data = r.json().get("data", [])
                    if resp_data:
                        pgpt_id = resp_data[0]["doc_id"]
                        doc_db.doc_id_pgpt = pgpt_id
                        doc_db.is_indexed = True
                        doc_db.save(request)

                        meta_payload = {
                            "roles": role_ids,
                            "is_infinite": is_inf,
                            "valid_from": v_from,
                            "valid_to": v_to,
                            "db_id": doc_db.id,
                            "access_url": doc_db.archivo.url if doc_db.archivo else None,
                        }
                        try:
                            requests.post(
                                f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{pgpt_id}/metadata",
                                json=meta_payload,
                                timeout=None,
                            )
                        except Exception:
                            pass

                count += 1

            except requests.exceptions.ConnectTimeout:
                logger.error("Timeout conectando a IA")
                messages.warning(request, f"El archivo {f.name} se guardó localmente, pero la IA no respondió a tiempo.")
            except requests.exceptions.ConnectionError:
                logger.error("No se puede conectar a IA")
                messages.error(request, f"Error de conexión con la IA para {f.name}.")
            except Exception as e:
                logger.error("Error indexando en IA: %s", e)

        msg = f"Se subieron {count} archivos."
        if skip > 0:
            msg += f" (Se omitieron {skip} duplicados o inválidos)."
        messages.success(request, msg)

    except Exception as e:
        messages.error(request, f"Error crítico: {e}")

    return redirect("chatbot:document_manager")


def delete_document(request, doc_id):
    if request.method != "POST":
        return redirect("chatbot:document_manager")

    try:
        doc = RagDocument.objects.get(id=doc_id)

        if doc.doc_id_pgpt:
            try:
                api_url = f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{doc.doc_id_pgpt}"
                requests.delete(api_url, timeout=None)
            except Exception as e:
                logger.error("Error de conexión al borrar de IA: %s", e)

        if doc.archivo:
            doc.archivo.delete(save=False)

        doc.delete()
        messages.success(request, f"Documento '{doc.nombre}' eliminado completamente.")

    except RagDocument.DoesNotExist:
        messages.error(request, "El documento no existe.")
    except Exception as e:
        messages.error(request, f"Error eliminando documento: {e}")

    return redirect("chatbot:document_manager")


def update_document_role(request, doc_id):
    if request.method != "POST":
        return redirect("chatbot:document_manager")

    try:
        role_ids = request.POST.getlist("roles")
        is_inf = request.POST.get("is_infinite") == "on"
        v_from = request.POST.get("valid_from") or None
        v_to = request.POST.get("valid_to") or None

        doc = RagDocument.objects.get(id=doc_id)
        doc.roles_permitidos.set(role_ids)
        doc.is_infinite = is_inf
        doc.valid_from = v_from
        doc.valid_to = v_to
        doc.save(request)

        if doc.doc_id_pgpt:
            payload = {
                "db_id": doc.id,
                "file_name": doc.nombre,
                "roles": role_ids,
                "is_infinite": is_inf,
                "valid_from": v_from,
                "valid_to": v_to,
                "access_url": doc.archivo.url if doc.archivo else None,
            }
            requests.post(
                f"{settings.PRIVATE_GPT_API_URL}/v1/ingest/{doc.doc_id_pgpt}/metadata",
                json=payload,
                timeout=None,
            )

        messages.success(request, "Documento actualizado.")

    except RagDocument.DoesNotExist:
        messages.error(request, "Documento no encontrado.")
    except Exception as e:
        messages.error(request, f"Error actualizando: {e}")

    return redirect("chatbot:document_manager")


# ==============================================================================
# 5. Gestión de procesos (BusinessProcess)
# ==============================================================================

@require_http_methods(["GET"])
def process_manager(request):
    return redirect("chatbot:document_manager")


@require_http_methods(["POST"])
def create_process(request):
    try:
        name_input = request.POST.get("name")
        type_id = request.POST.get("process_type")
        process_type_obj = get_object_or_404(BusinessProcessType, id=type_id)

        source_url = request.POST.get("source_url")
        business_context = request.POST.get("business_context")
        active_msg = request.POST.get("active_message")
        is_infinite = request.POST.get("is_infinite") == "on"
        need_documentation = request.POST.get("need_documentation") == "on"

        start_date = request.POST.get("start_date") or None
        end_date = request.POST.get("end_date") or None

        if is_infinite:
            now = timezone.now().date()
            start_date = now
            end_date = now

        has_closed = request.POST.get("has_closed_message") == "on"
        closed_msg = request.POST.get("closed_message") if has_closed else None

        role_ids = request.POST.getlist("roles")

        proc = BusinessProcess.objects.create(
            nombre=name_input,
            process_type=process_type_obj,
            source_url=source_url,
            is_infinite=is_infinite,
            business_context=business_context,
            closed_message=closed_msg,
            need_documentation=need_documentation,
            start_date=start_date,
            end_date=end_date,
            active_message=active_msg,
            status=True,
        )

        if role_ids:
            proc.roles_permitidos.set(role_ids)

        messages.success(request, "Proceso creado correctamente.")

    except Exception as e:
        messages.error(request, f"Error al crear: {e}")

    return redirect("chatbot:process_manager")


@require_http_methods(["POST"])
def delete_process(request, process_id):
    try:
        proc = BusinessProcess.objects.get(id=process_id)
        proc.status = False
        proc.save()
        messages.success(request, "Proceso eliminado.")
    except BusinessProcess.DoesNotExist:
        messages.error(request, "Proceso no encontrado.")
    except Exception as e:
        messages.error(request, f"Error: {e}")

    return redirect("chatbot:process_manager")


@require_http_methods(["POST"])
def edit_process(request, process_id):
    try:
        proc = BusinessProcess.objects.get(id=process_id)

        proc.nombre = request.POST.get("name")
        proc.business_context = request.POST.get("business_context")

        type_id = request.POST.get("process_type")
        if type_id:
            proc.process_type = get_object_or_404(BusinessProcessType, id=type_id)

        proc.source_url = request.POST.get("source_url") or None

        proc.is_infinite = request.POST.get("is_infinite") in ["on", "true", "1", "True"]
        proc.need_documentation = request.POST.get("need_documentation") in ["on", "true", "1", "True"]

        start_date = request.POST.get("start_date") or None
        end_date = request.POST.get("end_date") or None

        if proc.is_infinite:
            today = timezone.now().date()
            proc.start_date = today
            proc.end_date = today
        else:
            proc.start_date = start_date
            proc.end_date = end_date

        proc.active_message = request.POST.get("active_message")

        has_closed_msg = request.POST.get("has_closed_message") == "on"
        proc.closed_message = request.POST.get("closed_message") if has_closed_msg else None

        role_ids = request.POST.getlist("roles")
        proc.roles_permitidos.set(role_ids)

        proc.save()
        messages.success(request, "Proceso actualizado.")

    except Exception as e:
        messages.error(request, f"Error: {e}")

    return redirect("chatbot:process_manager")


# ==============================================================================
# 6. Subida de documentación (Handoff)  ✅ archivo opcional
# ==============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def upload_documentation(request):
    """
    Endpoint para finalizar la derivación humana:
    - acepta details (texto) y file (opcional)
    - limpia handoff_pending
    """
    try:
        extra_details = (request.POST.get("details", "") or "").strip()
        uploaded_file = request.FILES.get("file")  # opcional

        file_url = None
        if uploaded_file:
            storage = FileSystemStorage(
                location=os.path.join(settings.MEDIA_ROOT, "balcon_docs"),
                base_url=settings.MEDIA_URL + "balcon_docs/",
            )
            filename = storage.save(uploaded_file.name, uploaded_file)
            file_url = request.build_absolute_uri(storage.url(filename))

        # limpia estado de sesión (clave para que el flujo no se quede pegado)
        request.session.pop(SESSION_HANDOFF_PENDING_KEY, None)
        request.session.modified = True

        mensaje_para_usuario = (
            "Perfecto. Ya envié tu solicitud a mis compañeros humanos. "
            "¿Hay algo más en lo que te pueda ayudar?"
        )

        return JsonResponse(
            {
                "status": "success",
                "message": "Solicitud recibida correctamente.",
                "file_url": file_url,
                "ai_response": mensaje_para_usuario,
            }
        )

    except Exception as e:
        logger.exception("Error subiendo documentación: %s", e)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ==============================================================================
# 7. Gestión de tipos de proceso
# ==============================================================================

@require_POST
def create_process_type(request):
    try:
        nombre = request.POST.get("nombre")
        req_docs = request.POST.get("requiere_documentacion") == "on"

        BusinessProcessType.objects.create(
            nombre=nombre, requiere_documentacion_por_defecto=req_docs
        )
        messages.success(request, "Tipo de proceso creado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al crear tipo: {e}")

    return redirect("chatbot:document_manager")


@require_POST
def edit_process_type(request, type_id):
    pt = get_object_or_404(BusinessProcessType, id=type_id)
    try:
        pt.nombre = request.POST.get("nombre")
        pt.requiere_documentacion_por_defecto = request.POST.get("requiere_documentacion") == "on"
        pt.save()
        messages.success(request, "Tipo actualizado.")
    except Exception as e:
        messages.error(request, f"Error al actualizar: {e}")

    return redirect("chatbot:document_manager")


@require_POST
def delete_process_type(request, type_id):
    pt = get_object_or_404(BusinessProcessType, id=type_id)
    try:
        pt.delete()  # PROTECT si está en uso
        messages.success(request, "Tipo eliminado.")
    except Exception:
        messages.error(request, "No se puede eliminar este tipo porque hay procesos que lo utilizan.")

    return redirect("chatbot:document_manager")
