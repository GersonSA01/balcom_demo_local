
import json
from django.db.models import Sum
from .models import (
    SgaMatricula, SgaRecordacademico, 
    SgaPracticaspreprofesionalesinscripcion, SgaProyectogrado, SgaPreproyectogradoInscripciones,
    SgaInscripcion, SgaMateriaasignada, SagestRubro, SgaProyectosgrado, SgaAnteproyectoInscripciones,
    SgaAsignaturamalla, SgaAsignatura, SgaMateria, SgaInscripcionmalla,
    # Schedule
    SgaClase, SgaTurno,
    # Financial
    SagestPago,
    # Exams
    SgaHorarioexamendetallealumno,
    # Requisitos
    SgaAsignaturaPrecedencia,
)
from collections import defaultdict
from django.utils import timezone


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _get_inscripciones_activas(persona):
    # SgaInscripcion tiene persona/carrera (unique_together persona,carrera)
    return SgaInscripcion.objects.filter(persona=persona, carrera__status=True)

def _get_matricula(persona, periodo_id=None):
    inscripciones = _get_inscripciones_activas(persona)
    if not inscripciones.exists():
        return None, "No se encontró inscripción activa."

    filtros = {"inscripcion__in": inscripciones, "status": True}
    if periodo_id:
        try:
            filtros["nivel__periodo__id"] = int(periodo_id)
        except ValueError:
            return None, "El periodo_id es inválido."

    matricula = SgaMatricula.objects.filter(**filtros).order_by("-id").first()
    if not matricula:
        if not periodo_id:
            return None, "No tienes matrícula activa. Indica el periodo."
        return None, "No se encontró matrícula para ese periodo."
    return matricula, None

def _get_materias_asignadas(persona, periodo_id=None):
    matricula, err = _get_matricula(persona, periodo_id)
    if err:
        return None, err
    qs = SgaMateriaasignada.objects.filter(matricula=matricula, status=True)
    return qs, None

# -----------------------------------------------------------------------------
# TOPIC: SCHEDULE (Matrícula/Materias/Horario/Choques)
# -----------------------------------------------------------------------------
def q_estado_matricula(persona, periodo_id=None):
    matricula, err = _get_matricula(persona, periodo_id)
    if err:
        # CORRECCIÓN: Devolver JSON incluso en error
        return json.dumps({"error": err, "estado": "SIN_DATOS"}, ensure_ascii=False)

    # Prioridad: estado_matricula (Choices) > aprobado (Boolean)
    if hasattr(matricula, "get_estado_matricula_display"):
        estado = matricula.get_estado_matricula_display()
    else:
        estado = "MATRICULADO"

    if getattr(matricula, "retiradomatricula", False):
        estado = "RETIRADO"
    
    data = {
        "estado": estado,
        "periodo": getattr(matricula.nivel.periodo, "nombre", None),
        "carrera": getattr(matricula.inscripcion.carrera, "nombre", None),
    }
    return json.dumps(data, ensure_ascii=False)

def q_materias_matriculadas(persona, periodo_id=None):
    materias_asignadas, err = _get_materias_asignadas(persona, periodo_id)
    if err:
        # CORRECCIÓN: Devolver JSON incluso en error
        return json.dumps({"error": err, "materias": []}, ensure_ascii=False)

    materias_asignadas = materias_asignadas.select_related("materia__asignatura")

    out = []
    for ma in materias_asignadas:
        out.append({
            "asignatura": ma.materia.asignatura.nombre if ma.materia and ma.materia.asignatura else None,
            "paralelo": getattr(ma.materia, "paralelo", None),
        })
    return json.dumps({"materias": out}, ensure_ascii=False)

def q_nivel_semestre_paralelo(persona, periodo_id=None):
    matricula, err = _get_matricula(persona, periodo_id)
    if err:
        # CORRECCIÓN: Devolver JSON incluso en error
        return json.dumps({"error": err}, ensure_ascii=False)

    paralelo = getattr(matricula.nivel, "paralelo", None)
    nivel_nombre = None
    
    # 1. Intentar nivel de malla directo
    try:
        if matricula.nivel.nivelmalla:
            nivel_nombre = matricula.nivel.nivelmalla.nombre
    except:
        pass

    # 2. Refinamiento con Materias (SgaAsignaturamalla)
    # Lógica portada de get_info_matricula para soporte multi-nivel
    try:
         materias_asignadas = SgaMateriaasignada.objects.filter(matricula=matricula, status=True)
         if materias_asignadas.exists():
            im = SgaInscripcionmalla.objects.filter(inscripcion=matricula.inscripcion, status=True).first()
            if im and im.malla:
                malla_estudiante = im.malla
                niveles_detectados = set()
                
                for ma in materias_asignadas:
                    am = SgaAsignaturamalla.objects.filter(
                        asignatura=ma.materia.asignatura, 
                        malla=malla_estudiante,
                        status=True
                    ).select_related('nivelmalla').first()
                    
                    if am and am.nivelmalla:
                        niveles_detectados.add(am.nivelmalla.nombre)
                
                if niveles_detectados:
                    niveles_lista = sorted(list(niveles_detectados))
                    nivel_nombre = ", ".join(niveles_lista)
    except Exception as e:
        print(f"Error refinando nivel en q_nivel: {e}")

    return json.dumps({
        # "nivel_id": matricula.nivel_id, # Eliminado
        "nivel": nivel_nombre,
        "paralelo": paralelo,
    }, ensure_ascii=False)

def q_horario_semanal(persona, periodo_id=None):
    materias_asignadas, err = _get_materias_asignadas(persona, periodo_id)
    if err:
        # CORRECCIÓN: Devolver JSON incluso en error
        return json.dumps({"error": err, "horario": []}, ensure_ascii=False)

    materia_ids = list(materias_asignadas.values_list("materia_id", flat=True))

    clases = (SgaClase.objects
              .filter(materia_id__in=materia_ids, status=True, activo=True)
              .select_related("turno", "materia__asignatura", "profesor__persona", "aula"))

    items = []
    dias_semana = {
        1: "Lunes", 2: "Martes", 3: "Miercoles", 4: "Jueves", 
        5: "Viernes", 6: "Sabado", 7: "Domingo"
    }

    for c in clases:
        profesor_nombre = "Por Asignar"
        if c.profesor and c.profesor.persona:
            p = c.profesor.persona
            profesor_nombre = f"{p.nombres} {p.apellido1} {p.apellido2}".strip()
        
        aula_nombre = "Por Asignar"
        if c.aula:
            aula_nombre = c.aula.nombre

        items.append({
            "dia": dias_semana.get(c.dia, f"Día {c.dia}"),
            "hora_inicio": str(getattr(c.turno, "comienza", "")),
            "hora_fin": str(getattr(c.turno, "termina", "")),
            "asignatura": c.materia.asignatura.nombre if c.materia and c.materia.asignatura else None,
            "aula": aula_nombre,
            "profesor": profesor_nombre,
        })

    clases = sorted(clases, key=lambda x: (x.dia, getattr(x.turno, "comienza", "")))

    # Re-iterate on sorted list
    final_items = []
    for c in clases:
        profesor_nombre = "Por Asignar"
        if c.profesor and c.profesor.persona:
            p = c.profesor.persona
            profesor_nombre = f"{p.nombres} {p.apellido1} {p.apellido2}".strip()
        
        aula_nombre = "Por Asignar"
        if c.aula:
            aula_nombre = c.aula.nombre

        final_items.append({
            "dia": dias_semana.get(c.dia, f"Día {c.dia}"),
            "hora_inicio": str(getattr(c.turno, "comienza", "")),
            "hora_fin": str(getattr(c.turno, "termina", "")),
            "asignatura": c.materia.asignatura.nombre if c.materia and c.materia.asignatura else None,
            "aula": aula_nombre,
            "profesor": profesor_nombre,
        })
        
    return json.dumps({"horario": final_items}, ensure_ascii=False)



# -----------------------------------------------------------------------------
# TOPIC: FINANCIAL (Rubros/Pagos/Deudas/Bloqueos)
# -----------------------------------------------------------------------------
def q_rubros_pendientes(persona):
    rubros = SagestRubro.objects.filter(persona=persona, cancelado=False, status=True)
    if not rubros.exists():
        return json.dumps({"estado": "SIN_DEUDA", "rubros": []}, ensure_ascii=False)

    total = rubros.aggregate(Sum("saldo"))["saldo__sum"] or 0
    items = []
    for r in rubros:
        items.append({
            "rubro_id": r.id,
            "concepto": getattr(r, "nombre", None),
            "valor_total": float(getattr(r, "valor", 0) or 0),
            "saldo": float(getattr(r, "saldo", 0) or 0),
            "vence": str(getattr(r, "fechavence", "")),
        })
    return json.dumps({"estado": "CON_DEUDA", "rubros": items}, ensure_ascii=False)

def q_detalle_rubro(persona, rubro_id:int):
    r = SagestRubro.objects.filter(persona=persona, id=int(rubro_id), status=True).first()
    if not r:
        return "No se encontró ese rubro para tu cuenta."
    data = {
        "rubro_id": r.id,
        "concepto": getattr(r, "nombre", None),
        "valor_total": float(getattr(r, "valor", 0) or 0),
        "saldo": float(getattr(r, "saldo", 0) or 0),
        "vence": str(getattr(r, "fechavence", "")),
        "cancelado": bool(getattr(r, "cancelado", False)),
        "bloqueado": bool(getattr(r, "bloqueado", False)),
        "coactiva": bool(getattr(r, "coactiva", False)),
    }
    return json.dumps(data, ensure_ascii=False)

def q_pagos_realizados(persona, limit=20):
    pagos = (SagestPago.objects
             .filter(rubro__persona=persona, status=True)
             .select_related("rubro")
             .order_by("-fecha")[:int(limit)])

    out = []
    for p in pagos:
        out.append({
            "pago_id": p.id,
            "fecha": str(getattr(p, "fecha", "")),
            "valor": float(getattr(p, "valortotal", 0) or 0),
            "referencia": getattr(p, "referenciapago", None),
            "rubro": getattr(p.rubro, "nombre", None) if getattr(p, "rubro", None) else None,
            "comprobante": p.comprobante.numero if getattr(p, "comprobante", None) else None,
        })
    return json.dumps({"pagos": out}, ensure_ascii=False)




# -----------------------------------------------------------------------------
# TOPIC: GRADES (Notas/Promedios/Asistencia/Estado calificación)
# -----------------------------------------------------------------------------
def q_notas_periodo(persona, periodo_id:int):
    try:
        periodo_id = int(periodo_id)
    except:
        return json.dumps({"error": "ID de periodo inválido.", "notas": {}}, ensure_ascii=False)

    records = (SgaRecordacademico.objects
               .filter(inscripcion__persona=persona,
                       materiaregular__nivel__periodo__id=periodo_id,
                       status=True)
               .select_related("asignatura"))

    materias_asignadas = (SgaMateriaasignada.objects
                          .filter(matricula__inscripcion__persona=persona,
                                  matricula__nivel__periodo__id=periodo_id,
                                  status=True)
                          .select_related("materia__asignatura"))

    if not records.exists() and not materias_asignadas.exists():
        # CORRECCIÓN: JSON en vez de string plano
        return json.dumps({"error": "No se encontraron notas/materias para ese periodo.", "notas": {}}, ensure_ascii=False)

    notas = {}

    for ma in materias_asignadas:
        nombre = ma.materia.asignatura.nombre if ma.materia and ma.materia.asignatura else "Materia"
        estado = "CURSANDO"
        if getattr(ma, "retiramateria", False):
            estado = "RETIRADA"
        elif getattr(ma, "cerrado", False):
            estado = "APROBADO" if (getattr(ma, "notafinal", 0) or 0) >= 70 else "REPROBADO"

        notas[nombre] = {
            "nota": float(getattr(ma, "notafinal", 0) or 0),
            "asistencia": float(getattr(ma, "asistenciafinal", 0) or 0),
            "estado": estado
        }

    for r in records:
        nombre = r.asignatura.nombre if r.asignatura else "Materia"
        notas[nombre] = {
            "nota": float(getattr(r, "nota", 0) or 0),
            "asistencia": float(getattr(r, "asistencia", 0) or 0),
            "estado": "APROBADO" if getattr(r, "aprobada", False) else "REPROBADO"
        }

    return json.dumps({"periodo_id": periodo_id, "notas": notas}, ensure_ascii=False)

def q_asistencia_periodo(persona, periodo_id:int):
    data = json.loads(q_notas_periodo(persona, periodo_id))
    notas = data.get("notas", {})
    if not notas:
        return "No hay datos de asistencia para ese periodo."
    vals = [v.get("asistencia", 0) for v in notas.values() if v.get("estado") != "RETIRADA"]
    prom = sum(vals)/len(vals) if vals else 0
    return json.dumps({"periodo_id": int(periodo_id), "asistencia_promedio": prom, "detalle": notas}, ensure_ascii=False)

def q_promedio_periodo(persona, periodo_id:int):
    data = json.loads(q_notas_periodo(persona, periodo_id))
    notas = data.get("notas", {})
    vals = [v.get("nota", 0) for v in notas.values() if v.get("estado") not in ("RETIRADA", "CURSANDO")]
    prom = sum(vals)/len(vals) if vals else 0
    return json.dumps({"periodo_id": int(periodo_id), "promedio": prom}, ensure_ascii=False)

def q_estado_calificacion(persona, periodo_id:int):
    data = json.loads(q_notas_periodo(persona, periodo_id))
    out = {}
    for mat, v in data.get("notas", {}).items():
        out[mat] = "PUBLICADA" if v.get("estado") in ("APROBADO", "REPROBADO") else "PENDIENTE"
    return json.dumps({"periodo_id": int(periodo_id), "estado_calificacion": out}, ensure_ascii=False)

# -----------------------------------------------------------------------------
# TOPIC: PRACTICAS
# -----------------------------------------------------------------------------
def q_practicas(persona):
    practicas = SgaPracticaspreprofesionalesinscripcion.objects.filter(inscripcion__persona=persona, status=True)
    if not practicas.exists():
        # CORRECCIÓN: JSON en vez de string plano
        return json.dumps({"mensaje": "No se encontraron prácticas registradas.", "practicas": []}, ensure_ascii=False)
    out = []
    for p in practicas:
        out.append({
            "institucion": getattr(p, "institucion", None),
            "horas": getattr(p, "numerohora", None),
            "fecha_inicio": str(getattr(p, "fechadesde", "")),
            "estado": "Culminada" if getattr(p, "culminada", False) else "En proceso/Vigente"
        })
    return json.dumps({"practicas": out}, ensure_ascii=False)
