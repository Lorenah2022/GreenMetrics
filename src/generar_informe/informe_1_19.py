import requests
from fpdf import FPDF
import xml.etree.ElementTree as ET
import os
import json
import pandas as pd
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv
import io
from docx import Document
from docx.shared import Inches
from docx2pdf import convert
import sys
import csv

base_dir = os.path.dirname(__file__)

# Función para reemplazar texto en un documento de Word
def replace_text_in_docx(doc, old_text, new_text):
    for paragraph in doc.paragraphs:
        if old_text in paragraph.text:
            paragraph.text = new_text

def remove_text_from_docx(doc, text_to_remove):
    """Elimina cualquier párrafo que contenga el texto especificado."""
    for paragraph in doc.paragraphs:
        if text_to_remove in paragraph.text:
            paragraph.text = ""  # Eliminar el texto


def extraer_licitaciones():
    rss_url = "https://contratacion.ubu.es/licitacion/rest/rss/expediente/1753"
    def obtener_rss(url):
        response = requests.get(url)
        return response.text if response.status_code == 200 else None
    
    def extraer_enlaces_rss(contenido_rss):
        root = ET.fromstring(contenido_rss)
        return [item.find("link").text for item in root.findall(".//item") if item.find("link") is not None]
    
    def crear_pdf_con_enlaces(enlaces, archivo_pdf):
        # Obtener el directorio del archivo
        directorio = os.path.dirname(archivo_pdf)
        
        # Verificar si el directorio existe, si no, crearlo
        if not os.path.exists(directorio):
            os.makedirs(directorio)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, "Enlaces del Feed RSS", ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", size=10)
        for enlace in enlaces:
            pdf.multi_cell(0, 10, enlace)
            pdf.ln(5)
        
        pdf.output(archivo_pdf)
        print(f"Archivo PDF guardado en: {archivo_pdf}")
    
    contenido_rss = obtener_rss(rss_url)
    if contenido_rss:
        enlaces = extraer_enlaces_rss(contenido_rss)
        if enlaces:
            # Ruta corregida
            pdf_path = os.path.join(base_dir, "enlaces_rss.pdf")
            crear_pdf_con_enlaces(enlaces, pdf_path)


def ejecutar_API():
    pdf_path = os.path.join(base_dir, "enlaces_rss.pdf")
    load_dotenv()
    base_url = "http://127.0.0.1:1234"
    api_key = os.getenv("API_KEY")
    myModel = "lmstudio-community/DeepSeek-R1-Distill-Llama-8B-GGUF"
    
    def extraer_enlaces_de_pdf(pdf_path):
        enlaces = set()
        with open(pdf_path, "rb") as file:
            reader = PdfReader(file)
            for page in reader.pages:
                texto = page.extract_text()
                if texto:
                    urls = re.findall(r"https?://[^\s<>\"']+", texto)
                    enlaces.update(url for url in urls if "idExpediente=" in url and url[-1].isdigit())
        return sorted(enlaces)
    
    def obtener_html(url):
        try:
            response = requests.get(url, timeout=10)
            return response.text if response.status_code == 200 else None
        except requests.exceptions.RequestException:
            return None
    
    def limpiar_html(html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        texto_limpio = soup.get_text(separator="\n", strip=True)
        return " ".join(texto_limpio.split()[:3500])
    
    def extraer_datos_llm(html_texto, url):
        if not html_texto:
            return None

        body = {
            "model": myModel,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract and return only the following fields:\n"
                        "1. Building: Extracted from Objeto. If the text mentions 'buildings', return 'All university buildings'.\n"
                        "2. Contract: Extracted from the CPV section, including the text after the number [CPV Code]. This will be the detailed description of the contract, e.g., 'Servicios de reparación y mantenimiento de equipos eléctricos de edificios'.\n"
                        "3. Maintenance Type: Extracted from the CPV section, typically indicating the type of maintenance. For example, 'Mantenimiento de equipos eléctricos de edificios'.\n"
                        "4. File: Extracted from 'Expediente'. If the text appears in the format 'Expediente X UBU/2023/0018 (Company Name)', return only 'UBU/2023/0018' and ignore the company name inside parentheses.\n"
                        "5. Link:"
                        "Extract and return only the following fields in a single line, separated by commas in this format:\n"
                        "Building,Contract,Maintenance Type,File,Link\n"
                        "Do NOT include extra text, explanations, or headers.\n"
                        "Ensure that you return ONLY these five fields in a single line, without extra text."

                            )
                },
                {
                    "role": "user",
                    "content": html_texto
                }
            ],
            "temperature": 0.2
        }
        
        body_json = json.dumps(body)

        response = requests.post(
            f"{base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            data=body_json
        )

        if response.status_code != 200:
            print(f"Error en la API para {url}: {response.status_code} - {response.text}")
            return None
       

        #  Obtener respuesta limpia
        message_content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        #  Eliminar `</think>` si existe
        if "</think>" in message_content:
            message_content = message_content.split("</think>")[-1].strip()

        #  Procesar como CSV usando `csv.reader`
        try:
            csv_reader = csv.reader(io.StringIO(message_content))  # Convertir texto a archivo virtual
            contenido_separado = next(csv_reader)  # Obtener la primera (y única) línea
            
        except Exception as e:
            print(f"Error al leer CSV: {e}\nTexto recibido:\n{message_content}")
            return None

        #  Validar si tiene los 5 elementos requeridos
        if len(contenido_separado) >= 5:
            return {
                "Building": contenido_separado[0].strip(),
                "Contract": contenido_separado[1].strip(),
                "Maintenance Type": contenido_separado[2].strip(),
                "File": contenido_separado[3].strip(),
                "Link": url
            }
        else:
            print(f" Error: La respuesta de la IA no tiene el formato correcto.\nRecibido:\n{message_content}")
            return None
    enlaces = extraer_enlaces_de_pdf(pdf_path)
    resultados = [extraer_datos_llm(limpiar_html(obtener_html(enlace)), enlace) for enlace in enlaces if obtener_html(enlace)]
    
    # Filtrar valores None antes de crear el DataFrame
    resultados_filtrados = [res for res in resultados if res is not None]

    
    # Eliminar duplicados en la columna "File"
    df = pd.DataFrame(resultados_filtrados, columns=["Building", "Contract", "Maintenance Type", "File", "Link"])
    df = df.drop_duplicates(subset=["File"], keep="first")  # Se queda con el primer registro de cada "File"

    if not df.empty:
        df.to_excel("resultados_licitaciones.xlsx", index=False)
        print("\nArchivo Excel guardado sin duplicados en 'File'.")
    else:
        print("No se generaron datos válidos. No se creó el archivo Excel.")

  
# Función que genera el informe
def generar_informe():
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, 'informe_general.docx')
    if not os.path.exists(template_path):
        print(f"Error: No se encontró la plantilla {template_path}")
        sys.exit(1)
    
    excel_data_path = "resultados_licitaciones.xlsx"
    output_filename = "University_Country_1_19_Percentage_of_operation_and_maintenance_activities_of_building_in_one_year_pe"
    headers_custom = ["Building", "Contract", "Maintenance Type", "File", "Link"]
    output_docx_path = os.path.join(base_dir, f"{output_filename}.docx")
    output_pdf_path = os.path.join(base_dir, f"{output_filename}.pdf")
    
    def extract_data_from_excel(path):
        df = pd.read_excel(path)
        df = df[df['Building'].notna()]
        return headers_custom, df.values.tolist()
    
    def fill_table(doc, headers, data):
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell.text = ""
            while len(table.columns) < len(headers):
                table.add_column(width=Inches(1.5))
            for i, header in enumerate(headers):
                table.cell(0, i).text = header
            for row_idx, row in enumerate(data):
                if row_idx + 1 >= len(table.rows):
                    table.add_row()
                for col_idx, value in enumerate(row):
                    table.cell(row_idx + 1, col_idx).text = str(value)
            break
    
    doc = Document(template_path)
    # Reemplazar el texto específico en la plantilla
    replace_text_in_docx(doc, "[6] Education and Research (ED)", 
        "[1] Setting and Infrastructure (SI)\n\n"
        "[1.19] Percentage of operation and maintenance activities of building in one year period\n\n"
        "*Min. at least five maintenance classification for each building"
    )
    headers, data_from_excel = extract_data_from_excel(excel_data_path)
    
    fill_table(doc, headers, data_from_excel)
    
    # Eliminar "Description: " si aparece en el documento
    remove_text_from_docx(doc, "Description:")

    doc.save(output_docx_path)
    
    try:
        convert(output_docx_path, output_pdf_path)
    except Exception as e:
        print(f"Error al convertir a PDF: {e}")
    
    print(f"Documento PDF generado en: {output_pdf_path}")

# Función que llama en el orden correcto al resto de funciones.
def generar():
    extraer_licitaciones()
    ejecutar_API()
    generar_informe()

