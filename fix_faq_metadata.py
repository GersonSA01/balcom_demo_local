import os
import django
import sys

# Add the project root to the python path
sys.path.append(os.getcwd())

# Set up Django environment
# Assuming 'config.settings' based on the directory structure. 
# If this fails, checking manage.py would be the next step.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from chatbot.models import Faq

def reindex_faqs():
    print("Iniciando re-indexación de FAQs...")
    faqs = Faq.objects.all()
    count = faqs.count()
    print(f"Se encontraron {count} FAQs.")

    for i, faq in enumerate(faqs, 1):
        try:
            print(f"[{i}/{count}] Procesando FAQ ID {faq.id}: {faq.pregunta[:50]}...")
            # Forzamos el guardado para disparar la señal post_save
            # No cambiamos nada, pero el save() dispara la señal 'sincronizar_faq_con_ia'
            faq.save()
        except Exception as e:
            print(f"❌ Error procesando FAQ {faq.id}: {e}")

    print("✅ Re-indexación completada.")

if __name__ == "__main__":
    reindex_faqs()
