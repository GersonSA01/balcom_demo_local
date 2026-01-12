import os
import sys
import json
import requests
import time
import django

# ================= CONFIGURACIÓN =================
# Ajusta esto a la URL local de tu entorno de desarrollo
API_URL = "http://127.0.0.1:9090/api/chatbot/chat/" 
ARCHIVO_ENTRADA = "datos.jsonl"
ARCHIVO_SALIDA = "resultados_pruebas.jsonl"
# =================================================

# --- CONFIGURACIÓN DE DJANGO ---
# Aseguramos que el path del proyecto esté en sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Ahora podemos importar modelos de Django
from chatbot.models import SgaPersona, SgaPerfilusuario, SgaMatricula

def procesar_stream_ndjson(response):
    """
    Lee el flujo NDJSON que genera views.py.
    Ignora los mensajes de estado y devuelve el objeto 'final'.
    """
    datos_finales = None
    texto_acumulado = ""

    try:
        # Iteramos sobre las líneas del stream (NDJSON)
        for linea in response.iter_lines():
            if linea:
                decodificado = linea.decode('utf-8')
                try:
                    obj_json = json.loads(decodificado)
                    
                    # Tipo 'status': Son mensajes como "Analizando...", "Consultando normativa..."
                    if obj_json.get("type") == "status":
                        print(f"   [Estado]: {obj_json.get('text')}")
                    
                    # Tipo 'final': Contiene la respuesta definitiva de la IA
                    if obj_json.get("type") == "final":
                        datos_finales = obj_json.get("data")
                        
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error leyendo el stream: {e}")
        
    return datos_finales

def ejecutar_pruebas():
    # 1. Cargar datos del JSONL
    print(f"📂 Cargando datos desde {ARCHIVO_ENTRADA}...")
    filas_datos = []
    try:
        with open(os.path.join(os.path.dirname(__file__), ARCHIVO_ENTRADA), 'r', encoding='utf-8') as f:
            for linea in f:
                if linea.strip():
                    filas_datos.append(json.loads(linea))
    except FileNotFoundError:
        print(f"❌ Error: No se encuentra el archivo de entrada en {os.path.join(os.path.dirname(__file__), ARCHIVO_ENTRADA)}")
        return

    print(f"🚀 Iniciando prueba con {len(filas_datos)} casos...")
    casos_procesados = 0
    output_path = os.path.join(os.path.dirname(__file__), ARCHIVO_SALIDA)

    for i, fila in enumerate(filas_datos):
        cedula = fila.get("cedula", "")
        pregunta = fila.get("pregunta", "")
        resolucion_historica = fila.get("resolucion", "")
        proceso_origen = fila.get("proceso", "General")
        
        # Filtro: Saltar si la resolución está vacía
        if not resolucion_historica or str(resolucion_historica).strip() == "":
            print(f"\n[{i+1}/{len(filas_datos)}] Saltando Usuario: {cedula} (Sin resolución esperada)")
            continue

        casos_procesados += 1
        print(f"\n[{i+1}/{len(filas_datos)}] Probando Usuario: {cedula}")
        print(f"   ❓ Pregunta: {pregunta[:100]}...")

        # --- BÚSQUEDA DE DATOS REALES EN BD ---
        periodo_id = None
        perfil_id = None
        try:
            persona = SgaPersona.objects.filter(cedula=cedula).first()
            if persona:
                print(f"   👤 Usuario identificado: {persona}")
                # Buscamos el primer perfil activo
                perfil = SgaPerfilusuario.objects.filter(persona=persona, status=True).first()
                if perfil:
                    perfil_id = perfil.id
                    # Buscamos la última matrícula no retirada para obtener el periodo
                    if perfil.inscripcion:
                        matricula = SgaMatricula.objects.filter(
                            inscripcion=perfil.inscripcion, 
                            retiradomatricula=False
                        ).order_by('-nivel__periodo__inicio').first()
                        if matricula and matricula.nivel and matricula.nivel.periodo:
                            periodo_id = matricula.nivel.periodo.id
                            print(f"   📌 Perfil: {perfil_id}, Periodo: {periodo_id}")
            else:
                print(f"   ⚠️ Usuario no encontrado en BD. Se usará perfil ficticio.")
        except Exception as e:
            print(f"   ⚠️ Error consultando BD: {e}")

        # 2. Construir el Payload (Cuerpo de la petición)
        payload = {
            "message": pregunta,
            "history": [], # Historial vacío para prueba aislada
            "current_process": proceso_origen,
            "session_data": {
                cedula: {
                    "periodo_id": periodo_id, 
                    "perfiles": [{"id": perfil_id}] if perfil_id else [{"id": 0}]
                }
            }
        }

        inicio = time.time()
        
        try:
            # 3. Enviar petición al Chatbot (stream=True es vital para NDJSON)
            resp = requests.post(API_URL, json=payload, stream=True, timeout=None)
            
            respuesta_ia = "ERROR: Sin respuesta"
            accion_ia = "ERROR"
            fuentes = []

            if resp.status_code == 200:
                output = procesar_stream_ndjson(resp)
                
                if output:
                    respuesta_ia = output.get("response", "")
                    accion_ia = output.get("action", "") # ANSWER, FUNCTION, TECH_ISSUE...
                    fuentes_raw = output.get("sources", [])
                    fuentes = [s.get("title", "Doc") for s in fuentes_raw]
                    
                    print(f"   🤖 Acción IA: {accion_ia}")
                    # Mostramos un fragmento de la respuesta
                    print(f"   📝 Respuesta IA: {respuesta_ia[:100].replace(chr(10), ' ')}...")
            else:
                respuesta_ia = f"HTTP Error {resp.status_code}"
                print(f"   ❌ HTTP Error: {resp.status_code}")

        except Exception as e:
            respuesta_ia = f"Excepción: {str(e)}"
            print(f"   ❌ Excepción: {e}")
            
        duracion = round(time.time() - inicio, 2)

        # 4. Guardar resultados en formato JSONL
        
        resultado_fila = {
            "cedula": cedula,
            "pregunta": pregunta,
            "resolucion_original": resolucion_historica,
            "respuesta_chatbot": respuesta_ia,
            "metadatos": {
                "accion": accion_ia,
                "latencia": duracion,
                "fuentes": fuentes,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        try:
            with open(output_path, "a", encoding="utf-8") as f_out:
                f_out.write(json.dumps(resultado_fila, ensure_ascii=False) + "\n")
            print(f"   💾 Resultado guardado en {ARCHIVO_SALIDA}")
        except Exception as e:
            print(f"   ❌ Error guardando resultado: {e}")

    if casos_procesados > 0:
        print(f"\n✅ Pruebas finalizadas. Casos procesados: {casos_procesados}. Resultados en: {output_path}")
    else:
        print(f"\n⚠️ Pruebas finalizadas. No se procesó ningún caso (verifique 'resolucion' en {ARCHIVO_ENTRADA}).")

if __name__ == "__main__":
    ejecutar_pruebas()
