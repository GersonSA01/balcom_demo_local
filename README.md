# Balcón de Servicios UNEMI - Demo Local

Sistema de gestión de solicitudes estudiantiles con chatbot inteligente que consume Private-GPT API.

## 📋 Descripción

Balcon Demo es un **frontend ligero** que consume la API de **Private-GPT** para:
- **Clasificación de intenciones**: Determina si el usuario necesita información o quiere realizar un trámite
- **Consultas RAG**: Busca información en documentos normativos a través de Private-GPT
- **Gestión de solicitudes**: Sistema completo para trámites estudiantiles

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────┐
│  Balcon Demo Local (Este Proyecto)             │
│  ├─ Frontend (Svelte)                          │
│  ├─ Backend Django (API REST)                  │
│  │   ├─ intent_parser.py → Private-GPT API    │
│  │   └─ views.py → Private-GPT API (RAG)      │
└─────────────────────────────────────────────────┘
                    ↓ HTTP Requests
┌─────────────────────────────────────────────────┐
│  Private-GPT (Proyecto Separado)               │
│  ├─ /v1/chat/completions                       │
│  ├─ Ollama (LLM)                               │
│  ├─ Qdrant (Vector DB)                         │
│  └─ Documentos PDF ingresados                  │
└─────────────────────────────────────────────────┘
```

## 🚀 Características

- ✅ **Chatbot Inteligente**: Clasifica intenciones y responde con contexto
- ✅ **Integración con Private-GPT**: Consume API RAG para búsqueda semántica
- ✅ **Gestión de Solicitudes**: Sistema completo para trámites estudiantiles
- ✅ **Arquitectura Desacoplada**: No requiere Ollama local, todo vía API

## 📁 Estructura del Proyecto

```
balcon_demo_local/
├── chatbot/              # App Django - Chatbot + API
│   ├── intent_parser.py  # Clasificación de intenciones (usa Private-GPT)
│   ├── views.py          # Consultas RAG (usa Private-GPT)
│   └── urls.py
├── config/               # Configuración Django
│   └── settings.py       # PRIVATE_GPT_API_URL
├── frontend/             # Frontend Svelte
└── requirements.txt      # Dependencias Python mínimas
```

## 🔧 Instalación

### Requisitos Previos

1. **Python 3.9+**
2. **Node.js 16+**
3. **Private-GPT corriendo** (en `http://localhost:8001` o configurado en `.env`)

### Pasos de Instalación

1. **Clonar el repositorio:**
```bash
git clone <repo>
cd balcon_demo_local
```

2. **Crear entorno virtual e instalar dependencias:**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

3. **Configurar variables de entorno:**
Crear archivo `.env` en la raíz:
```env
PRIVATE_GPT_API_URL=http://localhost:8001
```

4. **Instalar dependencias del Frontend:**
```bash
cd frontend
npm install
```

## 🚀 Uso

### 1. Asegúrate de que Private-GPT esté corriendo

```bash
cd private-gpt-main
docker compose up
# o tu método preferido de ejecución
```

Verifica que esté disponible en: `http://localhost:8001/docs`

### 2. Iniciar el servidor Django

```bash
python manage.py runserver
```

### 3. Iniciar el frontend (en otra terminal)

```bash
cd frontend
npm run dev
```

El sistema estará disponible en:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5173
- **Private-GPT**: http://localhost:8001

## 🔌 Endpoints

### Backend Django (Puerto 8000)

- `POST /api/chatbot/chat/` - Endpoint principal del chatbot (streaming)
- `GET /api/chatbot/health/` - Health check del servicio

### Flujo de Datos

1. **Usuario envía mensaje** → Frontend
2. **Frontend** → `POST /api/chatbot/chat/`
3. **Backend Django:**
   - `intent_parser.py` → Private-GPT (`use_context=false`) para clasificar
   - Si es informativo → `views.py` → Private-GPT (`use_context=true`) para RAG
4. **Private-GPT** busca en documentos y genera respuesta
5. **Respuesta** → Frontend → Usuario

## 🛠️ Tecnologías

- **Backend**: Django 4.x, Django REST Framework
- **Frontend**: Svelte 4, SvelteStrap
- **IA/RAG**: Private-GPT API (proyecto separado)
- **HTTP Client**: requests

## ⚙️ Configuración

### Variables de Entorno (.env)

```env
# URL de la API de Private-GPT
PRIVATE_GPT_API_URL=http://localhost:8001
```

### Settings de Django

El archivo `config/settings.py` lee la configuración:

```python
PRIVATE_GPT_API_URL = os.getenv('PRIVATE_GPT_API_URL', 'http://localhost:8001')
```

## 📝 Notas Importantes

- Este proyecto **NO ejecuta Ollama directamente**, solo consume la API de Private-GPT
- Los documentos PDF se gestionan en el proyecto **Private-GPT**, no aquí
- El sistema de embeddings y vectores está en **Private-GPT**

## 📝 Licencia

Este proyecto es un demo local del sistema Balcón de Servicios UNEMI.

