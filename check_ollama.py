#!/usr/bin/env python
"""
Script de diagnóstico para verificar Ollama y el modelo configurado
"""
import requests
import json
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b-instruct-q4_K_M')

print("=" * 60)
print("DIAGNÓSTICO DE OLLAMA")
print("=" * 60)
print(f"\n📡 URL de Ollama: {OLLAMA_BASE_URL}")
print(f"🤖 Modelo configurado: {OLLAMA_MODEL}\n")

# 1. Verificar si Ollama está corriendo
print("1️⃣ Verificando conexión con Ollama...")
try:
    response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
    if response.status_code == 200:
        print("   ✅ Ollama está corriendo")
        models = response.json().get('models', [])
        print(f"   📦 Modelos instalados: {len(models)}")
        
        # 2. Verificar si el modelo está instalado
        print(f"\n2️⃣ Verificando si el modelo '{OLLAMA_MODEL}' está instalado...")
        model_names = [model.get('name', '') for model in models]
        model_available = any(OLLAMA_MODEL in name for name in model_names)
        
        if model_available:
            print(f"   ✅ Modelo '{OLLAMA_MODEL}' está instalado")
            # Mostrar el nombre exacto
            exact_match = [name for name in model_names if OLLAMA_MODEL in name]
            if exact_match:
                print(f"   📝 Nombre exacto: {exact_match[0]}")
        else:
            print(f"   ❌ Modelo '{OLLAMA_MODEL}' NO está instalado")
            print(f"\n   💡 Para instalarlo, ejecuta:")
            print(f"      ollama pull {OLLAMA_MODEL}")
            
            # Mostrar modelos similares
            print(f"\n   📋 Modelos disponibles similares:")
            similar = [name for name in model_names if 'qwen' in name.lower() or '3b' in name.lower()]
            for name in similar[:5]:
                print(f"      - {name}")
        
        # 3. Listar todos los modelos
        print(f"\n3️⃣ Todos los modelos instalados:")
        if models:
            for model in models:
                name = model.get('name', 'N/A')
                size = model.get('size', 0)
                size_gb = size / (1024**3) if size > 0 else 0
                print(f"   - {name} ({size_gb:.2f} GB)")
        else:
            print("   ⚠️ No hay modelos instalados")
            
    else:
        print(f"   ❌ Ollama respondió con código {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("   ❌ No se pudo conectar con Ollama")
    print(f"\n   💡 Asegúrate de que Ollama esté ejecutándose:")
    print(f"      - En Windows: Abre la aplicación Ollama")
    print(f"      - Verifica que esté en: {OLLAMA_BASE_URL}")
    
except Exception as e:
    print(f"   ❌ Error: {str(e)}")

print("\n" + "=" * 60)
print("FIN DEL DIAGNÓSTICO")
print("=" * 60)

