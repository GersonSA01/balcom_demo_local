
import requests
import json

API_URL = "http://localhost:8001"
TEST_FILE_NAME = "test_faq_debug.txt"
TEST_CONTENT = "Esta es una pregunta de prueba para depurar la ingesta."

def debug_ingest():
    ingest_url = f"{API_URL}/v1/ingest/file"
    
    print(f"Subiendo archivo de prueba a: {ingest_url}")
    try:
        files = {'file': (TEST_FILE_NAME, TEST_CONTENT, 'text/plain')}
        resp = requests.post(ingest_url, files=files, timeout=10)
        
        print(f"Status Code: {resp.status_code}")
        print(f"Raw Response: {resp.text}")
        
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            if data:
                doc_id = data[0]['doc_id']
                print(f"✅ Ingesta exitosa. Doc ID: {doc_id}")
                
                # Check persistence immediately
                print("Verificando persistencia...")
                list_resp = requests.get(f"{API_URL}/v1/ingest/list")
                all_docs = list_resp.json().get('data', [])
                found = any(d['doc_id'] == doc_id for d in all_docs)
                if found:
                    print(f"✅ Documento encontrado en /list.")
                else:
                    print(f"❌ Documento NO encontrado en /list (Persistencia fallida).")
            else:
                print("⚠️ Respuesta 200 pero sin datos.")
    
    except Exception as e:
        print(f"❌ Excepción: {e}")

if __name__ == "__main__":
    debug_ingest()
