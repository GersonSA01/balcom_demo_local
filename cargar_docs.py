# cargar_docs.py
"""
Script para cargar documentos PDF/TXT a la base de datos vectorial RAG con categorización por roles.
Ejecutar desde la raíz del proyecto: python cargar_docs.py
"""
import os
import sys
import django
from pathlib import Path

# Configurar entorno Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from chatbot.rag_service import rag_service

# Usar settings.BASE_DIR para compatibilidad multiplataforma
BASE_DOCS_DIR = Path(settings.BASE_DIR) / "documentos_unemi"

# CATEGORÍAS COMPLETAS DE ROLES
CATEGORIAS_VALIDAS = [
    "general",
    "estudiantes",
    "docentes",
    "administrativos",
    "externos",
    "aspirantes",
    "postulantes",
    "admision",
    "empleo"
]

if __name__ == "__main__":
    print("=" * 70)
    print("INGESTA GRANULAR DE DOCUMENTOS RAG (MULTI-ROL)")
    print("=" * 70)
    
    # Crear carpeta base si no existe
    if not BASE_DOCS_DIR.exists():
        BASE_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"\n📁 Carpeta '{BASE_DOCS_DIR}' creada.")
        print(f"\n   Organiza tus documentos en subcarpetas:")
        print(f"   - general/        (Reglamentos públicos para todos)")
        print(f"   - estudiantes/    (Para 'es_estudiante')")
        print(f"   - docentes/       (Para 'es_profesor')")
        print(f"   - administrativos/(Para 'es_administrativo')")
        print(f"   - externos/       (Para 'es_externo')")
        print(f"   - aspirantes/     (Para 'es_inscripcionaspirante')")
        print(f"   - postulantes/    (Para 'es_postulante' / 'es_inscripcionpostulante')")
        print(f"   - admision/       (Para 'es_inscripcionadmision')")
        print(f"   - empleo/         (Para 'es_postulanteempleo')")
        print(f"\n   Ejecuta este script de nuevo después de organizar.\n")
        sys.exit(0)
    
    total_procesado = 0
    total_errores = 0
    carpetas_creadas = 0
    
    for cat in CATEGORIAS_VALIDAS:
        dir_path = BASE_DOCS_DIR / cat
        
        # Si la carpeta no existe, la creamos vacía para evitar errores
        if not dir_path.exists():
            print(f"\n⚠️  Creando carpeta vacía: {dir_path.name}/")
            os.makedirs(dir_path, exist_ok=True)
            carpetas_creadas += 1
            continue
            
        # Buscar archivos PDF/TXT en la carpeta
        archivos = [
            f for f in dir_path.iterdir()
            if f.is_file() and f.suffix.lower() in ['.pdf', '.txt']
        ]
        
        if not archivos:
            print(f"\n📂 Rol: [{cat.upper()}] - Sin archivos")
            continue
        
        print(f"\n📂 Procesando Rol: [{cat.upper()}] ({len(archivos)} archivo(s))")
        
        for archivo in archivos:
            full_path = str(archivo)
            print(f"   📄 Indexando: {archivo.name}...")
            
            # Enviamos la categoría al servicio RAG
            success, msg = rag_service.ingerir_documento(full_path, categoria=cat)
            
            if success:
                print(f"     ✅ OK: {msg}")
                total_procesado += 1
            else:
                print(f"     ❌ Error: {msg}")
                total_errores += 1
    
    print("\n" + "=" * 70)
    print(f"RESUMEN FINAL:")
    print(f"  ✅ Documentos procesados: {total_procesado}")
    print(f"  ❌ Errores: {total_errores}")
    print(f"  📁 Carpetas creadas: {carpetas_creadas}")
    print(f"  💾 Índice FAISS: {Path(settings.BASE_DIR) / 'faiss_index'}")
    print("=" * 70)
