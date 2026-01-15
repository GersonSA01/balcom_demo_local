import os

file_path = r"c:\Users\Gerson\Documents\balcon_demo_local\chatbot\models.py"
search_text = '"role": ["faq_system"], # Rol especial para filtrar rápido'
replace_text = '"role": "faq_system", # Rol especial para filtrar rápido'

def patch_file():
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        print(f"Reading {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if search_text not in content:
            print("Search text NOT found in file. Maybe already patched?")
            # Check if it's already patched
            if replace_text in content:
                 print("File already contains the replacement text.")
            else:
                 print("Could not find the target line.")
            return

        print("Applying patch...")
        new_content = content.replace(search_text, replace_text)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("File updated successfully.")

    except Exception as e:
        print(f"Error patching file: {e}")

if __name__ == "__main__":
    patch_file()
