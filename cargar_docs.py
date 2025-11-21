import os
import shutil  # <--- LIBRERÍA PARA BORRAR CARPETAS
import django
from pathlib import Path

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from chatbot.rag_service import rag_service

# Definimos la raíz de documentos
BASE_DOCS_DIR = Path(os.path.join(settings.BASE_DIR, "documentos_unemi"))
FAISS_PATH = Path(os.path.join(settings.BASE_DIR, "faiss_index"))

CATEGORIAS = [
    "general",          # Para todos
    "estudiantes",      # es_estudiante
    "docentes",         # es_profesor
    "administrativos",  # es_administrativo
    "externos",         # es_externo
    "aspirantes",       # es_inscripcionaspirante
    "postulantes",      # es_postulante / es_inscripcionpostulante
    "empleo",           # es_postulanteempleo
    "admision"          # es_inscripcionadmision
]

if __name__ == "__main__":
    print("--- 🧹 LIMPIEZA INICIAL ---")
    
    # 1. Borrar la base de datos antigua del disco
    if FAISS_PATH.exists():
        print(f"   🗑️  Borrando índice antiguo en: {FAISS_PATH}")
        try:
            shutil.rmtree(FAISS_PATH)
            print("   ✅ Disco limpio.")
        except Exception as e:
            print(f"   ❌ Error borrando carpeta: {e}")
    else:
        print("   ✨ No existía índice previo.")

    # 2. Borrar la base de datos de la memoria RAM (CRÍTICO)
    # Si no haces esto, rag_service sigue teniendo los datos viejos cargados en memoria
    rag_service.vector_store = None 
    print("   🧠 Memoria RAM reiniciada.")

    print("\n--- 🚀 INICIANDO INGESTA DE DOCUMENTOS POR ROLES ---")
    
    if not BASE_DOCS_DIR.exists():
        os.makedirs(BASE_DOCS_DIR)
        
    total = 0
    
    for cat in CATEGORIAS:
        ruta_cat = BASE_DOCS_DIR / cat
        
        # Crear carpeta si no existe
        if not ruta_cat.exists():
            print(f"   📁 Creando carpeta: {cat}/ (Pon tus PDFs aquí)")
            os.makedirs(ruta_cat)
            continue
            
        archivos = [f for f in os.listdir(ruta_cat) if f.endswith('.pdf') or f.endswith('.txt')]
        
        if archivos:
            print(f"\n   📂 Procesando [{cat.upper()}]: {len(archivos)} archivos")
            for archivo in archivos:
                full_path = str(ruta_cat / archivo)
                
                # Ingesta
                ok, msg = rag_service.ingerir_documento(full_path, categoria=cat)
                
                if ok:
                    print(f"      ✅ {archivo}")
                    total += 1
                else:
                    print(f"      ❌ {archivo}: {msg}")
        else:
            print(f"   ⚠️  Carpeta vacía: {cat}/")

    print(f"\n--- Fin. {total} documentos indexados en una base de datos LIMPIA. ---")