# cargar_docs.py
"""
Script para cargar documentos PDF/TXT a la base de datos vectorial RAG.
Ejecutar desde la raíz del proyecto: python cargar_docs.py
"""
import os
import sys
import django
from pathlib import Path

# FAISS no requiere SQLite, no necesitamos el fix

# Configurar entorno Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from chatbot.rag_service import rag_service

# Usar settings.BASE_DIR para compatibilidad multiplataforma
DOCUMENTOS_DIR = Path(settings.BASE_DIR) / "documentos_unemi"

if __name__ == "__main__":
    print("=" * 60)
    print("INGESTA DE DOCUMENTOS A RAG LOCAL")
    print("=" * 60)
    
    # Crear carpeta si no existe
    if not DOCUMENTOS_DIR.exists():
        DOCUMENTOS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"\n📁 Carpeta '{DOCUMENTOS_DIR}' creada.")
        print(f"   Pon tus archivos PDF/TXT ahí y ejecuta este script de nuevo.\n")
        sys.exit(0)
    
    # Buscar archivos
    archivos = [
        f for f in DOCUMENTOS_DIR.iterdir()
        if f.suffix.lower() in ['.pdf', '.txt']
    ]
    
    if not archivos:
        print(f"\n⚠️  No hay archivos PDF/TXT en '{DOCUMENTOS_DIR}'")
        print(f"   Coloca tus documentos ahí y ejecuta este script de nuevo.\n")
        sys.exit(0)
    
    print(f"\n📚 Encontrados {len(archivos)} archivo(s):\n")
    
    exitosos = 0
    errores = 0
    
    for archivo in archivos:
        print(f"📄 Procesando: {archivo.name}...")
        success, msg = rag_service.ingerir_documento(str(archivo))
        
        if success:
            print(f"   ✅ Éxito: {msg}\n")
            exitosos += 1
        else:
            print(f"   ❌ Error: {msg}\n")
            errores += 1
    
    print("=" * 60)
    print(f"RESUMEN: {exitosos} exitosos, {errores} errores")
    print(f"Índice FAISS guardado en: {Path(settings.BASE_DIR) / 'faiss_index'}")
    print("=" * 60)

