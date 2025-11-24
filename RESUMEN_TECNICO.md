# Resumen Técnico Detallado: Balcón Demo Local

Este documento ofrece un análisis profundo del funcionamiento interno del proyecto `balcon_demo_local`. Este sistema actúa como una interfaz inteligente (Frontend + Middleware) que consume los servicios de Inteligencia Artificial de un proyecto externo (**Private-GPT**).

## 🏗️ Arquitectura de Alto Nivel

El sistema no procesa la IA localmente. Su función es orquestar la comunicación entre el usuario y la API de Private-GPT.

1.  **Frontend (Svelte):** Interfaz de chat reactiva.
2.  **Backend (Django):** Middleware que gestiona la lógica de negocio, clasificación de intenciones y llamadas a la API.
3.  **Private-GPT (Externo):** Motor de IA que maneja los Embeddings, Vector Store (Qdrant) y el LLM (Ollama).

---

## 📂 Análisis Archivo por Archivo

A continuación, se detalla el contenido y la importancia de los archivos más críticos del proyecto.

### 1. Backend: Aplicación `chatbot`

Esta carpeta contiene la lógica central del "cerebro" del intermediario.

#### 📄 `chatbot/views.py` (El Controlador Principal)
**Importancia:** ⭐⭐⭐⭐⭐ (Crítica)
Es el archivo más importante del backend. Define cómo se procesan los mensajes.

*   **Clase `ChatView`:** Maneja las peticiones `POST` del chat.
*   **Streaming:** Utiliza `StreamingHttpResponse` para enviar la respuesta token por token al frontend, mejorando la percepción de velocidad.
*   **Lógica de Orquestación:**
    1.  Recibe el mensaje del usuario.
    2.  Llama a `intent_parser` para clasificar la intención.
    3.  **Si es Ambiguo:** Devuelve una pregunta de clarificación inmediata.
    4.  **Si es Operativo (Trámite):** Activa el flujo de `agent_handoff` (derivación a humano).
    5.  **Si es Informativo (Pregunta):** Construye un payload para la API de Private-GPT (`/v1/chat/completions`).
        *   Define un **System Prompt RAG** específico que instruye a la IA sobre cómo usar el contexto de los documentos.
        *   Maneja la respuesta en stream y la reenvía al frontend.

#### 📄 `chatbot/intent_parser.py` (El Clasificador)
**Importancia:** ⭐⭐⭐⭐⭐ (Crítica)
Responsable de entender *qué* quiere el usuario antes de intentar responder.

*   **Función `procesar_mensaje_usuario`:** Envía el texto a Private-GPT (con `use_context=False`) para una clasificación rápida.
*   **`SYSTEM_PROMPT`:** Un prompt de ingeniería detallado que define las reglas:
    *   Distingue entre `informational` (preguntas) y `operational` (acciones).
    *   Detecta ambigüedad (ej: "tengo una falta" -> ¿dinero o asistencia?).
*   **Normalización:** Convierte la respuesta de la IA (JSON) en una estructura de datos Python estandarizada para que `views.py` la use.

#### 📄 `chatbot/urls.py`
**Importancia:** ⭐⭐⭐
Define los puntos de entrada de la API.
*   `/chat/`: Endpoint principal para mensajería.
*   `/health/`: Endpoint de diagnóstico que verifica si Django y Private-GPT están operativos.

### 2. Configuración: `config`

#### 📄 `config/settings.py`
**Importancia:** ⭐⭐⭐⭐
Configuración global del framework Django.
*   **`PRIVATE_GPT_API_URL`:** Define dónde está escuchando la IA (por defecto `http://localhost:8001`).
*   **CORS:** Configurado para permitir peticiones desde `localhost:5173` (el frontend Svelte).

### 3. Frontend: `frontend`

#### 📄 `frontend/src/lib/Chatbot.svelte` (La Interfaz)
**Importancia:** ⭐⭐⭐⭐⭐
El componente visual con el que interactúa el usuario.

*   **Gestión de Estado:** Maneja la lista de mensajes, el estado de carga (`isLoading`) y la conexión (`isConnected`).
*   **Comunicación:** La función `sendMessage` hace el `POST` al backend y procesa la respuesta en formato **NDJSON** (Newline Delimited JSON).
*   **Renderizado Inteligente:**
    *   Muestra respuestas de texto normal.
    *   Muestra fuentes bibliográficas si es una respuesta RAG.
    *   Muestra mensajes especiales si ocurre una derivación a agente humano.

#### 📄 `frontend/src/App.svelte`
**Importancia:** ⭐⭐
El contenedor principal de la aplicación. Define la estructura base HTML y el enrutamiento simple.

### 4. Raíz del Proyecto

#### 📄 `manage.py`
Script estándar de Django para ejecutar comandos (runserver, makemigrations, etc.).

#### 📄 `requirements.txt`
Lista de dependencias. Es notablemente ligero porque no corre modelos pesados.
*   `Django`, `djangorestframework`: Para la API.
*   `requests`: Para hablar con Private-GPT.
*   `python-dotenv`: Para variables de entorno.

---

## 🔄 Resumen del Flujo de una Consulta

1.  **Usuario:** "¿Cómo justifico una falta?"
2.  **Frontend:** Envía texto a Django (`views.py`).
3.  **Django:** Envía texto a Private-GPT (Clasificador).
4.  **Private-GPT:** Responde JSON: `{"intent": "justificar_falta", "type": "operational"}`.
5.  **Django:** Detecta `operational`. No hace búsqueda RAG. Devuelve respuesta de "Handoff" al frontend.
6.  **Frontend:** Muestra: "He derivado tu caso a un asesor humano..."

*Si la pregunta fuera "¿Qué dice el reglamento sobre faltas?":*
1.  ...
4.  **Private-GPT:** Responde JSON: `{"type": "informational"}`.
5.  **Django:** Envía nueva petición a Private-GPT con `use_context=True` (RAG).
6.  **Private-GPT:** Busca en vectores, genera respuesta con contexto.
7.  **Django:** Transmite la respuesta generada al frontend.
