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







# ---- STUBS mínimos (solo si NO existen ya en tu models.py) ----
class SagestOpcionsistema(models.Model):
    class Meta:
        managed = False
        db_table = 'sagest_opcionsistema'

class SagestCarreradepartamento(models.Model):
    class Meta:
        managed = False
        db_table = 'sagest_carreradepartamento'

class BalconAgente(models.Model):
    class Meta:
        managed = False
        db_table = 'balcon_agente'


class BalconServicio(models.Model):
    status = models.BooleanField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    nombre = models.CharField(max_length=500, blank=True, null=True)
    descripcion = models.TextField()
    estado = models.BooleanField()
    usuario_creacion = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    usuario_modificacion = models.ForeignKey(
        User, models.DO_NOTHING, related_name='balconservicio_usuario_modificacion_set', blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = 'balcon_servicio'

class BalconServicioOpcsistema(models.Model):
    servicio = models.ForeignKey(BalconServicio, models.DO_NOTHING)
    opcionsistema = models.ForeignKey(SagestOpcionsistema, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'balcon_servicio_opcsistema'
        unique_together = (('servicio', 'opcionsistema'),)




class BalconServiciodepartamento(models.Model):
    status = models.BooleanField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    reasignar = models.BooleanField()
    carreradepartamento = models.ForeignKey(SagestCarreradepartamento, models.DO_NOTHING, blank=True, null=True)
    servicio = models.ForeignKey(BalconServicio, models.DO_NOTHING, blank=True, null=True)
    usuario_creacion = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    usuario_modificacion = models.ForeignKey(
        User, models.DO_NOTHING, related_name='balconserviciodepartamento_usuario_modificacion_set', blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = 'balcon_serviciodepartamento'
        unique_together = (('servicio', 'carreradepartamento'),)


class BalconProcesoservicio(models.Model):
    status = models.BooleanField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    tiempomaximo = models.IntegerField()
    tiempominimo = models.IntegerField()
    minutos = models.IntegerField()
    url = models.CharField(max_length=200, blank=True, null=True)

    # IMPORTANTE: BalconProceso debe existir en tu models.py
    proceso = models.ForeignKey('BalconProceso', models.DO_NOTHING, blank=True, null=True)
    servicio = models.ForeignKey(BalconServicio, models.DO_NOTHING, blank=True, null=True)

    usuario_creacion = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    usuario_modificacion = models.ForeignKey(
        User, models.DO_NOTHING, related_name='balconprocesoservicio_usuario_modificacion_set', blank=True, null=True
    )
    opcsistema = models.ForeignKey(SagestOpcionsistema, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'balcon_procesoservicio'


class BalconRequisito(models.Model):
    status = models.BooleanField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    descripcion = models.TextField()

    usuario_creacion = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    usuario_modificacion = models.ForeignKey(
        User, models.DO_NOTHING, related_name='balconrequisito_usuario_modificacion_set', blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = 'balcon_requisito'


class BalconSolicitud(models.Model):
    status = models.BooleanField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    codigo = models.CharField(max_length=1000, blank=True, null=True)
    estado = models.IntegerField()
    tipo = models.IntegerField()
    archivo = models.CharField(max_length=100, blank=True, null=True)
    descripcion = models.TextField()
    externo = models.BooleanField()
    numero = models.IntegerField(blank=True, null=True)

    agente = models.ForeignKey(BalconAgente, models.DO_NOTHING, blank=True, null=True)
    perfil = models.ForeignKey('SgaPerfilusuario', models.DO_NOTHING, blank=True, null=True)
    solicitante = models.ForeignKey('SgaPersona', models.DO_NOTHING, blank=True, null=True)

    usuario_creacion = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    usuario_modificacion = models.ForeignKey(
        User, models.DO_NOTHING, related_name='balconsolicitud_usuario_modificacion_set', blank=True, null=True
    )

    tiempoespera = models.IntegerField(blank=True, null=True)
    tiempoesperareal = models.IntegerField(blank=True, null=True)
    agenteactual = models.ForeignKey('SgaPersona', models.DO_NOTHING, related_name='balconsolicitud_agenteactual_set', blank=True, null=True)
    solicitud_devuelta = models.BooleanField()
    fecha_expiracion_solicitud = models.DateTimeField(blank=True, null=True)
    solicitudasociada = models.ForeignKey('self', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'balcon_solicitud'





class BalconRequisitosconfiguracion(models.Model):
    status = models.BooleanField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    obligatorio = models.BooleanField()
    activo = models.BooleanField()

    requisito = models.ForeignKey(BalconRequisito, models.DO_NOTHING, blank=True, null=True)
    servicio = models.ForeignKey(BalconProcesoservicio, models.DO_NOTHING, blank=True, null=True)

    usuario_creacion = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    usuario_modificacion = models.ForeignKey(
        User, models.DO_NOTHING, related_name='balconrequisitosconfiguracion_usuario_modificacion_set', blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = 'balcon_requisitosconfiguracion'


class BalconRequisitossolicitud(models.Model):
    status = models.BooleanField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)
    archivo = models.CharField(max_length=100)

    requisito = models.ForeignKey(BalconRequisitosconfiguracion, models.DO_NOTHING)
    solicitud = models.ForeignKey(BalconSolicitud, models.DO_NOTHING)

    usuario_creacion = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    usuario_modificacion = models.ForeignKey(
        User, models.DO_NOTHING, related_name='balconrequisitossolicitud_usuario_modificacion_set', blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = 'balcon_requisitossolicitud'
# ==============================================================================
# 2. MODELOS SGA (LEGACY - Managed False)
# Nota: Estos NO heredan de ModeloBase porque son tablas espejo de otra BDD
# ==============================================================================
class SgaCoordinacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    alias = models.CharField(max_length=100, blank=True, null=True)
    class Meta:
        managed = False
        db_table = 'sga_coordinacion'
    
    def __str__(self):
        return self.nombre


# EN TU ARCHIVO models.py

class SgaCarrera(models.Model):
    """Tabla legacy: sga_carrera (definición mínima para evitar desfaces de columnas)."""
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sga_carrera'

    def __str__(self):
        return self.nombre or str(self.id)


class SgaCoordinacionCarrera(models.Model):
    """Tabla puente legacy: sga_coordinacion_carrera (Coordinación <-> Carrera)."""
    coordinacion = models.ForeignKey(SgaCoordinacion, models.DO_NOTHING)
    carrera = models.ForeignKey(SgaCarrera, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'sga_coordinacion_carrera'
        unique_together = (('coordinacion', 'carrera'),)


class SgaPersona(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombres = models.CharField(max_length=100)
    apellido1 = models.CharField(max_length=50)
    apellido2 = models.CharField(max_length=50)
    cedula = models.CharField(max_length=20)
    # Vinculación con el usuario de Django (AuthUser)
    usuario = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    
    class Meta:
        managed = False
        db_table = 'sga_persona'

    def __str__(self):
        return f"{self.nombres} {self.apellido1} {self.apellido2}"

class SgaPeriodo(models.Model):
    """
    Tabla de Periodos Académicos.
    El destino final de la consulta.
    """
    nombre = models.CharField(max_length=200)
    inicio = models.DateField()
    fin = models.DateField()
    activo = models.BooleanField()
    
    class Meta:
        managed = False
        db_table = 'sga_periodo'
    
    def __str__(self):
        return self.nombre


class SgaNivel(models.Model):
    """
    Tabla de Nivel (Conecta la matrícula con el periodo).
    """
    periodo = models.ForeignKey(SgaPeriodo, models.DO_NOTHING, verbose_name="Periodo")
    # Otros campos comunes en SGA:
    # nivel = models.IntegerField() 
    # paralelo = models.CharField(...)
    # carrera = models.ForeignKey(...) 
    
    class Meta:
        managed = False
        db_table = 'sga_nivel'
    
    def __str__(self):
        return f"Nivel {self.id} - {self.periodo}"


class SgaInscripcion(models.Model):
    id = models.BigAutoField(primary_key=True)
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING)
    carrera = models.ForeignKey(SgaCarrera, models.DO_NOTHING)
    activo = models.BooleanField(default=True)
    
    class Meta:
        managed = False
        db_table = 'sga_inscripcion'

class BalconCategoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    descripcion = models.TextField()
    estado = models.BooleanField()
    
    class Meta:
        managed = False
        db_table = 'balcon_categoria'
    
    def __str__(self):
        return self.descripcion

class BalconCategoriaCoordinaciones(models.Model):
    # Tabla intermedia que dice qué coordinación puede ver qué categoría
    categoria = models.ForeignKey(BalconCategoria, models.DO_NOTHING)
    coordinacion = models.ForeignKey(SgaCoordinacion, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'balcon_categoria_coordinaciones'
        unique_together = (('categoria', 'coordinacion'),)


class BalconTipo(models.Model):
    id = models.BigAutoField(primary_key=True)
    descripcion = models.TextField()
    estado = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'balcon_tipo'

    def __str__(self):
        return self.descripcion


class BalconProceso(models.Model):
    id = models.BigAutoField(primary_key=True)
    descripcion = models.TextField()
    categoria = models.ForeignKey(BalconCategoria, models.DO_NOTHING, blank=True, null=True)
    activo = models.BooleanField()

    # ✅ CAMPOS QUE TU VIEW USA
    tiempoestimado = models.TextField(blank=True, null=True)
    tipo = models.ForeignKey(BalconTipo, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'balcon_proceso'

    def __str__(self):
        return self.descripcion


class SgaMatricula(models.Model):
    """
    Tabla intermedia: Un estudiante (Inscripcion) se matricula en un Nivel.
    Esta es la conexión clave que solicitaste.
    """
    inscripcion = models.ForeignKey(SgaInscripcion, models.DO_NOTHING, related_name='matriculas')
    nivel = models.ForeignKey(SgaNivel, models.DO_NOTHING)
    retiradomatricula = models.BooleanField(default=False)
    
    # Campos útiles para filtrar matrículas válidas
    estado_matricula = models.IntegerField(default=1) 
    
    class Meta:
        managed = False
        db_table = 'sga_matricula'
    
    def __str__(self):
        return f"Matrícula {self.id}"

class SgaMateria(models.Model):
    # Necesaria para saber el nombre de la asignatura
    nombre = models.CharField(max_length=200)
    # ... otros campos
    class Meta:
        managed = False
        db_table = 'sga_materia'

class SgaRecordAcademico(models.Model):
    """
    Tabla de Notas / Calificaciones
    """
    inscripcion = models.ForeignKey(SgaInscripcion, models.DO_NOTHING)
    materia = models.ForeignKey(SgaMateria, models.DO_NOTHING)
    nota = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    asistencia = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    aprobada = models.BooleanField(default=False)
    # Importante: Normalmente se vincula a una matrícula o periodo. 
    # Si no tiene FK directo a periodo, se llega por inscripcion->matricula->nivel->periodo
    # OJO: Asumiremos que filtramos por la inscripcion y luego por las materias de la matricula actual.
    
    class Meta:
        managed = False
        db_table = 'sga_recordacademico'

class SgaRubro(models.Model):
    """
    Tabla financiera / Deudas
    """
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING)
    nombre = models.CharField(max_length=200) # ej: "Matrícula", "Arancel"
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    saldo = models.DecimalField(max_digits=10, decimal_places=2)
    cancelado = models.BooleanField(default=False)
    fecha_vence = models.DateField(null=True)
    
    class Meta:
        managed = False
        db_table = 'sga_rubro'

class GobeSolicitud(models.Model):
    """
    Solicitudes del Balcón de Servicios (Suele ser módulo GOBE o SAGA)
    """
    persona = models.ForeignKey(SgaPersona, models.DO_NOTHING)
    descripcion = models.TextField()
    estado = models.IntegerField() # 1: Pendiente, 2: Aprobado, etc.
    fecha_creacion = models.DateTimeField()
    
    class Meta:
        managed = False
        db_table = 'gobe_solicitud'

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


class BusinessProcessType(ModeloBase):
    """
    Catálogo de tipos de procesos (ej: Informativo, Operativo, Trámite Urgente).
    Controla el comportamiento del flujo.
    """
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Tipo")    
    requiere_documentacion_por_defecto = models.BooleanField(default=False, verbose_name="¿Suele requerir docs?")
    
    class Meta:
        verbose_name = "Tipo de Proceso"
        verbose_name_plural = "Tipos de Procesos"
        db_table = 'chatbot_process_types'

    def __str__(self):
        return self.nombre



class BusinessProcess(ModeloBase):
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Proceso")
    business_context = models.TextField(default="Descripcion", verbose_name="Contexto del proceso")
    
    process_type = models.ForeignKey(
        BusinessProcessType, 
        on_delete=models.PROTECT, 
        verbose_name="Tipo de Proceso",
        related_name="procesos"
    )

    source_url = models.CharField(max_length=500, blank=True, null=True, verbose_name="Fuente")
    closed_message = models.TextField(verbose_name="Mensaje No Disponible", blank=True, null=True)

    start_date = models.DateField(verbose_name="Fecha Inicio")
    end_date = models.DateField(verbose_name="Fecha Fin")
    is_infinite = models.BooleanField(default=False, verbose_name="Es Indefinido")
    
    active_message = models.TextField(verbose_name="Mensaje Activo")
    roles_permitidos = models.ManyToManyField(ChatbotRol, blank=True, verbose_name="Roles Permitidos")
    
    need_documentation = models.BooleanField(default=False, verbose_name="Requiere Documentación")

    @property
    def active(self):
        return self.status

    class Meta:
        managed = True 
        db_table = 'chatbot_business_processes'
        verbose_name = 'Proceso de Negocio'

    def __str__(self):
        return f"{self.nombre} ({self.process_type.nombre})"