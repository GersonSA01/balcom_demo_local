import json
import re
import logging
from django.conf import settings
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DEL LLM ---
llm = ChatOllama(
    model=settings.OLLAMA_MODEL,
    format="json",
    temperature=0, 
    keep_alive="1h",
    num_predict=settings.OLLAMA_NUM_PREDICT,
    base_url=settings.OLLAMA_BASE_URL,
    num_ctx=settings.OLLAMA_NUM_CTX,
    num_thread=settings.OLLAMA_NUM_THREAD,
)

# --- PROMPT "ROUTER INDUSTRIAL" CON DETECCIÓN DE AMBIGÜEDAD (ESPAÑOL) ---
SYSTEM_PROMPT = """ERES UN CLASIFICADOR DE INTENCIONES INTELIGENTE.
Analiza la solicitud del usuario (en español) y extrae datos estructurados en JSON.

OBJETIVOS:
1. CLASIFICAR "answer_type": "informational" (saber/consultar) vs "operational" (hacer/tramitar).
2. DETECTAR AMBIGÜEDAD: Si el usuario usa palabras polisémicas (con múltiples significados) sin contexto, marca como ambiguo.

REGLAS CRÍTICAS DE AMBIGÜEDAD (Contexto Universitario):
- "Falta": Ambiguo. Puede significar "Inasistencia" (clases), "Deuda" (dinero), o "Sanción" (disciplina).
  -> SI falta contexto (ej: solo dice "tengo una falta"), is_ambiguous = true.
  -> SI hay contexto (ej: "falta a clases", "falta de dinero"), is_ambiguous = false.
- "Baja": Ambiguo. Puede ser "Baja médica" (enfermedad) o "Baja académica" (retiro).
- Palabras sueltas: Entradas como "dinero", "papeles", "ayuda", "solicitud" son usualmente ambiguas sin contexto.

ESQUEMA JSON:
{
  "intent_code": "string",
  "accion": "string",
  "objeto": "string",
  "is_ambiguous": boolean,
  "clarification_prompt": "string o null",
  "answer_type": "informational | operational", 
  "multi_intent": boolean,
  "intents": []
}

*** EJEMPLOS ***

Input: "Necesito justificar una falta"
Output: {
  "intent_code": "otro", "accion": "justificar", "objeto": "falta", 
  "is_ambiguous": false, "clarification_prompt": null,
  "answer_type": "operational", "multi_intent": false, "intents": []
}

Input: "Tengo una falta"
Output: {
  "intent_code": "otro", "accion": "tener", "objeto": "falta", 
  "is_ambiguous": true, 
  "clarification_prompt": "¿Te refieres a una inasistencia a clases, una falta disciplinaria o una deuda pendiente?",
  "answer_type": "informational", "multi_intent": false, "intents": []
}

Input: "Quiero ver mis notas"
Output: {
  "intent_code": "otro", "accion": "consultar", "objeto": "notas", 
  "is_ambiguous": false, "clarification_prompt": null,
  "answer_type": "informational", "multi_intent": false, "intents": []
}

Input: "Necesito dinero"
Output: {
  "intent_code": "otro", "accion": "necesitar", "objeto": "dinero",
  "is_ambiguous": true,
  "clarification_prompt": "¿Buscas información sobre becas, préstamos estudiantiles, o ayuda económica de emergencia?",
  "answer_type": "informational", "multi_intent": false, "intents": []
}

REGLAS ADICIONALES:
1. Si `is_ambiguous` es true, `clarification_prompt` DEBE contener una pregunta educada en español pidiendo detalles.
2. Comandos directos ("solicitar", "quiero hacer") son "operational". Preguntas ("cómo", "dónde", "requisitos") son "informational".
3. Si el usuario pregunta "Cómo", "Dónde", "Requisitos", etc., SIEMPRE es "informational".
"""

def procesar_mensaje_usuario(texto_usuario: str) -> dict:
    # 1. Filtro de saludo rápido
    if _es_saludo_simple(texto_usuario):
        return _respuesta_rapida("saludo", texto_usuario)

    try:
        prompt = f"{SYSTEM_PROMPT}\nInput: \"{texto_usuario}\"\nOutput:"
        response = llm.invoke(prompt)
        raw_content = response.content.strip()

        match = re.search(r"\{[\s\S]*\}", raw_content)
        if not match:
            return _respuesta_rapida("error_formato", texto_usuario)
            
        json_str = match.group(0)
        data = json.loads(json_str)

        return _normalizar_salida(data, texto_usuario)

    except Exception as e:
        logger.error(f"Error critico: {str(e)}")
        return _respuesta_rapida("error_sistema", texto_usuario)


def _normalizar_salida(data: dict, original_text: str) -> dict:
    base = {
        "intent_code": "otro",
        "accion": "", "objeto": "",
        "is_ambiguous": False,
        "clarification_prompt": None,
        "answer_type": "informational", 
        "agent_handoff": False,
        "system_response": "",
        "multi_intent": False, "intents": [], "original_text": original_text
    }

    # Copiar datos del LLM
    for k, v in data.items():
        if k in base and v is not None:
            base[k] = v

    # --- LÓGICA DE NEGOCIO ---
    
    # 1. Si es ambiguo, preparamos la respuesta inmediata
    if base["is_ambiguous"]:
        base["system_response"] = base["clarification_prompt"] or "¿Podrías darme más detalles? No estoy seguro de a qué te refieres."
        # Importante: Si es ambiguo, NO debe ser operational ni ir al RAG
        base["answer_type"] = "clarification"
        return base

    # 2. Guardrail para preguntas informativas
    indicadores_pregunta = ["como ", "cómo ", "requisitos", "pasos", "donde ", "cuándo ", "que necesito"]
    if any(i in original_text.lower() for i in indicadores_pregunta):
        base["answer_type"] = "informational"

    # 3. Handoff Operativo
    if base["answer_type"] == "operational":
        base["agent_handoff"] = True
        accion = base.get('accion', 'tu solicitud')
        objeto = base.get('objeto', '')
        base["system_response"] = (
            f"Entendido. He derivado tu solicitud de **{accion} {objeto}** a un asesor humano. "
            "Te contactarán en breve para completar el proceso."
        )

    return base


def _es_saludo_simple(texto: str) -> bool:
    t = re.sub(r"[^\w\s]", "", texto.lower()).strip()
    return len(t.split()) < 3 and any(w in ["hola", "buenas", "hi", "alo"] for w in t.split())

def _respuesta_rapida(tipo: str, texto: str) -> dict:
    return {
        "intent_code": "saludo" if tipo == "saludo" else "otro",
        "answer_type": "informational",
        "agent_handoff": False,
        "is_ambiguous": False,
        "clarification_prompt": None,
        "system_response": "¡Hola! Soy el asistente virtual de UNEMI. ¿En qué puedo ayudarte?",
        "original_text": texto, "multi_intent": False, "intents": []
    }
