
import requests

API_URL = "http://localhost:8001"

try:
    print(f"Fetching docs from {API_URL}/v1/ingest/list ...")
    resp = requests.get(f"{API_URL}/v1/ingest/list")
    
    if resp.status_code == 200:
        data = resp.json()
        docs = data.get('data', [])
        print(f"Found {len(docs)} documents.")
        
        # Print first 5 docs to see IDs
        for d in docs[:5]:
            print(f"ID: {d.get('doc_id')} | Name: {d.get('doc_metadata', {}).get('file_name')}")
            
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

except Exception as e:
    print(f"Exception: {e}")
