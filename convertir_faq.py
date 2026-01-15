import csv
import re
from bs4 import BeautifulSoup

# Tu HTML original (lo he puesto en una variable para facilitar el uso)
html_content = """
<div class="wpb_wrapper"><div class="gt3_spacing"><div class="gt3_spacing-height gt3_spacing-height_default" style="height:32px;"></div></div>  
<h2 style="text-align: left;font-family:Montserrat;font-weight:700;font-style:normal" class="vc_custom_heading">Información sobre Admisión y Nivelación</h2><div class="gt3_spacing"><div class="gt3_spacing-height gt3_spacing-height_default" style="height:32px;"></div></div>  
<div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Quiénes pueden aplicar al proceso de admisión a la educación superior?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Todos los bachilleres a nivel nacional y estudiantes que se encuentran en tercero de bachillerato, que deseen acceder a la educación superior pública.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>Al culminar con la inscripción en la etapa de Registro Nacional no imprimí el comprobante, ¿qué puedo hacer?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La Senescyt remite a todas las Universidades y Escuelas Politécnicas públicas con proceso de admisión propio, la información de los aspirantes que realizaron el Registro Nacional.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cuáles son los pasos para aplicar al proceso de admisión para acceder a las Universidades Públicas?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>De acuerdo al Art. 15 del Reglamento del Sistema Nacional de Nivelación y Admisión las etapas del proceso de admisión a la Educación Superior son:</p>
<ol>
<li>Registro Nacional;</li>
<li>Levantamiento de Estado Académico;</li>
<li>Determinación de la oferta de cupos;</li>
<li>Inscripción;</li>
<li>Evaluación de Capacidades y Competencias;</li>
<li>Postulación;</li>
<li>Asignación de Cupos;</li>
<li>Aceptación de Cupos; y,</li>
<li>Matriculación.</li>
</ol>
<p>Todas las etapas son de cumplimiento obligatorio, los numerales 1, 4, 5, 6, 8 y 9 forman parte de la gestión del aspirante.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿A qué plataformas debo acceder para realizar el proceso de admisión a la Educación Superior?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><ol>
<li><strong>La etapa 1 Registro Nacional </strong>la deberá realizar obligatoriamente, este es el único mecanismo que te habilita para aplicar al proceso de admisión vigente: <span><a href="https://www.registrounicoedusup.gob.ec" target="_blank" rel="noopener external noreferrer" data-wpel-link="external"><span>https://www.registrounicoedusup.gob.ec</span></a></span></li>
<li><strong>Las etapas 4, 5 y 6 las deberá cumplir de acuerdo al cronograma publicado en la web institucional de la Universidad Estatal de Milagro </strong><span><a href="https://admisiongrado.unemi.edu.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external"><span>https://admisiongrado.unemi.edu.ec/</span></a></span>, no podrá ingresar antes, ni después de las fechas establecidas dentro de cada etapa del proceso.</li>
<li><strong>La aceptación de cupos</strong> deberá ser ejecutado en la plataforma de la Senescyt, para lo cual deberá estar pendiente de las publicaciones en las páginas web de la Senescyt, UNEMI y demás fuentes oficiales de la Educación Superior.</li>
<li><strong>La matriculación</strong> en la nivelación deberá ser realizada en la plataforma que la Universidad determine para esta etapa.</li>
</ol>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué pasos debo realizar en el Registro Nacional?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Si desea participar en el proceso de admisión a la educación superior pública del Ecuador, deberás realizar obligatoriamente los siguientes pasos en la etapa de Registro Nacional:</p>
<ul>
<li>Creación de cuenta, en caso de no tener, de lo contrario debe ingresar con su contraseña anterior.</li>
<li>Registrar los datos solicitados.</li>
<li>Confirmación del registro.</li>
<li>Generación del Comprobante del Registro Nacional.</li>
</ul>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo puedo recuperar la contraseña en el proceso de acceso a la educación superior (etapa con la Senescyt)?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Acceda a la página <span><a href="https://www.registrounicoedusup.gob.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://www.registrounicoedusup.gob.ec/</a></span> en la etiqueta Registro Nacional te aparecerá la opción “¿Has olvidado tu contraseña?” mediante la que podrás recuperar tu contraseña.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo puedo actualizar el correo electrónico ingresado en la página https://www.registrounicoedusup.gob.ec/?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Acceda a la página <span><a href="https://www.registrounicoedusup.gob.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://www.registrounicoedusup.gob.ec/</a></span> en la etiqueta Registro Nacional te aparecerá la opción “¿Has olvidado tu contraseña?” visualizarás un &nbsp;link donde podrás solicitar&nbsp; la actualización del correo electrónico, y en el transcurso de las 48 horas siguientes se reflejará el cambio solicitado.</p>
<p>También tiene la opción de contactar a la Senescyt para los trámites relacionados a su plataforma.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Dónde puedo obtener el certificado de la etapa de Registro Nacional?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El certificado lo puede imprimir accediendo con su usuario y contraseña a <span><a href="https://certificados.senescyt.gob.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://certificados.senescyt.gob.ec/</a></span><span>.</span></p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué es la Encuesta del Registro Social?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Es un catastro que consta de información social, económica y demográfica individualizada y a nivel de familias, que permite a las instituciones identificar a sus poblaciones objetivo para enfocar mejor los esfuerzos hacia los grupos en condiciones de pobreza.</p>
<p>Quienes no tengan información en el Registro Social serán informados, mediante un correo electrónico por la Senescyt para llenar el formulario. Esta información no es obligatoria.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>No me ha llegado el correo para llenar la Encuesta de Registro Social, ¿qué puedo hacer?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El correo con la información para llenar la Encuesta de Registro Social les llegará únicamente a las personas que, en la confirmación de Registro Nacional, se les informó que no cuentan con los datos registrados en la Unidad de Registro Social.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo puedo actualizar la información que está en el Registro Social?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Si ya cuenta con datos en el Registro Social, podrá actualizar la información posteriormente. Las fechas para realizar este proceso serán publicadas en los canales oficiales de la Senescyt: <a href="https://siau.senescyt.gob.ec/canales-de-informacion/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://siau.senescyt.gob.ec/canales-de-informacion/</a></p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Dónde puedo obtener información sobre los pasos posteriores al Registro Nacional?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La información y cronograma de las etapas de inscripción, evaluación, postulación y aceptación de cupos las podrá observar en la página oficial de la UNEMI <span><a href="https://www.unemi.edu.ec/" data-wpel-link="internal">https://www.unemi.edu.ec/</a></span>, ingresando al apartado de Admisión <span><a href="https://www.unemi.edu.ec/index.php/admision/" data-wpel-link="internal">https://www.unemi.edu.ec/admision/</a></span> donde encontrará la etiqueta del período del proceso de Admisión de la Universidad Estatal de Milagro en vigencia.</p>
<p>Cabe indicar que las indicaciones de cada etapa de la admisión a la educación superior, se publica en los canales oficiales institucionales mediante claquetas informativas: Facebook, Instagram, X, Youtube y LinkedIn donde nos encontrará como /UNEMIEcuador.</p>
<p>En el actual período los aspirantes llevan a cabo el proceso de admisión a la institución en la plataforma <span><a href="https://admisiongrado.unemi.edu.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://admisiongrado.unemi.edu.ec/</a></span></p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo me registro en la etapa de Inscripción para el proceso de admisión en la UNEMI?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El Art. 18 del Reglamento de Admisión y Nivelación de la Universidad Estatal de Milagro, establece: <em>“Los aspirantes interesados en estudiar en la Universidad Estatal de Milagro, deberán realizar el proceso de inscripción en la plataforma informática institucional, de acuerdo con los mecanismos, lineamientos y cronogramas establecidos para el efecto. En esta etapa solo podrán participar los aspirantes que hayan realizado el registro nacional, en la plataforma informática del Sistema Nacional de Nivelación y Admisión.</em> <em>Una vez finalizada el registro en la plataforma informática de la universidad, los estudiantes podrán descargar así mismo su respectivo certificado de inscripción”</em></p>
<p>Como lo establece la norma citada, para acceder a la etapa de inscripción previamente debió realizar el Registro Nacional del mismo período, y para conocer las fechas en que debe realizar el proceso de inscripción deberá estar pendiente de la página de la UNEMI <span><a href="https://admisiongrado.unemi.edu.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://admisiongrado.unemi.edu.ec/</a></span> y publicaciones de los canales oficiales de la institución.</p>
<p>En esta etapa el aspirante deberá ingresar al link de Inscripción habilitada, donde se le solicitará información como número de cédula, nombres y apellidos completos, correo electrónico vigente y contacto telefónico, luego deberá seleccionar hasta tres (3) opciones de carrera, leer y aceptar los términos y condiciones, posterior ingresar con su usuario (cédula) y clave que se le proporciona e ingresar al sitio: &nbsp;<span><a href="https://admisiongrado.unemi.edu.ec/app/autenticacion/login" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://admisiongrado.unemi.edu.ec/app/autenticacion/login</a></span> para proceder a generar el comprobante de inscripción.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿En la UNEMI, en qué momento efectúo el paso de postulación a una carrera?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>En la etapa de inscripción los aspirantes podrán escoger las opciones de carrera de acuerdo con los cupos disponibles en la oferta académica de la UNEMI.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Existe una sanción si me inscribí en el proceso de Admisión a la Educación Superior pero no me presenté a rendir la evaluación de capacidades y competencias de la Universidad Estatal de Milagro?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>No existe ninguna sanción por no presentarse a rendir la evaluación de capacidades y competencias; sin embargo, el sistema le notificará la nota de cero (0) en la plataforma, y le realizará el cálculo de su puntaje final de postulación sólo con su puntaje de antecedentes académicos y el puntaje adicional (si ese fuere su caso) basado en el marco de las políticas de acción afirmativa.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo realizo el cálculo del puntaje de postulación?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>De conformidad con el artículo 24 del Reglamento de Admisión y Nivelación de la UNEMI, el puntaje de postulación tiene los siguientes componentes:</p>
<ol>
<li><em>a) Puntaje de evaluación de capacidades y competencias (entre 50% y el 75%);</em></li>
<li><em>b) Puntaje de antecedentes académicos, corresponde a la nota de grado más alta del bachillerato (entre el 25% y el 50%); y,</em></li>
<li><em>c) Puntaje adicional por acciones afirmativas en caso de que corresponda.</em></li>
</ol>
<p><em>Los aspirantes que no cuenten con la información referente a sus antecedentes académicos y que realizaron los procesos de homologación del título de bachiller con el Ministerio de Educación, el puntaje de postulación estará determinado por la totalidad del puntaje de evaluación más el puntaje adicional por 7políticas de acción afirmativa, en los casos que corresponda.”</em></p>
<p>En el período actual para ingresar a la institución la nota de la Evaluación de Capacidades y Competencias equivale al 50%; y los antecedentes académicos, es decir la nota de grado equivale al 50% del puntaje final de postulación. Cabe indicar que, esta ponderación podrá variar de un período a otro.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿En qué consiste el puntaje adicional por acciones afirmativas?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Las políticas de acción afirmativa al que se hace referencia en la pregunta que antecede, obedece a un sistema de educación superior inclusivo, donde toda la ciudadanía tiene la oportunidad de ingresar a un tercer nivel de estudios, independientemente de su origen o condición.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cuáles son los segmentos poblacionales que se benefician con el puntaje adicional mediante políticas de acción afirmativa en el acceso a la educación superior en Ecuador?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El artículo <strong>49 del Reglamento del SNNA</strong>, establece los criterios que las IES públicas deben aplicar para conceder el puntaje adicional por políticas de acción afirmativa:</p>
<p>“<em>En aplicación de las políticas de acción afirmativa, se otorgarán puntos adicionales a los postulantes, de conformidad a los siguientes criterios:</em></p>
<ol>
<li><strong><em>Condición socioeconómica: </em></strong><em>Quince (15) puntos adicionales a los aspirantes identificados en condición de pobreza, de conformidad con la información entregada por la Unidad de Registro Social.</em></li>
<li><strong><em>Ruralidad: </em></strong><em>Cinco (5) puntos adicionales, a las y los aspirantes que estudien o hayan estudiado en instituciones educativas públicas (fiscales, fiscomisionales y municipales) pertenecientes a las zonas rurales, de conformidad con la información reportada por el ente rector del sistema nacional de educación.</em></li>
<li><strong><em>Territorialidad: </em></strong><em>Diez (10) puntos adicionales, a las y los aspirantes que residan en una de las parroquias con mayor índice de pobreza, de conformidad con lo determinado por la Unidad de Registro Social.</em></li>
<li><strong><em>Condiciones de vulnerabilidad: </em></strong><em>Cinco (5) puntos adicionales, hasta un máximo de treinta y cinco (35) puntos, de conformidad a las siguientes condiciones:</em></li>
</ol>
<ul>
<li><em>Personas con discapacidad con un porcentaje mínimo del 30% debidamente registradas por la Autoridad Sanitaria Nacional – cinco (5 puntos).</em></li>
<li><em>Personas calificadas como sustitutos de personas con discapacidad y las beneficiarias del Bono Joaquín Gallegos Lara que consten en los registros administrativos del Ministerio de Inclusión Económica y Social – cinco (5 puntos).</em></li>
<li><em>Víctimas de violencia sexual o de género siempre que se haya realizado la denuncia ante la Fiscalía General del Estado – cinco (5 puntos).</em></li>
<li><em>Personas ecuatorianas residentes en el exterior o migrantes retornados con la certificación del ente rector en movilidad humana – cinco (5 puntos).</em></li>
<li><em>Hijas e hijos de las víctimas de femicidio o muerte violenta, esta información será verificada a partir de los datos proporcionados por la autoridad competente – cinco (5 puntos).</em></li>
<li><em>Personas que adolezcan de enfermedades catastróficas o de alta complejidad, que consten en los registros de la Autoridad Sanitaria Nacional – cinco (5 puntos).</em></li>
<li><em>Personas que en alguna etapa de su niñez o adolescencia fueron ingresadas en una unidad de atención de acogimiento institucional como medida de protección, emitida por la autoridad competente – cinco (5 puntos).</em></li>
</ul>
<ol start="5">
<li><strong><em>Pueblos y nacionalidades: </em></strong><em>Diez (10) puntos adicionales a las personas pertenecientes a las comunidades, pueblos y nacionalidades indígenas, afroecuatorianos, montubios, entre otras.</em></li>
</ol>
<p><em>La SENESCYT, suscribirá con otras entidades del Estado convenios y acuerdos que permitan el intercambio y la interoperabilidad de la información necesaria para la aplicación de este Reglamento.”</em></p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Existen puntajes mínimos de postulación?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>No existen puntajes mínimos de postulación para que le sea asignada una carrera en la educación superior. Este proceso será ejecutado conforme al principio de meritocracia, es decir, que a los mejores puntuados se les asignará la carrera de&nbsp;acuerdo con la disponibilidad de cupos ofertados por la institución, y a la selección de la carrera por el postulante en la etapa de inscripción.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿En función de qué criterios la UNEMI efectúa la asignación de cupos?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La UNEMI como institución de Educación Superior Pública basa sus criterios de asignación en cumplimiento a lo establecido en el Artículo 51 del Reglamento del Sistema Nacional de Nivelación y Admisión:</p>
<p><em>“Artículo 51. Asignación de cupos. – La asignación de cupos será un proceso automatizado determinado por las IES públicas, que será realizado en función de los siguientes parámetros y en atención a los principios de mérito e igualdad de oportunidades:</em></p>
<ol>
<li><em> Oferta de cupos disponible</em></li>
<li><em> Puntaje de postulación, desde el puntaje de postulación más alto, al más bajo</em></li>
<li><em> Elección de carrera.</em></li>
<li><em> Orden de asignación.</em></li>
</ol>
<p><em>El resultado de la asignación de cupos se cargará en la plataforma que la SENESCYT determine para el efecto, a fin de ejecutar la siguiente etapa.”</em></p>
<p>La asignación de cupos en las universidades públicas de Ecuador es un proceso automatizado que prioriza el principio de meritocracia (mejores puntuados), a quienes se les asignará la carrera de acuerdo a la disponibilidad de cupos ofertados por la institución, a la selección de la carrera por el postulante y al orden de asignación, este último criterio se explicará en la siguiente interrogante.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cuál es el orden en el que la UNEMI asigna los cupos para la admisión a la Educación Superior?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La UNEMI como institución de Educación Superior Pública obedece a un orden de asignación de cupos acorde a lo establecido en el Artículo 52 del Reglamento del Sistema Nacional de Nivelación y Admisión:</p>
<p><em>“Artículo 52. Orden de asignación. – La asignación de cupos considerará el siguiente orden de segmentos:</em></p>
<p><strong><em>1) Grupo de política de cuotas:</em></strong><em> lo conforman los grupos históricamente excluidos o discriminados determinados por las IES públicas y por la SENESCYT para los institutos superiores técnicos, tecnológicos, pedagógicos de artes y conservatorios superiores públicos.</em></p>
<p><em>Para este grupo se segmentará entre el 5% y 10% de la oferta por carrera, de conformidad a lo determinado en el artículo 31 de este cuerpo normativo.</em></p>
<p><strong><em>2) Grupo de mayor vulnerabilidad socioeconómica:</em></strong><em> Lo conforman los aspirantes en condición de pobreza, de conformidad a la información entregada por la Unidad del Registro Social.</em></p>
<p><em>Para este grupo se segmentará al menos el 10% de la oferta por carrera.</em></p>
<p><strong><em>3) Grupo de Mérito Académico:</em></strong><em> el mismo estará conformado por el cuadro de honor de las instituciones educativas del último régimen escolar en curso.</em></p>
<p><em>Para este grupo se segmentará al menos el 20% de la oferta por carrera.</em></p>
<p><strong><em>4) Grupo de Otros Reconocimientos al Mérito:</em></strong><em> en el marco de la autonomía responsable, las IES públicas podrán determinar otros grupos de reconocimiento al mérito de tipo: académico, cultural, deportivo, entre otros, los cuales deberán estar regulados en su normativa interna.</em></p>
<p><em>De igual manera, deberán justificar el tipo de reconocimiento adicional, a través de un informe técnico que se remitirá a la SENESCYT previo al inicio de la etapa de inscripción de la convocatoria en curso, en el que conste los mecanismos de verificación para la fase de monitoreo.</em></p>
<p><em>Para este grupo se segmentará un máximo del 2% de la oferta por carrera:</em></p>
<p><strong><em>5) Bachilleres del último régimen escolar en curso:</em></strong><em> los conforman los bachilleres del último régimen escolar de conformidad con la información provista por el MINEDUC:</em></p>
<p><em>La asignación inicia por aquellos pertenecientes a pueblos y nacionalidades. Para este grupo se segmentará un máximo del 10% de la oferta por carrera.</em></p>
<p><em>Continuará con los demás bachilleres de la convocatoria en curso. Para este grupo se segmentará al menos el 20% de la oferta por carrera. Los bachilleres participaran en la asignación de este grupo por una sola ocasión.</em></p>
<p><strong><em>6) Población general:</em></strong><em> se encuentra conformado por bachilleres de años anteriores que no pertenecen a los grupos antes descritos, más la población que no se asigne un cupo en su segmento.</em></p>
<p><em>Para este grupo se segmentará al menos el 20% de la oferta por carrera.</em></p>
<p><em>La asignación se realizará en instancias, por cada segmento, y en cada grupo siempre se deberá contemplar el principio de meritocracia.</em></p>
<p><em>Si un postulante cumple con más de un (1) criterio participará inicialmente en el grupo que más le favorezca y de no obtener un cupo asignado en dicho grupo será reasignado para continuar participando en el o los siguientes grupos a los que pertenezca, hasta llegar a población general de ser el caso.</em></p>
<p><em>Si un postulante registra título de tercer nivel o superior, participará únicamente en el grupo de población general.</em></p>
<p><em>En caso de que dentro de cada grupo no se cumpla el porcentaje establecido por no tener postulantes que demanden la carrera, los cupos serán liberados y serán incrementados al grupo correspondiente a población general.</em></p>
<p><em>El orden de asignación detallado será de carácter obligatorio.</em></p>
<p><em>Los porcentajes establecidos en los segmentos para el orden de asignación serán determinados por las IES públicas, en el marco de su autonomía responsable.”</em></p>
<p>Con base a la normativa expuesta la institución dentro del sistema de asignación de cupos busca equilibrar el mérito académico con la igualdad de oportunidades, considerando acciones afirmativas para grupos específicos y garantizando la transparencia del proceso a través de la automatización de la plataforma monitoreada por la SENESCYT.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué puedo hacer si realicé la etapa de Registro Nacional, pero no efectué las siguientes etapas establecidas en el cronograma del proceso de Admisión de la UNEMI?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Si realizó la etapa del Registro Nacional, pero no la etapa de Inscripción espere para aplicar al proceso de Admisión a la Educación Superior del siguiente período, por cuanto, la etapa de Registro Nacional es obligatoria, por ello, deberá consultar la fecha de inicio del nuevo proceso en https://www.registrounicoedusup.gob.ec/</p>
<p>Tenga en cuenta que de acuerdo a la normativa vigente todo proceso de acceso a la Educación Superior Pública da inicio en la plataforma que la Senescyt determina, actualmente el Registro Nacional lo llevan a cabo en el sitio web <a href="https://www.registrounicoedusup.gob.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://www.registrounicoedusup.gob.ec/</a>, por consiguiente, la información de las nuevas fechas del proceso de admisión a la Educación Superior pública, se darán a conocer mediante los canales oficiales de la Senescyt.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿El examen de Competencias y Capacidades tiene algún costo?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La evaluación de capacidades y competencias no tiene ningún costo. Si realizó las etapas de Registro Nacional (Senescyt) y la de inscripción (UNEMI), sólo se requiere estar atento a la plataforma <a href="https://admisiongrado.unemi.edu.ec/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://admisiongrado.unemi.edu.ec/</a>, y rendir la evaluación de acuerdo a las fechas y modalidad publicadas.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué debo hacer si he aceptado un cupo para el Curso de Nivelación de Carreras en la UNEMI?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Si usted aceptó un cupo para alguna de las carreras ofertadas por la UNEMI, deberá matricularse en el Curso de Nivelación del mismo período académico de su aceptación, es decir, para el período académico para el cual fue asignado.</p>
<p>Sobre fechas de matrícula e inicio de clases deberá estar pendiente de los comunicados oficiales emitidos por la UNEMI en la página web https://www.unemi.edu.ec/ y en sus canales oficiales institucionales mediante claquetas informativas: Facebook, Instagram, X, Youtube y LinkedIn donde nos encontrará como /UNEMIEcuador.</p>
<p>En el caso de que la o el postulante acepte un cupo en el periodo académico en curso, no podrá participar en el siguiente proceso de acceso, acorde a lo establecido en el artículo 56 del Reglamento del Sistema Nacional de Nivelación y Admisión vigente.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Si acepté un cupo en la UNEMI puedo solicitar que lo anulen?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El Reglamento del Sistema Nacional de Nivelación y Admisión, establece: <em>“El cupo aceptado en una determinada carrera no podrá ser modificado, ni anulado y tampoco se podrá renunciar al mismo…”.</em></p>
<p>Debido a que la acción de aceptar un cupo es un acto libre y voluntario, el cupo no puede ser anulado, tampoco es factible que la carrera o modalidad que conste en ese cupo sea cambiado por ningún concepto, ni renunciar al cupo.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Si rechazo el cupo puedo acudir a la institución para que me reintegren el cupo?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La respuesta es no, con base en lo establecido en el Reglamento del Sistema Nacional de Nivelación y Admisión, la institución aplica estrategias para lograr una asignación de cupos eficiente, de manera que, si el aspirante Rechaza o no se pronuncia sobre la asignación del cupo otorgado, el sistema implementado automáticamente realizará la asignación de ese cupo a otro aspirante aplicando los principios de mérito e igualdad de oportunidades.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo puedo conocer las fechas de matriculación a Nivelación y qué debo hacer para constar como matriculado/a?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Debe revisar con frecuencia las publicaciones en la página oficial de la UNEMI: https://www.unemi.edu.ec/, y en los canales oficiales de Facebook, Instagram y X : @UNEMIEcuador, con la finalidad de conocer las fechas y requisitos de la matriculación.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Quiénes poseen gratuidad en el Curso de Nivelación?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>De acuerdo con lo que contempla el Artículo 54 del Reglamento del Sistema Nacional de Nivelación y Admisión: La gratuidad cubrirá únicamente la primera matrícula del programa de Nivelación de Carreras, no cubre la segunda matrícula. La pérdida del beneficio de gratuidad en nivelación de carrera no afectará la gratuidad del aspirante durante el programa de formación.</p>
<p>En los casos de aspirantes a segunda carrera (estudiante o graduado), no contará con el beneficio de gratuidad desde el inicio de la nivelación.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo puedo conocer las fechas de matriculación a Nivelación y qué debo hacer para constar como matriculado/a?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Debe revisar con frecuencia las publicaciones en la página oficial de la UNEMI, y en los canales oficiales de Facebook, Instagram y X (Twitter): @UNEMIEcuador, con la finalidad de conocer las fechas y requisitos de la matriculación.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>Si tengo que cancelar valor de matriculación por segunda carrera o segunda matrícula, ¿Hasta cuándo puedo pagar los valores que adeudo?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>De conformidad con lo establecido en el Art. 41 del Reglamento de Admisión y Nivelación de la Universidad Estatal de Milagro: “Los aspirantes que sean de segunda carrera o de segunda matrícula, para ser considerados legalmente matriculados, deberán tener cancelado obligatoriamente el valor de la matrícula hasta una semana antes del inicio del curso o su equivalente, de lo contrario serán eliminados del Sistema de Gestión Académica SGA.”</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Si tengo que cancelar valor de matriculación por Segunda Carrera o Segunda Matrícula, hasta cuándo puedo pagar los valores que adeudo?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>De conformidad con lo establecido en el Art. 40 del Reglamento de Admisión y Nivelación de la Universidad Estatal de Milagro: <em>“Los aspirantes que sean de segunda carrera o de segunda matrícula para ser considerados legalmente matriculados, deberán tener cancelado obligatoriamente el valor de la matrícula hasta una semana antes del inicio del curso o su equivalente, de lo contrario serán eliminados del Sistema de Gestión Académica SGA.”</em></p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Con qué puntajes apruebo el Curso de Nivelación por Carreras?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p style="text-align: left;">El Reglamento de Admisión y Nivelación de la Universidad Estatal de Milagro, en el Art. 53 establece las escalas de calificaciones, como se muestra a continuación:</p>
<table id="table" class=" aligncenter">
<tbody>
<tr style="height: 24px;">
<th style="height: 25px; width: 35.0199%; text-align: center;">ESCALA CUANTITATIVA</th>
<th style="text-align: center; height: 25px; width: 33.493%;">EQUIVALENCIA</th>
</tr>
<tr style="height: 24px;">
<td style="height: 24px; width: 35.0199%; text-align: center;">96 – 100</td>
<td style="text-align: center; height: 24px; width: 33.493%;">Excelente</td>
</tr>
<tr style="height: 24px;">
<td style="height: 24px; width: 35.0199%; text-align: center;">85 – 95</td>
<td style="text-align: center; height: 24px; width: 33.493%;">Muy Bueno</td>
</tr>
<tr style="height: 24px;">
<td style="height: 24px; width: 35.0199%; text-align: center;">71 – 84</td>
<td style="text-align: center; height: 24px; width: 33.493%;">Bueno</td>
</tr>
<tr style="height: 24px;">
<td style="height: 24px; width: 35.0199%; text-align: center;">70</td>
<td style="text-align: center; height: 24px; width: 33.493%;">Aprobado</td>
</tr>
<tr style="height: 24px;">
<td style="height: 24px; width: 35.0199%; text-align: center;">1 – 69</td>
<td style="text-align: center; height: 24px; width: 33.493%;">Reprobado</td>
</tr>
</tbody>
</table>
<p>Es decir, que para aprobar el Curso de Nivelación de Carreras deberá obtener un puntaje mínimo de 70 puntos en cada asignatura.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Si apruebo el curso de nivelación, en qué modalidad se desarrollarán las clases a partir del primer semestre o nivel?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La modalidad de la carrera que va a cursar desde el primer hasta el último semestre será la misma en la que obtuvo el cupo en el proceso de admisión a la educación superior pública.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué es el SGA y cómo ingreso?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El Sistema de Gestión Académica (<strong>SGA+</strong>) está disponible para los estudiantes de Nivelación y pregrado de la Universidad Estatal de Milagro de las diferentes modalidades (presencial, semipresencial y en línea) permite revisar información sobre notas, récord académico, horarios, asignaturas, porcentaje de asistencia, finanzas, entre otros datos de su vida estudiantil. Puede acceder al Sistema a través de computadoras o equipos móviles con navegadores web.</p>
<p>Para ingresar al SGA se lo realiza a través del siguiente link: <a href="https://sgaestudiante.unemi.edu.ec/login" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://sgaestudiante.unemi.edu.ec/login</a>, debe estar registrado como estudiante de nivelación y contar con su usuario y contraseña.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cuál es mi usuario y contraseña del SGA para ingresar por primera vez?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Los usuarios del SGA están compuestos por la primera letra de tu nombre, seguido de tu primer apellido y también la primera letra de tu segundo apellido, por ejemplo:</p>
<p style="padding-left: 40px;">Nombre del estudiante: <strong>P</strong>AÚL ERNESTO <strong>PÉREZ</strong> <strong>U</strong>LLOA<br>
El usuario es: <strong>pperezu</strong></p>
<p>La contraseña estará compuesta por los dígitos de la cédula del usuario, por ejemplo: 1805457659</p>
<p>Importante saber que:</p>
<ul>
<li>Las tildes no están consideradas en ningún nombre de usuario.</li>
<li>La letra eñe (ñ) se convierte automáticamente en n.</li>
</ul>
<p>En el caso de existir dos usuarios que coincidan, se diferenciarán en números incrementales adicionados al nombre de usuario, ejemplo: pperez1, pperezu2, y así sucesivamente.</p>
<p>En el primer ingreso, el Sistema solicitará el cambio de contraseña por una que solo tu conozcas. Esta nueva clave debe cumplir con una serie de condiciones que se irán coloreando a verde a medida que se vayan cumpliendo.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>Olvidé mi usuario y clave del SGA ¿Qué debo hacer?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>En caso de no conocer o haber olvidado sus credenciales de acceso al SGA, debe realizar los siguientes pasos:</p>
<ul>
<li>Ingrese al enlace: https://sga.unemi.edu.ec/loginsga?ret=/.</li>
<li>Haga clic en ¿Olvidaste tu contraseña?</li>
<li>Ingrese los dígitos de la cédula y presione “buscar”
<ol>
<li>En caso de encontrarse registrado, mostrará un mensaje de confirmación.
<ul>
<li>Presione el botón “Restablecer contraseña”, se enviará un enlace a su correo electrónico registrado.</li>
<li>Ingresar a su correo INSTITUCIONAL o PERSONAL registrado en el SGA; allí encontrará un enlace para reestablecer la contraseña.</li>
<li>Presione el enlace e ingrese la nueva clave.</li>
</ul>
</li>
</ol>
</li>
</ul>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo cambio mi clave del SGA?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><ul>
<li>Ingrese al SGA con su usuario y clave.</li>
<li>En el menú del PERFIL que se encuentra en el lado derecho superior; haga clic en Cambiar contraseña.</li>
<li>Ingrese la contraseña anterior.</li>
<li>Ingrese la nueva contraseña.</li>
<li>Confirme la nueva contraseña.</li>
<li>Para almacenar los cambios presione el botón “Guardar”.</li>
</ul>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué debo hacer para obtener un certificado de matrícula o de calificaciones en el SGA?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p><span>Deberá solicitarlo mediante el módulo del SGA: Servicios de Secretaría, obligatoriamente deberá utilizar este medio el que está dividido en tres (3) secciones: </span></p>
<ol>
<li><span> </span><span><strong>Solicitudes de Certificaciones de Nivelación Externas:</strong> Certificado de no estar matriculado en el Curso de Nivelación.</span></li>
<li><span> </span><span><strong>Solicitudes de Certificaciones de Nivelación Internas:</strong> Certificado de matrícula, Certificado de no adeudar (valores), Certificado de asistencia, certificado de carreras estudiadas en la nivelación, certificado de número de matrículas por carrera, certificados de segundas matrículas por carreras, certificados de horarios de clases por materias.</span></li>
<li><span> </span><span><strong>Solicitudes de Certificaciones de Nivelación Personalizadas:</strong> Certificado de notas de la Nivelación con el estado académico en cada una de las asignaturas cursadas.</span></li>
</ol>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué es el aula virtual y cómo ingreso?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El Aula de Nivelación de la Universidad Estatal de Milagro (UNEMI) es un espacio virtual diseñado para brindar a los estudiantes los recursos y herramientas necesarias para fortalecer sus conocimientos. Para acceder al aula virtual, el estudiante deberá ingresar con las mismas credenciales del Sistema de Gestión Académica (SGA).</p>
<p>El usuario registrado tiene acceso al aula virtual y podrá acceder al contenido y material didáctico de sus asignaturas del presente período académico, tales como videos, lecturas, diapositivas, enlaces, etc. Para ingresar al aula virtual, debe hacerlo a través del enlace web:&nbsp;<a href="https://aulanivelacion.unemi.edu.ec/login/index.php" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://aulanivelacion.unemi.edu.ec/</a></p>
</div></div><div class="gt3_spacing"><div class="gt3_spacing-height gt3_spacing-height_default" style="height:60px;"></div></div>  
<div class="vc_row wpb_row vc_inner vc_row-fluid"><div class="wpb_column vc_column_container vc_col-sm-12"><div class="vc_column-inner"><div class="wpb_wrapper"><div class="gt3_spacing"><div class="gt3_spacing-height gt3_spacing-height_default" style="height:32px;"></div></div>  
<h2 style="text-align: left;font-family:Montserrat;font-weight:700;font-style:normal" class="vc_custom_heading">Información sobre canales de atención, carreras, cambio de IES y homologaciones</h2><div class="gt3_spacing"><div class="gt3_spacing-height gt3_spacing-height_default" style="height:32px;"></div></div>  
<div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿A qué medios puedo contactar para consultas académicas relacionadas con los procesos de Admisión y Nivelación?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>En caso de requerir atención personalizada, actualmente la UNEMI mantiene habilitada las siguientes líneas de atención al usuario:</p>
<ol>
<li><strong>Balcón de Servicios</strong>
<ul>
<li>Para estudiantes de UNEMI el acceso para atención al usuario es mediante el Sistema de Gestión Académica SGA – Balcón de Servicios.</li>
<li>Para ciudadanos externos y que no tienen credenciales del SGA deben acceder al Balcón de servicio utilizando el siguiente enlace <a href="https://sga.unemi.edu.ec/alu_solicitudbalconexterno" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://sga.unemi.edu.ec/alu_solicitudbalconexterno</a>, en el cual deberá<br>
llenar un registro.</li>
</ul>
</li>
<li><strong>Presencial</strong>
<ul>
<li>Edificio CRAI, planta baja, en horario de 08h00 a 17h00</li>
</ul>
</li>
</ol>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Dónde puedo consultar información académica sobre las carreras que oferta la UNEMI, en la modalidad presencial, semipresencial y en línea?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>La información referente a las carreras que oferta la UNEMI la encontrará en la página web oficial de la UNEMI <a href="https://www.unemi.edu.ec/" data-wpel-link="internal">https://www.unemi.edu.ec/</a>, o ingresando a los siguientes links:</p>
<ul>
<li><strong>Modalidad presencial:</strong> https://www.unemi.edu.ec/index.php/carreras-presencial/</li>
<li><strong>Modalidad semipresencial:</strong> https://www.unemi.edu.ec/index.php/carreras-semipresencial/</li>
<li><strong>Modalidad en línea: </strong>https://www.unemi.edu.ec/index.php/carreras-en-linea/</li>
</ul>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué proceso debo realizar si pertenezco a otra universidad y deseo estudiar en la UNEMI?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Los ciudadanos que son de otras universidades públicas o privadas, deberán contactarse con el Departamento de Gestión y Servicios Académicos, mediante el balcón de servicios externo: <a href="https://sga.unemi.edu.ec/alu_solicitudbalconexterno" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://sga.unemi.edu.ec/alu_solicitudbalconexterno</a>, y exponer detalladamente su requerimiento y situación académica</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Qué normativa debo cumplir para acceder a un cambio de Carrera o de IES en la UNEMI?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El Reglamento de Régimen Académico vigente emitido por el CES, establece <em>“<strong>Artículo 79</strong>.- <strong>Cambio de carrera y cambio de institución de educación superior</strong>.- Los cambios de carrera están sujetos a los procesos de admisión establecidos por cada institución de educación superior, observando la normativa vigente del Sistema de Educación Superior. </em></p>
<p><em>El cambio de carrera podrá realizarse en la misma o diferente institución de educación superior, según las siguientes reglas: </em></p>
<ol>
<li><em>Cambio de carrera dentro de una misma IES pública: procede cuando se ha cursado al menos un periodo académico, de acuerdo a los mecanismos establecidos por la IES. Para efectos de gratuidad se podrá realizar el cambio por una sola vez. </em></li>
</ol>
<p><em>Si el estudiante se retira antes de aprobar el primer periodo académico establecido en la carrera, deberá iniciar el proceso de admisión establecido en el sistema de educación superior. Esta regla no aplica para el caso de reingresos. </em></p>
<p><em>En todos estos casos, la IES deberá observar que el aspirante cumpla con el puntaje mínimo de admisión de cohorte de la carrera receptora en el periodo académico correspondiente en el cual solicita su movilidad. </em></p>
<ol>
<li><em>Cambio de IES pública: Un estudiante podrá cambiarse entre IES públicas, sea a la misma carrera o a una distinta, una vez que haya cursado al menos dos (2) períodos académicos, según los mecanismos establecidos por la IES. Para efectos de gratuidad se podrá realizar el cambio por una sola vez. </em></li>
</ol>
<p><em>En todos estos casos, la IES deberá observar que el aspirante cumpla con el puntaje mínimo de admisión de cohorte de la carrera receptora en el periodo académico correspondiente en el cual solicita su movilidad. </em></p>
<ol>
<li><em>Cambio de IES particular a IES pública: Un estudiante podrá cambiarse de una IES particular a una IES pública, siempre que el estudiante haya cursado al menos dos (2) períodos académicos; sea sometido al proceso de asignación de cupos; y, obtenga el puntaje de cohorte de la carrera receptora en el periodo académico correspondiente en el cual solicita su movilidad. </em></li>
</ol>
<p><em>En todos estos casos la institución de educación superior deberá observar que el aspirante cumpla con el puntaje mínimo de admisión de cohorte de la carrera receptora en el periodo académico correspondiente en el cual solicita su movilidad. </em></p>
<ol>
<li><em>Cambio de IES particulares: Cuando un estudiante se cambia de cualquier IES a una IES particular, deberá someterse a los procesos de admisión establecidos por la IES receptora. Las IES definirán los mecanismos para los cambios de carrera. Para el caso de los programas, las IES definirán las condiciones en las que se aplican la movilidad.”</em></li>
</ol>
<p>En casos de requerimientos de cambios de modalidad, también podrá aplicar al proceso de cambio de carrera, por cuanto, algunas mallas de las carreras de modalidad presencial son distintas a las de modalidad en línea.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo puedo obtener los requisitos para realizar el proceso de Cambio de Carrera y/o Universidad?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Los requisitos se encuentran publicados en la web oficial institucional <a href="https://www.unemi.edu.ec/index.php/admision/requisitos-para-cambio-de-carrera-o-ies/" data-wpel-link="internal">https://www.unemi.edu.ec/index.php/admision/requisitos-para-cambio-de-carrera-o-ies/</a>.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cuáles son los requisitos para aplicar al proceso de Homologación de asignaturas?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Para conocer los requisitos deberá ingresar a: <a href="https://www.unemi.edu.ec/index.php/admision/requisitos-para-el-proceso-de-reingreso-reconocimiento-u-homologacion-de-estudios-de-tercer-nivel/" data-wpel-link="internal">https://www.unemi.edu.ec/index.php/admision/requisitos-para-el-proceso-de-reingreso-reconocimiento-u-homologacion-de-estudios-de-tercer-nivel/</a></p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo realizo el proceso de cambio de homologación de estudios de tercer nivel?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>El proceso de homologación se puede realizar siempre y cuando sea estudiante de UNEMI en grado o cuando realice un proceso de cambio de carrera/IES, para ello deberá subir la documentación en el módulo de homologación de SGA. <span><a href="https://sga.unemi.edu.ec/loginsga?ret=/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://sga.unemi.edu.ec/</a></span> o escoger “si” al momento de estar ejecutando un cambio de carrera.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Dónde se puede revisar el cronograma para aplicar a los procesos de cambio de carrera/ IES y el de homologación de asignaturas?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Deberá estar atento a las publicaciones en los canales&nbsp;oficiales de la Institución donde se indicarán las fechas de recepción de requisitos para aplicar a los procesos de cambio de carrera/IES, y el de Homologación de asignaturas:</p>
<p>Página Institucional de la UNEMI:&nbsp;<span><a href="https://www.unemi.edu.ec/index.php/admision/" data-wpel-link="internal">https://www.unemi.edu.ec/index.php/admision/</a></span></p>
<p>Canales oficiales: Facebook, Instagram, X, Youtube y LinkedIn donde nos encontrará como /UNEMIEcuador.</p>
</div></div><div class="vc_toggle vc_toggle_accordion_alternative vc_toggle_color_triangle vc_toggle_size_right vc_toggle_active"><div class="vc_toggle_title"><h4>¿Cómo realizo el proceso de cambio de carrera o IES?</h4><i class="vc_toggle_icon"></i></div><div class="vc_toggle_content" style="display: block;"><p>Los estudiantes de UNEMI (debe tener aprobado un semestre todas las materias y haber ingresado a la carrera por medio del proceso de admisión la Senescyt, tener comprobante de cupo obtenido), para este caso debe primero haber aprobado la nivelación de carreras e ingresar y aprobar el primer semestre de carrera, no solo nivelación.</p>
<p>Para subir los requisitos, los estudiantes de la UNEMI deberán ingresar al Sistema de Gestión Académica (SGA) <a href="https://sga.unemi.edu.ec/loginsga?ret=/" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://sga.unemi.edu.ec/</a>, módulo: Cambios de Carrera estudiantes.</p>
<p>Ciudadanos externos o de otras IES (debe tener aprobado dos semestres de carrera todas las materias y haber ingresado a la carrera por medio del proceso de admisión de la Senescyt)</p>
<p>Deberán acceder al link <a href="https://sga.unemi.edu.ec/alu_solicitudcambioies" target="_blank" rel="noopener external noreferrer" data-wpel-link="external">https://sga.unemi.edu.ec/alu_solicitudcambioies</a>, luego ingresa a “Solicitar cambio IES” y completa la información solicitada, previa carga de documentos requeridos.</p>
</div></div><div class="gt3_spacing"><div class="gt3_spacing-height gt3_spacing-height_default" style="height:60px;"></div></div>  
</div></div></div></div>
"""

soup = BeautifulSoup(html_content, 'html.parser')
faqs = []

# Selectores CSS basados en tu estructura HTML
# Título: .vc_toggle_title > h4
# Contenido: .vc_toggle_content

toggles = soup.find_all("div", class_="vc_toggle")

for toggle in toggles:
    # --- 1. Extraer Pregunta ---
    title_div = toggle.find("div", class_="vc_toggle_title")
    if not title_div: continue
    
    h4 = title_div.find("h4")
    pregunta = h4.get_text(strip=True) if h4 else title_div.get_text(strip=True)
    
    # --- 2. Extraer Respuesta (Limpieza Profunda) ---
    content_div = toggle.find("div", class_="vc_toggle_content")
    if not content_div: continue
    
    # Reemplazar <br> y <p> con saltos de línea legibles
    for br in content_div.find_all("br"):
        br.replace_with("\n")
    for p in content_div.find_all("p"):
        p.append("\n") # Salto simple para párrafos
        
    # Obtener texto limpio
    respuesta_raw = content_div.get_text(separator=' ', strip=True)
    
    # Limpieza final de espacios dobles
    pregunta = re.sub(r'\s+', ' ', pregunta).strip()
    respuesta = re.sub(r'\s+', ' ', respuesta_raw).strip()
    
    if pregunta and respuesta:
        faqs.append([pregunta, respuesta])

# --- 3. Guardar CSV con BOM (utf-8-sig) ---
filename = 'faqs_unemi_final.csv'

with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    # Cabeceras
    writer.writerow(["Pregunta", "Respuesta"])
    # Datos
    writer.writerows(faqs)

print(f"✅ Archivo '{filename}' generado con {len(faqs)} preguntas. Listo para abrir en Excel.")