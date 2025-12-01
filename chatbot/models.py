from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

ADMINISTRADOR_ID = 116717

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
                
        super(ModeloBase, self).save(**kwargs) # Uso de super() estándar de Django

    class Meta:
        abstract = True



class RagDocument(ModeloBase):
    """
    Modelo para gestionar los documentos de la Base de Conocimiento (RAG).
    Es la 'Fuente de la Verdad' local.
    """
    archivo = models.FileField(upload_to='rag_docs/', verbose_name="Archivo Físico")
    nombre = models.CharField(max_length=255, verbose_name="Nombre visible")
    
    # Metadatos de Negocio
    roles = models.JSONField(default=list, verbose_name="Roles permitidos")
    is_infinite = models.BooleanField(default=False, verbose_name="Vigencia Indefinida")
    valid_from = models.DateField(null=True, blank=True, verbose_name="Válido desde")
    valid_to = models.DateField(null=True, blank=True, verbose_name="Válido hasta")
    
    # Referencia al sistema externo (PrivateGPT)
    doc_id_pgpt = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID en PrivateGPT")
    is_indexed = models.BooleanField(default=False, verbose_name="Indexado en IA")

    class Meta:
        verbose_name = "Documento de Conocimiento"
        verbose_name_plural = "Documentos de Conocimiento"
        db_table = 'chatbot_rag_documents'

    def __str__(self):
        return self.nombre


class BusinessProcess(ModeloBase):
    name = models.CharField(max_length=255, verbose_name="Nombre del Proceso")
    business_context = models.TextField(default="Descripcion" ,verbose_name="Contexto del proceso")
    process_type = models.CharField(max_length=20,
        choices=[("informativo", "Informativo"), ("operativo", "Operativo")],
        default="informativo",
        verbose_name="Tipo de Proceso"
    )

    source_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Fuente o referencia (opcional)"
    )

    start_date = models.DateField(verbose_name="Fecha Inicio")
    end_date = models.DateField(verbose_name="Fecha Fin")
    is_infinite = models.BooleanField(default=False, verbose_name="Es Indefinido")
    active_message = models.TextField(verbose_name="Mensaje cuando está Activo")
    roles = models.JSONField(default=list, verbose_name="Roles Permitidos")
    need_documentation = models.BooleanField(default=False, verbose_name="Requiere Documentación")

    class Meta:
        # managed = True permite a Django crear la tabla con 'python manage.py migrate'
        managed = True 
        db_table = 'Business_processes'
        verbose_name = 'Proceso de Negocio'
        verbose_name_plural = 'Procesos de Negocio'

    def __str__(self):
        return f"{self.name} ({'Activo' if self.status else 'Inactivo'})"

# ==============================================================================
# MODELO: PERSONA (SgaPersona)
# Contiene toda la información demográfica. Se han desacoplado las FKs
# innecesarias convirtiéndolas a IntegerField para optimizar la carga.
# ==============================================================================

class SgaPersona(models.Model):
    nombres = models.CharField(max_length=100)
    apellido1 = models.CharField(max_length=50)
    apellido2 = models.CharField(max_length=50)
    cedula = models.CharField(max_length=20)
    pasaporte = models.CharField(max_length=20)
    nacimiento = models.DateField()
    
    # FKs convertidas a IntegerField (IDs directos) para evitar cargar modelos externos
    provincia_id = models.IntegerField(db_column='provincia_id', blank=True, null=True)
    sexo_id = models.IntegerField(db_column='sexo_id')
    
    nacionalidad = models.CharField(max_length=100)
    direccion = models.CharField(max_length=300)
    direccion2 = models.CharField(max_length=300)
    num_direccion = models.CharField(max_length=15)
    sector = models.CharField(max_length=300)
    ciudad = models.CharField(max_length=50)
    telefono = models.CharField(max_length=50)
    telefono_conv = models.CharField(max_length=50)
    email = models.CharField(max_length=200)
    
    # Usuario de sistema (Login) - Se mantiene como FK a AuthUser
    usuario = models.ForeignKey('AuthUser', models.DO_NOTHING, blank=True, null=True)
    
    # Más FKs convertidas a IntegerField
    sangre_id = models.IntegerField(db_column='sangre_id', blank=True, null=True)
    
    emailinst = models.CharField(max_length=200)
    
    parroquia_id = models.IntegerField(db_column='parroquia_id', blank=True, null=True)
    pais_id = models.IntegerField(db_column='pais_id', blank=True, null=True)
    
    anioresidencia = models.IntegerField()
    
    # Datos de nacimiento y origen (IDs)
    paisnacimiento_id = models.IntegerField(db_column='paisnacimiento_id', blank=True, null=True)
    provincianacimiento_id = models.IntegerField(db_column='provincianacimiento_id', blank=True, null=True)
    cantonnacimiento_id = models.IntegerField(db_column='cantonnacimiento_id', blank=True, null=True)
    parroquianacimiento_id = models.IntegerField(db_column='parroquianacimiento_id', blank=True, null=True)
    
    referencia = models.CharField(max_length=100)
    identificacioninstitucion = models.CharField(max_length=20)
    regitrocertificacion = models.CharField(max_length=20)
    libretamilitar = models.CharField(max_length=20)
    servidorcarrera = models.BooleanField()
    telefonoextension = models.CharField(max_length=20)
    ruc = models.CharField(max_length=20, blank=True, null=True)
    tipocelular = models.IntegerField()
    archivocroquis = models.CharField(max_length=100, blank=True, null=True)
    fechaingresoies = models.DateField(blank=True, null=True)
    fechasalidaies = models.DateField(blank=True, null=True)
    concursomeritos = models.BooleanField()
    periodosabatico = models.BooleanField()
    fechainicioperiodosabatico = models.DateField(blank=True, null=True)
    fechafinperiodosabatico = models.DateField(blank=True, null=True)
    tipopersona = models.IntegerField(blank=True, null=True)
    contribuyenteespecial = models.BooleanField()
    real = models.BooleanField()
    status = models.BooleanField()
    
    # Auditoría
    usuario_creacion = models.ForeignKey('AuthUser', models.DO_NOTHING, related_name='sgapersona_creacion', blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    usuario_modificacion = models.ForeignKey('AuthUser', models.DO_NOTHING, related_name='sgapersona_modificacion', blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    
    # Otros campos específicos
    lgtbi = models.BooleanField()
    datosactualizados = models.IntegerField()
    confirmarextensiontelefonia = models.BooleanField()
    
    credo_id = models.IntegerField(db_column='credo_id', blank=True, null=True)
    preferenciapolitica_id = models.IntegerField(db_column='preferenciapolitica_id', blank=True, null=True)
    
    idusermoodle = models.IntegerField(blank=True, null=True)
    observacionppl = models.CharField(max_length=500, blank=True, null=True)
    ppl = models.BooleanField()
    telefono2 = models.CharField(max_length=50, blank=True, null=True)
    confirmardatosbienestar = models.BooleanField()
    fechaactualizabienestar = models.DateField(blank=True, null=True)
    labora = models.IntegerField(blank=True, null=True)
    sectorlugar = models.IntegerField(blank=True, null=True)
    unicoestudia = models.IntegerField(blank=True, null=True)
    estadogestacion = models.BooleanField()
    eszurdo = models.BooleanField()
    aceptaservicio = models.IntegerField(blank=True, null=True)
    mesembarazo = models.IntegerField(blank=True, null=True)
    niniera = models.BooleanField()
    numeromiembrosfamilia = models.IntegerField(blank=True, null=True)
    localizacionactualizada = models.BooleanField()
    idusermoodleposgrado = models.IntegerField(blank=True, null=True)
    identificadororcid = models.CharField(max_length=250, blank=True, null=True)
    visualizar_tutorial = models.BooleanField()
    ciudadela = models.CharField(max_length=300)
    zona = models.IntegerField(blank=True, null=True)
    archivoplanillaluz = models.CharField(max_length=100, blank=True, null=True)
    
    paisnacionalidad_id = models.IntegerField(db_column='paisnacionalidad_id', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sga_persona'


# ==============================================================================
# MODELO: PERFIL USUARIO (SgaPerfilusuario)
# Conecta a la persona con sus roles (Estudiante, Profesor, etc.)
# Se usan IntegerField apuntando a los IDs para no cargar tablas de roles gigantes.
# ==============================================================================

class SgaPerfilusuario(models.Model):
    # Relación principal: Esta SÍ debe ser ForeignKey para navegar persona.perfiles
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING)
    
    # Roles: Convertidos a IntegerField mapeados a la columna FK original.
    # Esto permite verificar existencia (if perfil.inscripcion) sin importar el modelo.
    inscripcion = models.IntegerField(db_column='inscripcion_id', blank=True, null=True)
    administrativo = models.IntegerField(db_column='administrativo_id', blank=True, null=True)
    profesor = models.IntegerField(db_column='profesor_id', blank=True, null=True)
    
    inscripcionprincipal = models.BooleanField()
    
    empleador = models.IntegerField(db_column='empleador_id', blank=True, null=True)
    externo = models.IntegerField(db_column='externo_id', blank=True, null=True)
    
    status = models.BooleanField()
    
    # Auditoría
    usuario_creacion = models.ForeignKey('AuthUser', models.DO_NOTHING, blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    usuario_modificacion = models.ForeignKey('AuthUser', models.DO_NOTHING, related_name='sgaperfil_modificacion', blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    
    # Otros roles
    instructor = models.IntegerField(db_column='instructor_id', blank=True, null=True)
    inscripcionaspirante = models.IntegerField(db_column='inscripcionaspirante_id', blank=True, null=True)
    visible = models.BooleanField()
    inscripcionpostulante = models.IntegerField(db_column='inscripcionpostulante_id', blank=True, null=True)
    postulante = models.IntegerField(db_column='postulante_id', blank=True, null=True)
    postulanteempleo = models.IntegerField(db_column='postulanteempleo_id', blank=True, null=True)
    inscripcionadmision = models.IntegerField(db_column='inscripcionadmision_id', blank=True, null=True)
    instructorejecutiva = models.IntegerField(db_column='instructorejecutiva_id', blank=True, null=True)
    inscritoejecutivo = models.IntegerField(db_column='inscritoejecutivo_id', blank=True, null=True)
    instructorformacionejecutiva = models.IntegerField(db_column='instructorformacionejecutiva_id', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sga_perfilusuario'
        # unique_together removido del managed=False para evitar validaciones estrictas en Django
        # que requieran los otros modelos, la base de datos ya lo garantiza.


# ==============================================================================
# MODELO: AUTH USER (Tabla nativa de Django/Sistema)
# Necesaria porque SgaPersona y Perfil hacen referencia a ella.
# ==============================================================================

class AuthUser(models.Model):
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    password = models.CharField(max_length=128)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    is_superuser = models.BooleanField()
    last_login = models.DateTimeField(blank=True, null=True)
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'