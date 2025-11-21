import os
import json
import re
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
        # 1. Embeddings (Nomic es el estándar de PrivateGPT para local)
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text", 
            base_url=settings.OLLAMA_BASE_URL
        )
        
        self.vector_store = None
        self._cargar_indice()

        # 2. LLM (Configuración de temperatura baja como en settings.yaml de PrivateGPT)
        self.llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            format="json", # Forzamos JSON nativo de Ollama
            temperature=0.1, 
            base_url=settings.OLLAMA_BASE_URL,
            keep_alive="1h",
            num_predict=settings.OLLAMA_NUM_PREDICT,
            num_ctx=settings.OLLAMA_NUM_CTX,
            num_thread=settings.OLLAMA_NUM_THREAD,
        )
        
        # 3. Prompt RAG (Estricto, estilo PrivateGPT pero con lógica de contacto)
        self.rag_prompt = """You are a helpful, respectful and honest assistant for UNEMI.
Answer exclusively with a valid JSON.

TASK:
Analyze the context and user query. Return a JSON object with these keys:
{{
  "has_information": boolean, (true only if the answer is explicitly in the context)
  "need_contact": boolean, (true if the context implies manual processing at a window/office/secretary)
  "response": "string", (The answer in Spanish. Concise and natural. If no info, return null.)
  "sources": ["file.pdf"]
}}

CRITICAL RULES:
1. CONTEXT IS FILTERED FOR ROLE: {user_role}.
2. IF NO INFO IN CONTEXT: Set "has_information": false, "need_contact": true, "response": null.
3. TRUTH IS ONLY IN THE CONTEXT. If it says "Prohibited", say it.
4. IGNORE IRRELEVANT INFO. If user asks about "Faltas", ignore "Tesis" or "Notas".

CONTEXT:
{context}

USER QUERY:
{query}
"""

        # 4. Prompt de Expansión (EL ARREGLO CLAVE PARA TUS ALUCINACIONES)
        # Este prompt prohíbe explícitamente contextos laborales o de CV.
        self.expansion_prompt = """ACT AS AN ACADEMIC SEARCH EXPERT.
Target Domain: University Regulations, Student Welfare, Academic Processes.

YOUR GOAL:
Translate the user's colloquial query into 3 precise search queries using formal academic terminology found in official regulation PDFs.

INSTRUCTIONS:
1. DETECT THE CORE TOPIC: Identify what the user really wants (e.g., money -> financial aid; missing class -> attendance).
2. DISCARD IRRELEVANT CONTEXTS: Ignore words related to "job", "work", "cv", "resume", "boyfriend", "parents", "currículum". Focus only on the University scope.
3. GENERATE 3 VARIATIONS:
   - Query 1: Formal academic term for the action (e.g., "Justificación de inasistencia").
   - Query 2: Specific regulation or article keyword (e.g., "Normativa de asistencia").
   - Query 3: Synonyms used in Ecuador/UNEMI context.

EXAMPLES:
User: "quiero borrar una materia"
JSON Output: {{"queries": ["anulación de matrícula", "retiro de asignatura", "proceso de baja académica"]}}

User: "falta laboral"
JSON Output: {{"queries": ["inasistencia a clases", "justificación de inasistencia", "reglamento de asistencia"]}}
(Note: It corrects 'laboral' to academic context).

USER INPUT: "{question}"

OUTPUT JSON FORMAT:
{{
  "queries": ["term 1", "term 2", "term 3"]
}}
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
            except Exception: self.vector_store = None
        else: self.vector_store = None

    def _extraer_json(self, texto):
        """Ayuda a encontrar el JSON si el modelo añade texto extra."""
        try:
            match = re.search(r"\{[\s\S]*\}", texto)
            if match:
                return json.loads(match.group(0))
            return json.loads(texto)
        except:
            return None

    def _expandir_query(self, query: str) -> list:
        try:
            prompt = self.expansion_prompt.format(question=query)
            res = self.llm.invoke(prompt)
            
            data = self._extraer_json(res.content)
            if not data: return [query]
            
            variantes = data.get("queries", [])
            if isinstance(variantes, list):
                variantes.append(query)
                return list(set(variantes))
            return [query]
        except Exception as e:
            logger.error(f"Error expandiendo: {e}")
            return [query]

    def consultar(self, query: str, categorias_permitidas: list, user_role_name: str):
        if not self.vector_store:
            return self._respuesta_fallback("Sistema apagado.")

        try:
            # 1. Expansión de Consulta
            queries = self._expandir_query(query)
            print(f"\n🔄 Queries expandidas: {queries}")
            
            # 2. Búsqueda "Wide" (Similar a PrivateGPT similarity_top_k=10)
            candidatos = []
            for q in queries:
                # k=10 asegura cobertura amplia antes del filtrado
                raw_docs = self.vector_store.similarity_search_with_score(q, k=10)
                for doc, score in raw_docs:
                    doc_cat = doc.metadata.get("categoria", "general")
                    
                    # Filtro de Rol
                    if doc_cat in categorias_permitidas:
                        candidatos.append((doc, score))

            # 3. Reranking y Deduplicación
            candidatos.sort(key=lambda x: x[1]) # Menor score es mejor
            
            docs_finales = []
            ids = set()
            
            for doc, score in candidatos:
                # Umbral de corte (Heurística para Nomic ~0.65 es decente)
                if score > 0.75: continue # Si es muy irrelevante, ignorar

                h = hash(doc.page_content)
                if h not in ids:
                    ids.add(h)
                    docs_finales.append(doc)
                if len(docs_finales) >= 6: break # Top 6 chunks

            if not docs_finales:
                return self._respuesta_fallback(f"No encontré información relevante en los documentos de {user_role_name}.")

            # 4. Generación
            context = "\n\n".join([d.page_content for d in docs_finales])
            fuentes = list(set([Path(d.metadata.get("source", "Doc")).name for d in docs_finales]))
            
            # DEBUG
            print(f"\n🔍 RAG [{user_role_name}]")
            print(f"📚 Fuentes ({len(docs_finales)} chunks): {fuentes}")
            
            # DEBUG CONTEXTO (Verificamos que no esté metiendo currículum)
            print(f"📄 Muestra contexto: {context[:200].replace(chr(10), ' ')}...") 

            final_prompt = self.rag_prompt.format(context=context, query=query, user_role=user_role_name)
            ai_response = self.llm.invoke(final_prompt)
            
            resultado = self._extraer_json(ai_response.content)
            
            if not resultado:
                # Fallback si el JSON falla
                resultado = {"has_information": True, "need_contact": False, "response": ai_response.content, "sources": []}

            resultado["sources"] = fuentes
            
            # Fallback semántico: Si la IA dice que no sabe
            if not resultado.get("has_information") or not resultado.get("response"):
                resultado["has_information"] = False
                resultado["need_contact"] = True
                resultado["response"] = "Lo siento, no encontré esa información específica en los reglamentos de tu perfil."

            return resultado

        except Exception as e:
            logger.error(f"Error RAG: {e}", exc_info=True)
            return self._respuesta_fallback("Error técnico.")

    def _respuesta_fallback(self, mensaje: str):
        return {"has_information": False, "need_contact": True, "response": mensaje, "sources": []}

    def ingerir_documento(self, file_path: str, categoria: str = "general"):
        try:
            if file_path.endswith(".pdf"): loader = PyPDFLoader(file_path)
            elif file_path.endswith(".txt"): loader = TextLoader(file_path)
            else: return False, "Formato incorrecto"
            
            docs = loader.load()
            for d in docs: d.metadata["categoria"] = categoria

            # --- CONFIGURACIÓN DE CHUNKING (Estilo PrivateGPT) ---
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1024, 
                chunk_overlap=200,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            splits = text_splitter.split_documents(docs)
            
            if not splits: return False, "Vacío"
            
            if self.vector_store is None: self.vector_store = FAISS.from_documents(splits, self.embeddings)
            else: self.vector_store.add_documents(splits)
            
            self.vector_store.save_local(FAISS_INDEX_PATH)
            return True, f"Ok ({categoria}): {len(splits)} frags"
        except Exception as e: return False, str(e)

    def listar_documentos(self): return []

rag_service = LocalRAGService()