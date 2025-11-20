import json
import re
import logging
from django.conf import settings
from langchain_ollama import ChatOllama

# Configuración de Logging
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DEL LLM ---
llm = ChatOllama(
    model=settings.OLLAMA_MODEL,
    format=settings.OLLAMA_FORMAT,
    temperature=settings.OLLAMA_TEMPERATURE,
    keep_alive="1h",
    num_predict=settings.OLLAMA_NUM_PREDICT,
    base_url=settings.OLLAMA_BASE_URL,
    num_ctx=settings.OLLAMA_NUM_CTX,
    num_thread=settings.OLLAMA_NUM_THREAD,
)

# --- PROMPT "INDUSTRIAL" (Sin cambios) ---
SYSTEM_PROMPT = """YOU ARE A STRICT DATA EXTRACTOR.
Output JSON only.

VALID INTENT_CODES:
- "consultar_solicitudes_balcon" (Only for checking STATUS of requests)
- "consultar_datos_personales" (Only for name, email, id)
- "consultar_carrera_actual" (Only for 'what is my major')
- "consultar_roles_usuario" (Only for 'what is my role')
- "otro" (USE THIS FOR ALL OTHER ACTIONS: solicitar, justificar, inscribir, cambiar, anular, pagar)

JSON SCHEMA:
{
  "intent_code": "string",
  "accion": "string (infinitive verb)",
  "objeto": "string (noun)",
  "asignatura": "string or null",
  "unidad_actividad": "string or null",
  "periodo": "string or null",
  "carrera": "string or null",
  "detalle": "string or null",
  "multi_intent": boolean,
  "intents": []
}

*** EXAMPLES (FOLLOW THIS PATTERN) ***

Input: "Quiero ver mis notas de calculo"
Output:
{
  "intent_code": "otro", "accion": "consultar", "objeto": "notas", "asignatura": "calculo", "multi_intent": false, "intents": []
}

Input: "Necesito justificar una falta y solicitar cambio de paralelo"
Output:
{
  "intent_code": "otro",
  "accion": "justificar",
  "objeto": "falta",
  "multi_intent": true,
  "intents": [
    {"intent_code": "otro", "accion": "justificar", "objeto": "falta"},
    {"intent_code": "otro", "accion": "solicitar", "objeto": "cambio de paralelo"}
  ]
}

Input: "Cual es mi carrera actual"
Output:
{
  "intent_code": "consultar_carrera_actual", "accion": "consultar", "objeto": "carrera", "multi_intent": false, "intents": []
}

*** END EXAMPLES ***

RULES:
1. If action is 'solicitar', 'cambiar', 'justificar' -> CODE IS ALWAYS "otro".
2. Do not invent new codes like "solicitar_cambio".
"""

def procesar_mensaje_usuario(texto_usuario: str) -> dict:
    # 1. Filtro de saludo rápido
    if _es_saludo_simple(texto_usuario):
        return _respuesta_rapida("saludo", texto_usuario)

    try:
        # 2. Llamada al LLM
        prompt = f"{SYSTEM_PROMPT}\nInput: \"{texto_usuario}\"\nOutput:"
        
        response = llm.invoke(prompt)
        raw_content = response.content.strip()

        # 3. Extracción de JSON
        match = re.search(r"\{[\s\S]*\}", raw_content)
        if not match:
            logger.warning(f"JSON no encontrado: {raw_content[:50]}")
            return _respuesta_rapida("error_formato", texto_usuario)
            
        json_str = match.group(0)
        data = json.loads(json_str)

        # 4. Normalización (AQUÍ OCURRE LA LÓGICA DE AGENTE)
        return _normalizar_salida(data, texto_usuario)

    except Exception as e:
        logger.error(f"Error critico: {str(e)}")
        return _respuesta_rapida("error_sistema", texto_usuario)


def _normalizar_salida(data: dict, original_text: str) -> dict:
    base = {
        "intent_code": "otro",
        "accion": "", "objeto": "", "asignatura": "", "unidad_actividad": "",
        "periodo": "", "carrera": "", "sistema": "", "detalle": "",
        "answer_type": "informativo",
        "agent_handoff": False, # Nuevo campo: Indica si pasa a humano
        "system_response": "",  # Nuevo campo: Mensaje listo para mostrar
        "multi_intent": False, "intents": [], "original_text": original_text
    }

    for k, v in data.items():
        if k in base and v is not None:
            base[k] = v

    # --- 1. CLASIFICAR TIPO DE RESPUESTA ---
    base["answer_type"] = _inferir_tipo_respuesta(base["intent_code"], base["accion"], original_text)

    # --- 2. LÓGICA DE AGENTE (Handoff) ---
    # Si es OPERATIVO, generamos el mensaje de contacto aquí mismo
    if base["answer_type"] == "operativo":
        base["agent_handoff"] = True
        # Construimos un mensaje natural usando los datos extraídos
        accion_txt = base.get('accion', 'procesar')
        objeto_txt = base.get('objeto', 'tu solicitud')
        base["system_response"] = (
            f"Entendido. Para gestionar tu solicitud de **{accion_txt} {objeto_txt}**, "
            "un agente especializado se pondrá en contacto contigo en breve."
        )

    # --- 3. PROCESAR MULTI-INTENT ---
    if base["multi_intent"] and isinstance(base.get("intents"), list):
        clean_intents = []
        for item in base["intents"]:
            sub = {
                "intent_code": item.get("intent_code", "otro"),
                "accion": item.get("accion", ""),
                "objeto": item.get("objeto", ""),
                "asignatura": item.get("asignatura", ""),
                "answer_type": "informativo",
                "agent_handoff": False,
                "system_response": ""
            }
            
            # Validar códigos
            valid_codes = ["consultar_solicitudes_balcon", "consultar_datos_personales", "consultar_carrera_actual", "consultar_roles_usuario", "otro"]
            if sub["intent_code"] not in valid_codes:
                sub["intent_code"] = "otro"
            
            # Inferir tipo para sub-intent
            sub["answer_type"] = _inferir_tipo_respuesta(sub["intent_code"], sub["accion"], "")
            
            # Lógica de agente para sub-intent
            if sub["answer_type"] == "operativo":
                sub["agent_handoff"] = True
                accion_sub = sub.get('accion', 'realizar')
                objeto_sub = sub.get('objeto', 'trámite')
                sub["system_response"] = (
                    f"Sobre tu requerimiento de **{accion_sub} {objeto_sub}**, "
                    "he notificado a un asesor para que te ayude personalmente."
                )

            clean_intents.append(sub)
        base["intents"] = clean_intents
    else:
        base["intents"] = []

    return base

def _inferir_tipo_respuesta(code: str, accion: str, texto_raw: str) -> str:
    """Reglas de negocio para decidir entre RAG (informativo) o AGENTE (operativo)."""
    # Consultas de lectura rápida -> Informativo
    if code in ["consultar_datos_personales", "consultar_carrera_actual", "consultar_roles_usuario", "consultar_solicitudes_balcon"]:
        return "informativo"

    accion = accion.lower().strip()
    texto = texto_raw.lower().strip()

    # Verbos que requieren acción humana
    verbos_operativos = [
        "solicitar", "cambiar", "justificar", "inscribir", "anular", 
        "pagar", "subir", "rectificar", "retirar", "crear", "actualizar",
        "homologar", "convalidar", "recalificar", "tramitar"
    ]
    
    es_verbo_operativo = any(v in accion for v in verbos_operativos)

    # Si pregunta "¿Cómo...?", es informativo (RAG), aunque el verbo sea operativo
    indicadores_pregunta = ["como ", "cómo ", "requisitos", "pasos", "donde ", "cuándo ", "por qué"]
    es_pregunta_como = any(i in texto for i in indicadores_pregunta)

    if es_pregunta_como:
        return "informativo"
    
    if es_verbo_operativo:
        return "operativo"

    return "informativo"

def _es_saludo_simple(texto: str) -> bool:
    t = re.sub(r"[^\w\s]", "", texto.lower()).strip()
    return len(t.split()) < 3 and any(w in ["hola", "buenas", "hi", "alo"] for w in t.split())

def _respuesta_rapida(tipo: str, texto: str) -> dict:
    return {
        "intent_code": "saludo" if tipo == "saludo" else "otro", 
        "answer_type": "informativo",
        "agent_handoff": False,
        "system_response": "¡Hola! Soy el asistente virtual de UNEMI. ¿En qué puedo ayudarte hoy?",
        "original_text": texto, 
        "multi_intent": False, 
        "intents": []
    }