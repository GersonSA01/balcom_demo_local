# Balcón de Servicios UNEMI - Demo Local

Sistema de gestión de solicitudes estudiantiles con chatbot RAG (Retrieval-Augmented Generation) completamente local.

## 📋 Descripción

Sistema RAG (Retrieval-Augmented Generation) completamente local usando:
- **LangChain**: Framework para RAG
- **FAISS**: Base de datos vectorial local (sin SQLite, sin servidor)
- **Ollama**: Modelos locales (Qwen 2.5 3B + nomic-embed-text)
- **Django**: Backend REST API
- **Svelte**: Frontend con componentes interactivos

## 🚀 Características

- ✅ **Chatbot RAG**: Respuestas informativas basadas en documentos institucionales
- ✅ **Gestión de Solicitudes**: Sistema completo para trámites estudiantiles
- ✅ **Completamente Local**: No requiere servicios externos ni internet
- ✅ **Búsqueda Semántica**: Encuentra información relevante en documentos PDF

## 📁 Estructura del Proyecto

```
balcon_demo_local/
├── chatbot/              # App Django - Chatbot RAG
├── config/               # Configuración Django
├── frontend/             # Frontend Svelte
├── documentos_unemi/     # Documentos PDF para RAG
├── faiss_index/         # Índice vectorial FAISS
└── requirements.txt     # Dependencias Python
```

## 🔧 Instalación

### Requisitos Previos

1. Python 3.9+
2. Node.js 16+
3. Ollama instalado y corriendo

### Pasos de Instalación

1. **Instalar dependencias Python:**
```bash
pip install -r requirements.txt
```

2. **Descargar modelo de embeddings:**
```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:3b-instruct-q4_K_M
```

3. **Instalar dependencias Frontend:**
```bash
cd frontend
npm install
```

4. **Cargar documentos al sistema RAG:**
```bash
python cargar_docs.py
```

## 🚀 Uso

### Iniciar el servidor Django

```bash
python manage.py runserver
```

### Iniciar el frontend (en otra terminal)

```bash
cd frontend
npm run dev
```

El sistema estará disponible en:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## 📚 Documentación

Para más detalles sobre el sistema RAG, consulta [README_RAG.md](README_RAG.md)

## 🛠️ Tecnologías

- **Backend**: Django, LangChain, FAISS
- **Frontend**: Svelte 4, SvelteStrap
- **IA**: Ollama (modelos locales)
- **Búsqueda Vectorial**: FAISS

## 📝 Licencia

Este proyecto es un demo local del sistema Balcón de Servicios UNEMI.

