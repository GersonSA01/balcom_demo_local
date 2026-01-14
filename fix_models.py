
path = r"C:\Users\Gerson\Documents\balcon_demo_local\chatbot\models.py"
try:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace("    id = models.AutoField()", "    id = models.AutoField(primary_key=True)")

    if content != new_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {path}")
        # Count occurrences
        print(f"Replaced {content.count('    id = models.AutoField()')} occurrences.")
    else:
        print("No changes made. String '    id = models.AutoField()' not found.")
except Exception as e:
    print(f"Error: {e}")
