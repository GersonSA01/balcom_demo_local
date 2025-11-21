import os
import json
import re
import logging
from pathlib import Path
from django.conf import settings
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import FAISS

# Tu procesador actual
from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = os.path.join(settings.BASE_DIR, "faiss_index")

class LocalRAGService:
    def __init__(self):
        # 1. Embeddings
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text", 
            base_url=settings.OLLAMA_BASE_URL
        )
        
        self.vector_store = None
        self._cargar_indice()

        # 2. LLM (Optimizado)
        self.llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            format="json", 
            temperature=0, 
            base_url=settings.OLLAMA_BASE_URL,
            keep_alive="1h",
            num_ctx=3072,
            num_thread=settings.OLLAMA_NUM_THREAD,
        )
        
        # 3. Prompt RAG (Español y Directo)
        self.rag_prompt = """ERES UN ASISTENTE EXPERTO PARA UNEMI.
        ROL ACTUAL DEL USUARIO: {user_role}
        Responde exclusivamente con JSON válido.

        CONTEXTO:
        {context}

        CONSULTA DEL USUARIO:
        {query}

        INSTRUCCIONES:
        1. RESPONDE DIRECTAMENTE usando SOLO el contexto proporcionado.
        2. Adapta el tono al rol {user_role}.
        3. Si el contexto contiene la respuesta, establece "has_information": true.
        4. Si no, establece "has_information": false.

        FORMATO JSON DE SALIDA:
        {{
          "has_information": boolean,
          "need_contact": boolean,
          "response": "Respuesta precisa en español",
          "sources": ["nombre_de_archivo"]
        }}
        """

        # 4. Prompt Reformulador (HyDE - Solo Normalización Técnica)
        self.reformer_prompt = """ACTÚA COMO UN EXPERTO EN TRÁMITES UNIVERSITARIOS.
        DOMINIO: Reglamento de Grado, Admisión y Procesos Académicos (UNEMI).
        
        TAREA: TRADUCE la consulta del usuario a TERMINOLOGÍA TÉCNICA del reglamento.
        
        INSTRUCCIONES:
        - Reescribe usando TERMINOLOGÍA DE REGLAMENTO.
        - Ejemplos:
          * "falta" -> "justificación inasistencia" O "sanción disciplinaria"
          * "borrar materia" -> "retiro de asignatura"
          * "matricularme" -> "proceso de matrícula"
        - Mantén el sentido original pero usa términos técnicos precisos.
        
        CONSULTA: "{query}"
        ROL: "{user_role}"
        
        JSON DE SALIDA:
        {{
          "search_query": "string (Término técnico optimizado para búsqueda)"
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
                logger.info("✅ Índice FAISS cargado.")
            except Exception as e: 
                logger.error(f"❌ Error cargando índice: {e}")
                self.vector_store = None
        else: 
            self.vector_store = None

    def _extraer_json(self, texto):
        try:
            match = re.search(r"\{[\s\S]*\}", texto)
            return json.loads(match.group(0)) if match else json.loads(texto)
        except: return None


    def _reformular_consulta(self, query: str, user_role: str) -> dict:
        """
        Reformula la consulta del usuario a términos técnicos del reglamento.
        Nota: La ambigüedad ya se maneja en intent_parser, aquí solo reformulamos.
        """
        try:
            prompt = self.reformer_prompt.format(query=query, user_role=user_role)
            res = self.llm.invoke(prompt)
            data = self._extraer_json(res.content)
            
            # Extraer search_query (ignoramos cualquier is_ambiguous que venga del LLM)
            query_tecnica = data.get("search_query", query) if data else query
            
            # DEBUG PRINT: Ver reformulación
            print(f"\n🤖 [REFORMULADO] '{query}' -> '{query_tecnica}'")
            
            return {"search_query": query_tecnica}
        except Exception as e:
            logger.error(f"Error reformulando: {e}")
            return {"search_query": query}

    def consultar(self, query: str, intent_data: dict, categorias_permitidas: list, user_role_name: str):
        if not self.vector_store: self._cargar_indice()
        if not self.vector_store: return self._respuesta_fallback("Sistema en mantenimiento.")

        try:
            # 1. REFORMULACIÓN INTELIGENTE (Solo normalización técnica)
            analisis = self._reformular_consulta(query, user_role_name)
            query_tecnica = analisis.get("search_query", query)
            
            # Multi-query: Buscar con original + reformulada (boost sin keywords)
            queries_finales = list(dict.fromkeys([query, query_tecnica]))
            print(f"🤖 [BUSQUEDA] Queries: {queries_finales}")

            # 2. BÚSQUEDA WIDE SOLO VECTORIAL
            candidatos_brutos = []
            for q in queries_finales:
                raw_docs = self.vector_store.similarity_search_with_score(q, k=30)
                
                for doc, distance in raw_docs:
                    if doc.metadata.get("categoria") not in categorias_permitidas:
                        continue
                    
                    # Score vectorial normalizado (0 a 1)
                    vector_score = 1 / (1 + distance)
                    candidatos_brutos.append((doc, vector_score))

            # 3. RE-RANKING Y BUCKETING
            candidatos_brutos.sort(key=lambda x: x[1], reverse=True)
            
            docs_finales = []
            ids_vistos = set()
            fuentes_vistas = {}
            
            MAX_TOTAL = 5
            UMBRAL = 0.30  # Más permisivo con solo embeddings
            
            for doc, score in candidatos_brutos:
                if score < UMBRAL: continue
                
                h = hash(doc.page_content)
                if h in ids_vistos: continue
                
                nombre = Path(doc.metadata.get("source", "desc")).name
                conteo = fuentes_vistas.get(nombre, 0)
                
                limite = 3 if "REGLAMENTO" in nombre.upper() else 2
                if conteo >= limite and len(docs_finales) >= 2: continue
                
                fuentes_vistas[nombre] = conteo + 1
                ids_vistos.add(h)
                docs_finales.append(doc)
                if len(docs_finales) >= MAX_TOTAL: break

            if not docs_finales:
                print("❌ [RAG] No se encontraron documentos relevantes tras filtrado.")
                return self._respuesta_fallback(f"No encontré normativa específica sobre '{query_tecnica}'.")

            # 4. GENERACIÓN
            context = "\n\n".join([f"DOC: {Path(d.metadata.get('source','?')).name}\nTXT: {d.page_content}" for d in docs_finales])
            
            # DEBUG PRINT: Ver contexto enviado
            print(f"\n📄 [CONTEXTO] {len(docs_finales)} chunks enviados al LLM:\n{context[:500]}...\n")
            
            final_prompt = self.rag_prompt.format(context=context, query=query, user_role=user_role_name)
            ai_response = self.llm.invoke(final_prompt)
            
            # DEBUG PRINT: Ver respuesta cruda del LLM
            print(f"\n📥 [LLM OUTPUT]:\n{ai_response.content}\n")
            
            resultado = self._extraer_json(ai_response.content)
            if not resultado: 
                resultado = {"has_information": True, "need_contact": False, "response": ai_response.content}
            
            resultado["sources"] = list(fuentes_vistas.keys())
            
            if not resultado.get("has_information"):
                resultado["response"] = f"Revisé la normativa sobre '{query_tecnica}' pero no hallé el dato exacto."
                resultado["need_contact"] = True
            
            return resultado

        except Exception as e:
            logger.error(f"Error RAG: {e}", exc_info=True)
            return self._respuesta_fallback("Error técnico procesando consulta.")

    def _respuesta_fallback(self, mensaje: str):
        return {"has_information": False, "need_contact": True, "response": mensaje, "sources": []}

    # ... (El método ingerir_documento sigue igual, es correcto) ...
    def ingerir_documento(self, file_path: str, categoria: str = "general", auto_save: bool = True):
        processor = DocumentProcessor()
        try:
            documents = processor.process_document(
                file_path,
                additional_metadata={"categoria": categoria, "role_filter": categoria}
            )
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(documents, self.embeddings)
            else:
                self.vector_store.add_documents(documents)
            
            if auto_save:
                self.vector_store.save_local(FAISS_INDEX_PATH)
            return True, f"Ingestado: {len(documents)} fragmentos."
        except Exception as e:
            logger.error(f"Error ingesta {file_path}: {e}")
            return False, str(e)

    def guardar_indice(self):
        if self.vector_store:
            self.vector_store.save_local(FAISS_INDEX_PATH)
            return True
        return False

rag_service = LocalRAGService()