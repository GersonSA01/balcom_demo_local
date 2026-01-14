import os
import sys
from io import StringIO
from datetime import datetime
import django
from django.core.management import call_command

# Configurar el entorno de Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import models
from django.contrib.auth.models import User

# Definición de ModeloBase proporcionada por el usuario
MODELO_BASE_CODE = """
class ModeloBase(models.Model):
    \"\"\" Modelo base para todos los modelos del proyecto \"\"\"
    status = models.BooleanField(default=True)
    usuario_creacion = models.ForeignKey(User, related_name='+', blank=True, null=True, on_delete=models.SET_NULL)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    usuario_modificacion = models.ForeignKey(User, related_name='+', blank=True, null=True, on_delete=models.SET_NULL)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        usuario = None
        fecha_modificacion = datetime.now()
        fecha_creacion = None
        update_fields = None
        
        # Lógica para detectar el usuario si se pasa en los argumentos
        if len(args) > 0 and hasattr(args[0], 'user'):
            usuario = args[0].user.id
            
        for key, value in kwargs.items():
            if 'usuario_id' == key:
                usuario = value
            if 'fecha_modificacion' == key:
                fecha_modificacion = value
            if 'fecha_creacion' == key:
                fecha_creacion = value
            if 'update_fields' == key:
                update_fields = value
        
        if self.id:
            self.usuario_modificacion_id = usuario if usuario else ADMINISTRADOR_ID
            self.fecha_modificacion = fecha_modificacion
            if update_fields is not None:
                update_fields = [*update_fields, 'usuario_modificacion_id', 'fecha_modificacion']
                kwargs['update_fields'] = list(set(update_fields))
        else:
            self.usuario_creacion_id = usuario if usuario else ADMINISTRADOR_ID
            self.fecha_creacion = fecha_modificacion
            if fecha_creacion:
                self.fecha_creacion = fecha_creacion
                
        super(ModeloBase, self).save(**kwargs)

    class Meta:
        abstract = True
"""

def generate_models_copy():
    output_filename = 'models_copy.py'
    
    print(f"Generando {output_filename}...")
    
    # Capturar la salida de inspectdb
    out = StringIO()
    call_command('inspectdb', stdout=out)
    inspectdb_content = out.getvalue()
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        # 1. Escribir imports necesarios
        f.write("from django.db import models\n")
        f.write("from django.contrib.auth.models import User\n")
        f.write("from datetime import datetime\n\n")
        
        # Definir constante ADMINISTRADOR_ID si no existe (asumimos 1 por defecto)
        f.write("ADMINISTRADOR_ID = 1\n\n")
        
        # 2. Escribir ModeloBase
        f.write(MODELO_BASE_CODE)
        f.write("\n\n")
        
        # 3. Escribir el contenido de inspectdb
        # Filtramos la línea 'from django.db import models' ya que la pusimos arriba
        lines = inspectdb_content.splitlines()
        for line in lines:
            if line.strip() == "from django.db import models":
                continue
            f.write(line + "\n")
            
    print(f"¡Éxito! Archivo generado en: {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    generate_models_copy()
