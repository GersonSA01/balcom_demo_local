# chatbot/rag_service.py

import os
import json
import logging
from pathlib import Path
from django.conf import settings

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = os.path.join(settings.BASE_DIR, "faiss_index")

class LocalRAGService:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text", 
            base_url=settings.OLLAMA_BASE_URL
        )
        
        self.vector_store = None
        self._cargar_indice()

        self.llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            format="json",
            temperature=0,
            base_url=settings.OLLAMA_BASE_URL,
            keep_alive="1h",
            num_predict=settings.OLLAMA_NUM_PREDICT,
            num_ctx=settings.OLLAMA_NUM_CTX,
            num_thread=settings.OLLAMA_NUM_THREAD,
        )
        
        # --- PROMPT OPTIMIZADO PARA VELOCIDAD (TOKEN SAVING) ---
        self.rag_prompt = """YOU ARE AN ACADEMIC ASSISTANT FOR UNEMI.
Answer based ONLY on the provided CONTEXT.

TASK:
Return a JSON: {{ "has_information": bool, "need_contact": bool, "response": string, "sources": [] }}

CRITICAL RULES:
1. IF NO INFO IN CONTEXT: Set "has_information": false, "need_contact": true, and "response": null. (DO NOT WRITE AN APOLOGY. SAVE TOKENS).
2. IF INFO EXISTS: Set "has_information": true. If manual action is needed, "need_contact": true. Write the answer in "response" in Spanish.
3. TRUTH IS ONLY IN THE CONTEXT. If it says "Prohibited", say it.
4. CONTEXT IS FILTERED FOR USER ROLE: {user_role}. IGNORE IRRELEVANT INFO. If user asks about "Faltas", ignore "Tesis" or "Notas".

CONTEXT:
{context}

USER QUERY:
{query}
"""

        # Prompt para Reformular Preguntas (Query Expansion)
        self.expansion_prompt = """Eres un experto en terminología universitaria.
Genera 3 variantes de búsqueda para la siguiente pregunta.
Corrige faltas ortográficas.

Output JSON format:
{{
  "queries": ["variante 1", "variante 2", "variante 3"]
}}

User Question: {question}
"""

    def _cargar_indice(self):
        if os.path.exists(FAISS_INDEX_PATH):
            try:
                self.vector_store = FAISS.load_local(
                    FAISS_INDEX_PATH, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Índice FAISS cargado.")
            except Exception as e:
                logger.error(f"Error cargando FAISS: {e}")
                self.vector_store = None
        else:
            logger.warning("Índice no encontrado.")
            self.vector_store = None

    def _expandir_query(self, query_original: str) -> list:
        """Genera 3 versiones de la pregunta para mejorar la búsqueda."""
        try:
            prompt = self.expansion_prompt.format(question=query_original)
            response = self.llm.invoke(prompt)
            raw_content = response.content.strip()
            
            # Extracción robusta de JSON
            import re
            match = re.search(r"\{[\s\S]*\}", raw_content)
            if not match:
                logger.warning(f"JSON no encontrado en expansión: {raw_content[:50]}")
                return [query_original]
            
            json_str = match.group(0)
            data = json.loads(json_str)
            variantes = data.get("queries", [])
            
            # Validar que sea una lista
            if not isinstance(variantes, list):
                return [query_original]
            
            # Agregamos la original por si acaso
            variantes.append(query_original)
            return list(set(variantes))  # Eliminar duplicados
        except Exception as e:
            logger.error(f"Error expandiendo query: {e}")
            return [query_original]  # Fallback a la original

    def consultar(self, query: str, categorias_permitidas: list = None, user_role_name: str = "Visitante"):
        # CASO 0: No hay base de datos -> Contactar soporte
        if not self.vector_store:
            return self._respuesta_fallback("El sistema de documentos está apagado.")

        # Default: Si no se especifican categorías, permitir todas (compatibilidad hacia atrás)
        if categorias_permitidas is None:
            categorias_permitidas = ["general", "estudiantes", "docentes", "administrativos"]

        try:
            # PASO 1: Expandir consulta (Multi-Query)
            queries_optimizadas = self._expandir_query(query)
            print(f"🔍 Búsqueda expandida: {queries_optimizadas}")

            # PASO 2: Búsqueda Masiva con FILTRADO (Post-Filtering para máxima compatibilidad FAISS CPU)
            # Buscamos más documentos (k=15) y luego filtramos por categoría en Python
            candidatos = []
            
            for q in queries_optimizadas:
                # Traemos bastantes candidatos crudos
                raw_docs = self.vector_store.similarity_search_with_score(q, k=15)
                for doc, score in raw_docs:
                    doc_cat = doc.metadata.get("categoria", "general")
                    
                    # --- FILTRO DE SEGURIDAD ---
                    if doc_cat in categorias_permitidas:
                        candidatos.append((doc, score))

            # PASO 3: Ordenar y Deduplicar
            # En FAISS L2 distance, menor score = mejor coincidencia.
            # Ordenamos de menor a mayor score.
            candidatos.sort(key=lambda x: x[1])  # Menor score es mejor

            docs_finales = []
            ids_vistos = set()
            
            for doc, score in candidatos:
                h = hash(doc.page_content)
                if h not in ids_vistos:
                    ids_vistos.add(h)
                    docs_finales.append(doc)
                if len(docs_finales) >= 6:  # Top 6 filtrados
                    break

            # CASO 1: No encontró nada en la búsqueda vectorial -> Contactar soporte
            if not docs_finales:
                return self._respuesta_fallback(f"No encontré información relevante para tu perfil ({user_role_name}).")

            # PASO 4: Construcción del Contexto
            context_text = "\n\n".join([d.page_content for d in docs_finales])
            
            # --- DEBUG VISUAL ---
            print("\n" + "="*40)
            print(f"🔍 RAG ({user_role_name}) | Categorías permitidas: {categorias_permitidas}")
            print(f"🏆 TOP {len(docs_finales)} CHUNKS SELECCIONADOS")
            print("-" * 40)
            fuentes_debug = list(set([Path(d.metadata.get("source", "Doc")).name for d in docs_finales]))
            print(f"📚 Fuentes usadas: {fuentes_debug}")
            print(f"CTX LENGTH: {len(context_text)} caracteres")
            print("="*40 + "\n")
            
            # PASO 5: Generación de Respuesta JSON
            final_prompt = self.rag_prompt.format(context=context_text, query=query, user_role=user_role_name)
            ai_response = self.llm.invoke(final_prompt)
            
            # Parseo seguro
            try:
                resultado = json.loads(ai_response.content)
            except json.JSONDecodeError:
                # Fallback si el modelo falla el JSON (raro con format="json")
                return self._respuesta_fallback("Error al procesar la respuesta del sistema.")

            resultado["sources"] = fuentes_debug

            # --- OPTIMIZACIÓN DE VELOCIDAD (PYTHON FILL-IN) ---
            if not resultado.get("has_information") or resultado.get("response") is None:
                resultado["has_information"] = False
                resultado["need_contact"] = True
                resultado["response"] = (
                    "Lo siento, no encontré esa información en los reglamentos de tu perfil. "
                    "He derivado tu caso a un asesor humano que podrá ayudarte mejor."
                )

            return resultado

        except Exception as e:
            logger.error(f"Error RAG: {e}", exc_info=True)
            return self._respuesta_fallback("Ocurrió un error técnico al consultar los documentos.")

    def _respuesta_fallback(self, mensaje: str):
        """Respuesta por defecto cuando todo falla: SIEMPRE pide contacto humano."""
        return {
            "has_information": False,
            "need_contact": True,  # <--- AQUÍ ESTÁ LA CLAVE
            "response": f"{mensaje} He derivado tu caso a un asesor humano.",
            "sources": []
        }

    def ingerir_documento(self, file_path: str, categoria: str = "general"):
        try:
            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith(".txt"):
                loader = TextLoader(file_path)
            else:
                return False, "Formato incorrecto"

            docs = loader.load()
            
            # INYECTAR METADATA CATEGORÍA en cada documento
            for d in docs:
                d.metadata["categoria"] = categoria

            # Chunking grande para mantener contexto legal junto
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,    
                chunk_overlap=200  
            )
            splits = text_splitter.split_documents(docs)
            
            # Verificar que la categoría se mantuvo después del split
            for split in splits:
                if "categoria" not in split.metadata:
                    split.metadata["categoria"] = categoria
            
            if not splits:
                return False, "Archivo vacío"

            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(splits, self.embeddings)
            else:
                self.vector_store.add_documents(splits)
            
            self.vector_store.save_local(FAISS_INDEX_PATH)
            
            return True, f"Procesado ({categoria}): {Path(file_path).name} ({len(splits)} fragmentos)"
            
        except Exception as e:
            logger.error(f"Error ingiriendo: {e}")
            return False, str(e)

    def listar_documentos(self):
        if not self.vector_store:
            return []
        return ["Documentos FAISS (Lista no disponible)"]

rag_service = LocalRAGService()
