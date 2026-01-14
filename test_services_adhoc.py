import os
import sys
import django
import json

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from chatbot.models import SgaPersona, SgaRecordacademico, SgaInscripcion, SgaPerfilusuario, SgaMatricula
# Importamos TODAS las funciones del service actual
from chatbot.services import (
    q_estado_matricula, q_materias_matriculadas, q_nivel_semestre_paralelo,
    q_horario_semanal,
    q_rubros_pendientes, q_detalle_rubro, q_pagos_realizados,
    q_notas_periodo, q_asistencia_periodo, q_promedio_periodo, q_estado_calificacion,
    q_practicas
)

# Configuration
#TARGET_CEDULAS = ["0957040132"] #Regular
TARGET_CEDULAS = ["2300371198"] #Con rubros pendientes

#PERIODO_ID = 468 
DEFAULT_PERIODO_ID = 224
DETECT_LATEST_PERIOD = True

def print_json_pretty(label, data_str):
    """Ayuda visual para imprimir JSON bonito o texto plano si falla"""
    print(f"    [{label}]")
    try:
        # Intentamos parsear por si es un JSON string
        parsed = json.loads(data_str)
        # Imprimimos con indentación para leer fácil
        print(json.dumps(parsed, indent=4, ensure_ascii=False)) 
        return parsed
    except (json.JSONDecodeError, TypeError):
        # Si falla (porque es texto plano como 'No se encontraron datos'), imprimimos el texto
        print(f"       Result (Text): {data_str}")
        return None
    except Exception as e:
        print(f"       Error procesando respuesta: {e}")
        return None

def run_test():
    print(f"--- TESTING FULL ORM SERVICES (Default Periodo: {DEFAULT_PERIODO_ID}) ---")

    for cedula in TARGET_CEDULAS:
        print(f"\n{'='*60}")
        print(f">>> Testing Persona: {cedula}")
        persona = SgaPersona.objects.filter(cedula=cedula).first()
        
        if not persona:
            print("    [!] Persona not found")
            continue
        
        print(f"    Name: {persona}")
        
        # --- DYNAMIC PERIOD DETECTION ---
        periodo_id = DEFAULT_PERIODO_ID
        
        if DETECT_LATEST_PERIOD:
            try:
                perfiles_activos = SgaPerfilusuario.objects.filter(persona=persona, status=True)
                candidate_matriculas = []

                for p in perfiles_activos:
                    if p.inscripcion:
                        # Buscar matriculas para este perfil
                        mats = SgaMatricula.objects.filter(
                            inscripcion=p.inscripcion, 
                            retiradomatricula=False
                        ).select_related('nivel__periodo')
                        
                        for m in mats:
                            candidate_matriculas.append(m)

                if candidate_matriculas:
                    # Ordenar en Python por periodo ID desc, luego matricula ID desc
                    candidate_matriculas.sort(key=lambda x: (getattr(x.nivel.periodo, 'id', 0), x.id), reverse=True)
                    
                    matricula = candidate_matriculas[0]
                    
                    if matricula and matricula.nivel and matricula.nivel.periodo:
                        periodo_id = matricula.nivel.periodo.id
                        print(f"    [INFO] Periodo detectado automáticamente: {periodo_id} (Origen: Matrícula ID {matricula.id})")
                    else:
                        print(f"    [WARN] La matrícula más reciente no tiene periodo válido. Usando default: {periodo_id}")
                else:
                     print(f"    [WARN] No se encontraron matrículas en ningún perfil activo. Usando periodo default: {periodo_id}")

            except Exception as e:
                print(f"    [ERROR] Falló la detección de periodo: {e}. Usando default: {periodo_id}")
        else:
            print(f"    [INFO] Detección automática desactivada. Usando periodo default: {periodo_id}")

        
        # 1. Test Grades (Notas/Promedios/Asistencia/Estado)
        print("\n    [1. TOPIC: GRADES]")
        print_json_pretty("q_notas_periodo", q_notas_periodo(persona, periodo_id))
        print_json_pretty("q_asistencia_periodo", q_asistencia_periodo(persona, periodo_id))
        print_json_pretty("q_promedio_periodo", q_promedio_periodo(persona, periodo_id))
        print_json_pretty("q_estado_calificacion", q_estado_calificacion(persona, periodo_id))
        
        # 2. Test Matricula / Schedule
        print("\n    [2. TOPIC: SCHEDULE]")
        print_json_pretty("q_estado_matricula", q_estado_matricula(persona, periodo_id))
        print_json_pretty("q_nivel_semestre_paralelo", q_nivel_semestre_paralelo(persona, periodo_id))
        print_json_pretty("q_materias_matriculadas", q_materias_matriculadas(persona, periodo_id))
        print_json_pretty("q_horario_semanal", q_horario_semanal(persona, periodo_id))

        # 3. Test Financiero
        print("\n    [3. TOPIC: FINANCIAL]")
        rubros_data = print_json_pretty("q_rubros_pendientes", q_rubros_pendientes(persona))
        
        # Si hay rubros, probamos detalle del primero
        if rubros_data and isinstance(rubros_data, dict) and rubros_data.get("rubros"):
             first_rubro_id = rubros_data["rubros"][0]["rubro_id"]
             print(f"       -> Validando detalle para rubro ID: {first_rubro_id}")
             print_json_pretty("q_detalle_rubro", q_detalle_rubro(persona, first_rubro_id))
        
        print_json_pretty("q_pagos_realizados", q_pagos_realizados(persona))
        print_json_pretty("q_pagos_realizados", q_pagos_realizados(persona))

        # 4. Test Practicas
        print("\n    [4. TOPIC: PRACTICAS]")
        print_json_pretty("q_practicas", q_practicas(persona))

    print("\n--- Test Finished ---")

if __name__ == "__main__":
    run_test()