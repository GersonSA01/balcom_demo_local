# chatbot/rag_service.py

import os
import logging
from pathlib import Path
from django.conf import settings

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Ruta del índice vectorial
FAISS_INDEX_PATH = os.path.join(settings.BASE_DIR, "faiss_index")

class LocalRAGService:
    def __init__(self):
        # 1. Embeddings (Nomic es ideal para esto)
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text", 
            base_url=settings.OLLAMA_BASE_URL
        )
        
        # 2. Cargar Base de Datos (FAISS)
        self.vector_store = None
        self._cargar_indice()

        # 3. LLM (Qwen)
        # IMPORTANTE: Sin format="" para que hable natural
        self.llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            temperature=0.0,  # Temperatura 0 para máxima fidelidad al texto
            base_url=settings.OLLAMA_BASE_URL,
            keep_alive="1h",
            num_predict=settings.OLLAMA_NUM_PREDICT,
            num_ctx=settings.OLLAMA_NUM_CTX,
            num_thread=settings.OLLAMA_NUM_THREAD,
        )
        
        # 4. PROMPT EN INGLÉS (Mejor obediencia)
        # Le ordenamos pensar en inglés pero RESPONDER EN ESPAÑOL.
        self.system_prompt = """YOU ARE AN STRICT ACADEMIC ASSISTANT FOR UNEMI UNIVERSITY.
Your goal is to answer user questions using ONLY the provided CONTEXT below.

CRITICAL RULES:
1. TRUTH IS ONLY IN THE CONTEXT: If the document says something is "prohibited" or "not allowed", state it clearly. Do NOT offer workarounds, apologies, or external advice.
2. NO HALLUCINATIONS: If the answer is not in the context, say: "No encuentro información sobre este tema en los documentos oficiales."
3. CITE SOURCES: Mention the document name if available.
4. LANGUAGE: The system prompt is in English for precision, but YOU MUST REPLY IN SPANISH.
5. TONE: Professional, direct, and informative.

CONTEXT:
{context}
"""

    def _cargar_indice(self):
        """Carga el índice FAISS si existe en disco."""
        if os.path.exists(FAISS_INDEX_PATH):
            try:
                self.vector_store = FAISS.load_local(
                    FAISS_INDEX_PATH, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Índice FAISS cargado correctamente.")
            except Exception as e:
                logger.error(f"Error cargando FAISS: {e}", exc_info=True)
        else:
            logger.warning("Índice FAISS no encontrado. Se creará al ingerir documentos.")

    def consultar(self, query: str):
        """
        Realiza la consulta RAG y muestra el contexto en consola.
        """
        if not self.vector_store:
            return {
                "response": "El sistema no tiene documentos cargados. Ejecuta la carga primero.",
                "has_information": False,
                "sources": []
            }

        try:
            # A. Búsqueda Vectorial
            docs = self.vector_store.similarity_search(query, k=3)
            
            if not docs:
                return {
                    "response": "No encontré información relevante en los reglamentos.",
                    "has_information": False,
                    "sources": []
                }

            # B. Construcción del Contexto
            context_text = "\n\n".join([d.page_content for d in docs])
            sources = list(set([Path(d.metadata.get("source", "Doc")).name for d in docs]))

            # --- 🕵️ DEBUGGING: VER LO QUE LEE LA IA ---
            print("\n" + "="*40)
            print(f"🔍 RAG CONTEXTO RECUPERADO PARA: '{query}'")
            print("-" * 40)
            print(context_text[:1000] + "..." if len(context_text) > 1000 else context_text)
            print("="*40 + "\n")
            # -------------------------------------------
            
            # C. Generación con LLM
            prompt = self.system_prompt.format(context=context_text)
            messages = [
                ("system", prompt),
                ("human", query), # La query está en español, el prompt le fuerza a responder en español
            ]
            
            ai_msg = self.llm.invoke(messages)
            
            return {
                "response": ai_msg.content,
                "has_information": True,
                "sources": sources
            }

        except Exception as e:
            logger.error(f"Error en RAG: {e}", exc_info=True)
            return {
                "response": "Ocurrió un error técnico al consultar los documentos.",
                "has_information": False,
                "sources": []
            }

    def ingerir_documento(self, file_path: str):
        """Ingesta de documentos a FAISS."""
        try:
            # 1. Cargar
            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith(".txt"):
                loader = TextLoader(file_path)
            else:
                return False, "Formato no soportado"

            docs = loader.load()
            
            # 2. Dividir (Chunking optimizado)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=600,    # Trozos un poco más grandes para tener contexto
                chunk_overlap=100  # Solapamiento para no cortar frases
            )
            splits = text_splitter.split_documents(docs)
            
            if not splits: return False, "Archivo vacío"

            # 3. Indexar
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(splits, self.embeddings)
            else:
                self.vector_store.add_documents(splits)
            
            # 4. Guardar
            self.vector_store.save_local(FAISS_INDEX_PATH)
            
            return True, f"Procesado: {Path(file_path).name} ({len(splits)} fragmentos)"
            
        except Exception as e:
            logger.error(f"Error ingiriendo: {e}", exc_info=True)
            return False, str(e)

    def listar_documentos(self):
        if not self.vector_store: return []
        return ["Documentos indexados en FAISS"] # FAISS no permite listar fácilmente

rag_service = LocalRAGService()