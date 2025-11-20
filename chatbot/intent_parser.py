import json
import re
import logging
from django.conf import settings
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DEL LLM ---
llm = ChatOllama(
    model=settings.OLLAMA_MODEL,
    format="json",  # JSON Mode Mandatory
    temperature=0, 
    keep_alive="1h",
    num_predict=settings.OLLAMA_NUM_PREDICT,
    base_url=settings.OLLAMA_BASE_URL,
    num_ctx=settings.OLLAMA_NUM_CTX,
    num_thread=settings.OLLAMA_NUM_THREAD,
)

# --- PROMPT "INDUSTRIAL ROUTER" (FULL ENGLISH) ---
SYSTEM_PROMPT = """YOU ARE AN INTELLIGENT INTENT CLASSIFIER.
Analyze the user's request (which is in Spanish) and extract structured data in JSON.

YOUR PRIMARY GOAL IS TO CLASSIFY "answer_type":
1. "informational": User wants to KNOW something, asks for "how to", requirements, steps, status, dates, or definitions.
2. "operational": User wants to DO something immediately that requires human intervention (e.g., change, cancel, register, upload, justify).

VALID INTENT_CODES:
- "consultar_solicitudes_balcon" (Checking status)
- "consultar_datos_personales" (Personal info)
- "consultar_carrera_actual" (Academic info)
- "consultar_roles_usuario" (User role)
- "otro" (Any other action)

JSON SCHEMA:
{
  "intent_code": "string",
  "accion": "string (verb in Spanish)",
  "objeto": "string (noun in Spanish)",
  "asignatura": "string or null",
  "answer_type": "informational | operational", 
  "multi_intent": boolean,
  "intents": []
}

*** EXAMPLES ***

Input: "Quiero ver mis notas"
Output: {"intent_code": "otro", "accion": "consultar", "objeto": "notas", "answer_type": "informational", "multi_intent": false, "intents": []}

Input: "Necesito justificar una falta urgente"
Output: {"intent_code": "otro", "accion": "justificar", "objeto": "falta", "answer_type": "operational", "multi_intent": false, "intents": []}

Input: "¿Cómo se justifica una falta?"
Output: {"intent_code": "otro", "accion": "justificar", "objeto": "falta", "answer_type": "informational", "multi_intent": false, "intents": []}
(Reason: User asks 'HOW', so it is informational, not an action request).

Input: "Solicitar cambio de carrera"
Output: {"intent_code": "otro", "accion": "solicitar", "objeto": "cambio de carrera", "answer_type": "operational", "multi_intent": false, "intents": []}

*** END EXAMPLES ***

RULES:
1. Questions starting with "Como", "Donde", "Requisitos" are ALWAYS "informational".
2. Direct action commands are "operational".
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

        # 4. Normalización
        return _normalizar_salida(data, texto_usuario)

    except Exception as e:
        logger.error(f"Error critico: {str(e)}")
        return _respuesta_rapida("error_sistema", texto_usuario)


def _normalizar_salida(data: dict, original_text: str) -> dict:
    base = {
        "intent_code": "otro",
        "accion": "", "objeto": "", "asignatura": "",
        "answer_type": "informational", # Default en Inglés
        "agent_handoff": False,
        "system_response": "",
        "multi_intent": False, "intents": [], "original_text": original_text
    }

    # Copiar datos del LLM
    for k, v in data.items():
        if k in base and v is not None:
            base[k] = v

    # --- PYTHON GUARDRAIL (Safety Check) ---
    # Aunque el LLM piense en inglés, el input es español. 
    # Reforzamos la regla de preguntas "Cómo/Dónde".
    indicadores_pregunta = ["como ", "cómo ", "requisitos", "pasos", "donde ", "cuándo ", "que necesito"]
    if any(i in original_text.lower() for i in indicadores_pregunta):
        base["answer_type"] = "informational"

    # --- LÓGICA DE NEGOCIO (HANDOFF) ---
    # Ahora verificamos la etiqueta en INGLÉS
    if base["answer_type"] == "operational":
        base["agent_handoff"] = True
        accion = base.get('accion', 'tu solicitud')
        objeto = base.get('objeto', '')
        base["system_response"] = (
            f"Entendido. He derivado tu solicitud de **{accion} {objeto}** a un asesor humano. "
            "Te contactarán en breve para completar el proceso."
        )

    # --- PROCESAMIENTO DE MULTI-INTENT ---
    if base["multi_intent"] and isinstance(base.get("intents"), list):
        clean_intents = []
        for item in base["intents"]:
            sub = base.copy()
            sub.update(item)
            sub["multi_intent"] = False
            sub["intents"] = []
            
            # Guardrail recursivo
            # Si el sub-intent fue marcado como operational por el LLM
            if sub["answer_type"] == "operational":
                sub["agent_handoff"] = True
                acc = sub.get('accion', 'solicitud')
                obj = sub.get('objeto', '')
                sub["system_response"] = f"Sobre **{acc} {obj}**: He notificado a un agente."
            
            clean_intents.append(sub)
        base["intents"] = clean_intents
    else:
        base["intents"] = []

    return base


def _es_saludo_simple(texto: str) -> bool:
    t = re.sub(r"[^\w\s]", "", texto.lower()).strip()
    return len(t.split()) < 3 and any(w in ["hola", "buenas", "hi", "alo"] for w in t.split())

def _respuesta_rapida(tipo: str, texto: str) -> dict:
    return {
        "intent_code": "saludo" if tipo == "saludo" else "otro",
        "answer_type": "informational",
        "agent_handoff": False,
        "system_response": "¡Hola! Soy el asistente virtual de UNEMI. ¿En qué puedo ayudarte?",
        "original_text": texto, "multi_intent": False, "intents": []
    }
