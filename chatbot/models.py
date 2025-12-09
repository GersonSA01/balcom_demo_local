from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime

# Definimos un ID por defecto para evitar errores si no se pasa usuario
ADMINISTRADOR_ID = 116717 

# ==============================================================================
# 1. MODELO BASE (Auditoría y Status)
# ==============================================================================

class ModeloBase(models.Model):
    """ Modelo base para todos los modelos del proyecto """
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


# ==============================================================================
# 2. MODELOS SGA (LEGACY - Managed False)
# Nota: Estos NO heredan de ModeloBase porque son tablas espejo de otra BDD
# ==============================================================================

class SgaCarrera(models.Model):
    nombre = models.CharField(max_length=300, default='')
    class Meta:
        managed = False
        db_table = 'sga_carrera'
        verbose_name = 'Carrera SGA'
    def __str__(self): return self.nombre

class SgaPersona(models.Model):
    nombres = models.CharField(max_length=100, default='')
    apellido1 = models.CharField(max_length=50, default='')
    apellido2 = models.CharField(max_length=50, default='')
    cedula = models.CharField(max_length=20, default='')
    class Meta:
        managed = False
        db_table = 'sga_persona'
    def __str__(self): return f"{self.nombres} {self.apellido1}"

class SgaInscripcion(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    carrera = models.ForeignKey(SgaCarrera, models.DO_NOTHING, db_column='carrera_id')
    class Meta: managed = False; db_table = 'sga_inscripcion'

class SgaProfesor(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'sga_profesor'

class SgaAdministrativo(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'sga_administrativo'

class SgaExterno(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'sga_externo'

class SgaEmpleador(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'sga_empleador'

class PostulaciondipInscripcionpostulante(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'postulaciondip_inscripcionpostulante'

class SgaPostulante(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'sga_postulante'

class SgaPostulanteempleo(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'sga_postulanteempleo'

class AdmisionInscripcion(models.Model):
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    class Meta: managed = False; db_table = 'admision_inscripcion'

class SagestCapinstructoripec(models.Model):
    # Definición mínima para que funcione la Foreign Key
    class Meta:
        managed = False
        db_table = 'sagest_capinstructoripec'

# ==============================================================================
# 3. PERFIL DE USUARIO
# ==============================================================================



class SgaPerfilusuario(models.Model):
    # Campos Principales
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING, db_column='persona_id')
    status = models.BooleanField(default=True, null=True, blank=True)
    inscripcionprincipal = models.BooleanField(default=True, null=True, blank=True)

    # Roles (Foreign Keys)
    inscripcion = models.ForeignKey(SgaInscripcion, models.DO_NOTHING, blank=True, null=True)
    administrativo = models.ForeignKey(SgaAdministrativo, models.DO_NOTHING, blank=True, null=True)
    profesor = models.ForeignKey(SgaProfesor, models.DO_NOTHING, blank=True, null=True)
    empleador = models.ForeignKey(SgaEmpleador, models.DO_NOTHING, blank=True, null=True)
    externo = models.ForeignKey(SgaExterno, models.DO_NOTHING, blank=True, null=True)
    instructor = models.ForeignKey(SagestCapinstructoripec, models.DO_NOTHING, blank=True, null=True)
    
    # Roles Adicionales / Específicos
    inscripcionpostulante = models.ForeignKey(PostulaciondipInscripcionpostulante, models.DO_NOTHING, blank=True, null=True)
    postulante = models.ForeignKey(SgaPostulante, models.DO_NOTHING, blank=True, null=True)
    postulanteempleo = models.ForeignKey(SgaPostulanteempleo, models.DO_NOTHING, blank=True, null=True)
    inscripcionadmision = models.ForeignKey(AdmisionInscripcion, models.DO_NOTHING, blank=True, null=True)


    class Meta:
        managed = False
        db_table = 'sga_perfilusuario'
        # Esto asegura integridad según tu base de datos
        unique_together = (('persona', 'inscripcion', 'administrativo', 'profesor', 'externo', 'instructor'))

# ==============================================================================
# 4. CONFIGURACIÓN DEL CHATBOT (Ahora heredan de ModeloBase)
# ==============================================================================

class ChatbotRol(ModeloBase):
    nombre = models.CharField(max_length=100)
    campo_sga = models.CharField(
        max_length=50, 
        help_text="Nombre exacto del campo en SgaPerfilusuario que valida este rol"
    )
    carreras = models.ManyToManyField(SgaCarrera, blank=True, db_constraint=False)
    
    # NOTA: 'activo' y 'fecha_creacion' se eliminan porque ModeloBase trae 'status' y 'fecha_creacion'
    
    # Alias para compatibilidad con código que busque .activo
    @property
    def activo(self):
        return self.status

    def __str__(self):
        return f"{self.nombre} ({self.campo_sga})"


class RagDocument(ModeloBase):
    """
    Modelo para gestionar los documentos de la Base de Conocimiento (RAG).
    """
    archivo = models.FileField(upload_to='rag_docs/', verbose_name="Archivo Físico")
    nombre = models.CharField(max_length=255, verbose_name="Nombre visible")
    
    roles_permitidos = models.ManyToManyField(ChatbotRol, blank=True, verbose_name="Roles permitidos")

    # Metadatos de Negocio
    is_infinite = models.BooleanField(default=False, verbose_name="Vigencia Indefinida")
    valid_from = models.DateField(null=True, blank=True, verbose_name="Válido desde")
    valid_to = models.DateField(null=True, blank=True, verbose_name="Válido hasta")    
    
    doc_id_pgpt = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID en PrivateGPT")
    is_indexed = models.BooleanField(default=False, verbose_name="Indexado en IA")

    class Meta:
        verbose_name = "Documento de Conocimiento"
        verbose_name_plural = "Documentos de Conocimiento"
        db_table = 'chatbot_rag_documents'

    def __str__(self):
        return self.nombre


class BusinessProcess(ModeloBase):
    """
    Modelo para gestionar flujos y fechas importantes.
    """
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Proceso")
    
    business_context = models.TextField(default="Descripcion", verbose_name="Contexto del proceso")
    process_type = models.CharField(max_length=20,
        choices=[("informativo", "Informativo"), ("operativo", "Operativo")],
        default="informativo",
        verbose_name="Tipo de Proceso"
    )

    source_url = models.CharField(
        max_length=500, blank=True, null=True, verbose_name="Fuente o referencia (opcional)"
    )

    closed_message = models.TextField(verbose_name="Mensaje Personalizado (No Disponible)", blank=True, null=True)

    start_date = models.DateField(verbose_name="Fecha Inicio")
    end_date = models.DateField(verbose_name="Fecha Fin")
    is_infinite = models.BooleanField(default=False, verbose_name="Es Indefinido")
    
    active_message = models.TextField(verbose_name="Mensaje cuando está Activo")
    
    roles_permitidos = models.ManyToManyField(ChatbotRol, blank=True, verbose_name="Roles Permitidos")
    
    need_documentation = models.BooleanField(default=False, verbose_name="Requiere Documentación")

    @property
    def active(self):
        return self.status

    class Meta:
        managed = True 
        db_table = 'chatbot_business_processes'
        verbose_name = 'Proceso de Negocio'
        verbose_name_plural = 'Procesos de Negocio'

    def __str__(self):
        estado = 'Activo' if self.status else 'Inactivo'
        return f"{self.nombre} ({estado})"