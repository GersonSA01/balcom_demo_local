from fpdf import FPDF
from fpdf.enums import XPos, YPos
import json
import os
from datetime import datetime

def sanitize_text(text):
    """
    Limpia el texto para que sea compatible con el encoding Latin-1 de FPDF.
    Elimina emojis y caracteres especiales que rompen la generación del PDF.
    """
    if not text:
        return ""
    # Reemplazar retornos de carro para evitar problemas de formato
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Codificar a latin-1 ignorando los caracteres que no pertenezcan a ese set (como emojis)
    return text.encode('latin-1', 'ignore').decode('latin-1')

class ReporteChatbotPDF(FPDF):
    def header(self):
        # Logo o Título
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(18, 33, 106) # Azul institucional
        self.cell(0, 10, 'INFORME DE CONTROL DE CALIDAD - CHATBOT BALCON', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        self.set_font('helvetica', '', 10)
        self.set_text_color(100)
        fecha_gen = datetime.now().strftime('%d/%m/%Y %H:%M')
        self.cell(0, 5, f'Generado el: {fecha_gen}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # Línea divisoria decorativa
        self.set_draw_color(255, 111, 29) # Naranja institucional
        self.set_line_width(0.5)
        self.line(10, 32, 200, 32)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()}/{{nb}} - UNEMI Balcon de Servicios', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')

def generar_pdf(jsonl_path, output_path):
    if not os.path.exists(jsonl_path):
        print(f"❌ Error: No se encontro {jsonl_path}")
        return

    resultados = []
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    resultados.append(json.loads(line))
    except Exception as e:
        print(f"❌ Error leyendo JSONL: {e}")
        return

    if not resultados:
        print("❌ Error: No hay datos para el reporte.")
        return

    # Usar FPDF con soporte para alias de numero de paginas
    pdf = ReporteChatbotPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Resumen Ejecutivo
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, '  RESUMEN DE PRUEBAS', border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
    
    total = len(resultados)
    latencias = [r['metadatos']['latencia'] for r in resultados]
    avg_lat = sum(latencias) / total if total > 0 else 0
    fuentes_uso = sum([1 for r in resultados if r['metadatos'].get('fuentes')])

    pdf.set_font('helvetica', '', 10)
    pdf.ln(2)
    pdf.cell(60, 7, f'Total de casos: {total}', new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 7, f'Latencia media: {avg_lat:.2f} segundos', new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 7, f'Uso de fuentes RAG: {fuentes_uso}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # Detalle de Casos
    case_num = 1
    for res in resultados:
        # Título de caso
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(0, 8, f' CASO #{case_num} - Usuario: {res["cedula"]}', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
        pdf.set_font('helvetica', '', 8)
        pdf.cell(0, 5, f'Timestamp: {res["metadatos"]["timestamp"]} | Latencia: {res["metadatos"]["latencia"]}s', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        
        pdf.ln(2)
        
        # Pregunta
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(18, 33, 106)
        pdf.cell(0, 5, 'PREGUNTA DEL USUARIO:', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(50)
        pdf.multi_cell(0, 5, sanitize_text(res['pregunta']), align='L')
        pdf.ln(3)

        # Respuesta Esperada
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(18, 33, 106)
        pdf.cell(0, 5, 'RESPUESTA ESPERADA (HISTORICA):', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(30)
        resolucion = res.get('resolucion_original', '')
        if not resolucion: resolucion = "N/A (No establecida)"
        pdf.multi_cell(0, 5, sanitize_text(resolucion), align='L')
        pdf.ln(3)

        # Respuesta Chatbot
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(18, 33, 106)
        pdf.cell(0, 5, 'RESPUESTA DEL CHATBOT:', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(30)
        pdf.multi_cell(0, 5, sanitize_text(res['respuesta_chatbot']), align='L')
        
        # Fuentes si existen
        if res['metadatos'].get('fuentes'):
            pdf.ln(2)
            pdf.set_font('helvetica', 'B', 8)
            pdf.set_text_color(100)
            pdf.cell(20, 5, 'FUENTES:', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.set_font('helvetica', '', 8)
            pdf.cell(0, 5, sanitize_text(', '.join(res['metadatos']['fuentes'])), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(5)
        pdf.set_draw_color(220)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        case_num += 1

    try:
        pdf.output(output_path)
        print(f"✅ Reporte PDF generado exitosamente: {output_path}")
    except Exception as e:
        print(f"❌ Error guardando PDF: {e}")

if __name__ == "__main__":
    generar_pdf("resultados_pruebas.jsonl", "reporte_pruebas.pdf")
