import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import asyncio

app = FastAPI()

# ==============================================================================
# 1. LÓGICA DEL ROUTER (Clasificación de intención)
# ==============================================================================
def get_mock_router_response(user_message):
    msg = user_message.lower()

    # --- ESCENARIO A: El usuario pide hablar con alguien explícitamente ---
    if "humano" in msg or "asesor" in msg or "persona" in msg:
        content_json = {
            "classification": "FUNCTION",
            "function_name": "HUMAN_HANDOFF",
            "action": "FUNCTION",
            "response": "¿Quieres que te contacte con mis compañeros humanos?",
            "handoff_message": "¿Deseas contactar a un agente?"
        }

    # --- ESCENARIO B: Tema fuera de contexto ---
    elif "pizza" in msg or "receta" in msg or "futbol" in msg:
        content_json = {
            "classification": "OFF_TOPIC",
            "action": "ANSWER",
            "function_name": "OFF_TOPIC",
            "response": "Lo siento, solo hablo de temas académicos."
        }

    # --- ESCENARIO C: Detecta un proceso/función específico ---
    elif "certificado" in msg:
        content_json = {
            "classification": "FUNCTION",
            "function_name": "Solicitud de Certificados", # Asegúrate que este nombre exista en tu BD Django si quieres que funcione completo
            "action": "FUNCTION",
            "response": "Procesando solicitud..."
        }

    # --- ESCENARIO D (Default): Pasa al RAG (Búsqueda de información) ---
    else:
        # Aquí simulamos que el Router optimiza la query
        content_json = {
            "classification": "RAG",
            "search_query": f"{user_message} (optimizada)", 
            "action": "ANSWER",
            "response": "RAG_MODE",
            "reformulated_query": f"{user_message} institucional reglamento" # Clave para tu views.py
        }
    
    # Empaquetado estilo OpenAI
    return {
        "choices": [{"message": {"content": json.dumps(content_json)}}]
    }


# ==============================================================================
# 2. LÓGICA DEL RAG (Generación de respuesta final)
# ==============================================================================
def get_mock_rag_response(user_message):
    msg = user_message.lower()
    
    # --- ESCENARIO: RAG NO ENCUENTRA NADA (answer_found = False) ---
    # Trigger: escribir "nada", "raro", "desconocido"
    if "nada" in msg or "raro" in msg or "desconocido" in msg:
        response_data = {
            "response": "Lo siento, en la documentación actual no encontré información sobre eso. ¿Deseas contactar a un humano?",
            "source_ids": [],
            "sources": [],
            "answer_found": False  # <--- ESTO ES LO QUE BUSCAS PROBAR
        }

    # --- ESCENARIO: RAG ÉXITO (answer_found = True) ---
    else:
        response_data = {
            "response": f"🤖 SIMULACIÓN RAG: He encontrado información relevante sobre '{user_message}'. Según el reglamento, el estudiante debe proceder...",
            "source_ids": [123, 456], # IDs simulados
            "sources": [
                {
                    "document": {
                        "doc_metadata": {
                            "file_name": "Reglamento_Academico_2025.pdf",
                            "access_url": "/media/docs/dummy.pdf"
                        }
                    }
                }
            ],
            "answer_found": True
        }
    
    return {
        "choices": [{"message": {"content": json.dumps(response_data)}}]
    }


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Simula Router y RAG diferenciando por el Prompt de Sistema
    """
    body = await request.json()
    messages = body.get("messages", [])
    
    # Extraer mensajes
    user_msg = ""
    system_msg = ""
    
    if messages:
        # Buscar el último mensaje del usuario
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        
        # Buscar el mensaje de sistema (generalmente el primero)
        if messages[0].get("role") == "system":
            system_msg = messages[0].get("content", "")

    print(f"\n📨 [MOCK REQUEST] User: '{user_msg}'")

    # 1. ¿Es una petición al ROUTER?
    # Tu views.py envía "[TOOLS_LIST]" o el prompt de "Intent Classifier"
    if "[TOOLS_LIST]" in system_msg or "Intent Classifier" in system_msg:
        print("   👉 [MODO] ROUTER")
        await asyncio.sleep(0.3) 
        return JSONResponse(content=get_mock_router_response(user_msg))

    # 2. ¿Es una petición de REFORMULACIÓN silenciosa?
    elif "REFORMULATE_QUERY_MODE" in system_msg:
        print("   👉 [MODO] REFORMULACIÓN")
        return JSONResponse(content={
            "choices": [{"message": {"content": user_msg}}] # Devuelve lo mismo para simplificar
        })

    # 3. ¿Es una petición al RAG (Generación final)?
    # Normalmente el prompt dice "RAG_EXPERT_MODE" o simplemente pide responder con contexto
    else:
        print("   👉 [MODO] RAG GENERATION")
        await asyncio.sleep(0.8) # Simular "pensando..."
        return JSONResponse(content=get_mock_rag_response(user_msg))


# Endpoints dummy para la subida de archivos (para que no de error el panel de admin)
@app.post("/v1/ingest/file")
def ingest_file(file: bytes = None):
    return {"data": [{"doc_id": "mock_id_999"}]}

@app.post("/v1/ingest/{doc_id}/metadata")
def ingest_metadata(doc_id: str):
    return {"status": "ok"}

@app.delete("/v1/ingest/{doc_id}")
def delete_ingest(doc_id: str):
    return {"status": "ok"}


if __name__ == "__main__":
    # Puerto 5050 según tu configuración
    print("🚀 Mock AI Server listo en http://localhost:5050")
    print("💡 TIPS DE PRUEBA:")
    print("   - Escribe 'nada' o 'raro' -> Simula RAG fallido (answer_found=False)")
    print("   - Escribe 'asesor' -> Simula Handoff inmediato")
    print("   - Escribe 'pizza' -> Simula Off-Topic")
    uvicorn.run(app, host="0.0.0.0", port=5050)