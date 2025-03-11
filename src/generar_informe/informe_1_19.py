import csv
import io
import json
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import pandas as pd
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
from docx2pdf import convert
from dotenv import load_dotenv
from fpdf import FPDF
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.chrome.options import Options


# Variable global
base_dir = os.path.dirname(__file__)
load_dotenv()
base_url = "http://127.0.0.1:1234"
api_key = os.getenv("API_KEY")
myModel = "lmstudio-community/DeepSeek-R1-Distill-Llama-8B-GGUF"

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
        
def ejecutar_API(enlaces):
    """Ejecuta la API sobre los enlaces y devuelve los resultados en memoria."""
    # Paso 1: Obtener el HTML de los enlaces y extraer los datos
    resultados = []
    for enlace in enlaces:
        html = obtener_html(enlace)
        if html:  # Verificar si el HTML fue obtenido correctamente
            datos = extraer_datos_llm(limpiar_html(html), enlace)
            resultados.append(datos)

    # Paso 2: Filtrar los resultados que no sean None
    resultados_filtrados = []  # Inicializamos una lista vacía para almacenar los resultados filtrados

    for res in resultados:  # Iteramos sobre todos los elementos de la lista "resultados"
        if res:  # Verificamos si el elemento "res" es considerado verdadero (es decir, no es None, vacío, etc.)
            resultados_filtrados.append(res)  # Si es verdadero, lo agregamos a la lista "resultados_filtrados"

    # Paso 3: Eliminar duplicados basados en el valor de "File"
    resultados_unicos = {}
    for res in resultados_filtrados:
        if res and "File" in res:
            resultados_unicos[res["File"]] = res

    # Convertir el diccionario de resultados únicos a una lista de valores
    resultados_filtrados_unicos = list(resultados_unicos.values())

    return list(resultados_filtrados_unicos)

def initialize_table(doc, headers):
    """Inicializa la tabla en el documento de Word con los encabezados."""
    for table in doc.tables:
        while len(table.columns) < len(headers):
            table.add_column(width=Inches(1.5))
        for i, header in enumerate(headers):
            table.cell(0, i).text = header
        return table  # Retornamos la primera tabla encontrada
    return None

def fill_table(table, headers, data):
    """Llena la tabla con encabezados y datos, asegurando que no haya duplicados."""
    
    # Eliminar todas las filas existentes si la tabla está vacía
    while len(table.rows) > 0:
        table._element.remove(table.rows[0]._element)

    # Crear la fila de encabezados
    header_row = table.add_row()
    for i, header in enumerate(headers):
        header_row.cells[i].text = header

    # Agregar filas con datos
    for row_data in data:
        row = table.add_row()
        for col_idx, value in enumerate(row_data):
            row.cells[col_idx].text = str(value)

  
# Función que genera el informe
def generar_informe(datos):
    """Genera el informe en memoria sin leer de Excel."""
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, 'informe_general.docx')
    print("Datos recibidos ", datos)
    if not os.path.exists(template_path):
        print(f"Error: No se encontró la plantilla {template_path}")
        return

    output_filename = "University_Country_1_19_Percentage_of_operation_and_maintenance_activities_of_building_in_one_year"
    output_docx_path = os.path.join(base_dir, f"{output_filename}.docx")
    output_pdf_path = os.path.join(base_dir, f"{output_filename}.pdf")

    doc = Document(template_path)

    # Reemplazar texto en la plantilla
    for paragraph in doc.paragraphs:
        paragraph.text = paragraph.text.replace(
            "[6] Education and Research (ED)", 
            "[1] Setting and Infrastructure (SI)\n\n"
            "[1.19] Percentage of operation and maintenance activities of building in one year period\n\n"
            "*Min. at least five maintenance classification for each building"
        )

    # Crear la tabla
    headers = ["Building", "Contract", "Maintenance Type", "File", "Link"]
    table = initialize_table(doc, headers)

    fill_table(table, headers, [list(d.values()) for d in datos])


    doc.save(output_docx_path)

    try:
        convert(output_docx_path, output_pdf_path)
    except Exception as e:
        print(f"Error al convertir a PDF: {e}")

    print(f"Documento PDF generado en: {output_pdf_path}")
    
def buscar():  
    # El navegador no muestra su interfaz gráfica.
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Habilita el modo headless

    # Iniciar el navegador
    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://contratacion.ubu.es/licitacion/busquedaAvanzConc.do")

    # Esperar a que la página cargue
    time.sleep(3)
   
    # # Llenar el campo "Expediente"
    # campo_expediente = driver.find_element(By.ID, "expediente")  # Usar ID correcto
    # campo_expediente.send_keys('UBU/2023/0018')

    # Llenar el campo "Objeto"
    campo_objeto = driver.find_element(By.ID, "ObjContrato")  # Ajusta el NAME real
    objeto = "Mantenimiento"
    campo_objeto.send_keys(objeto)



    # Marcar la casilla "Ver expedientes de organismos dependientes"
    casilla_organismos = driver.find_element(By.NAME, "descendientes")  # Ajusta el NAME real
    if not casilla_organismos.is_selected():
        casilla_organismos.click()  # Marcar la casilla si no está seleccionada

    # Hacer clic en el botón de búsqueda
    boton_buscar = driver.find_element(By.NAME, "busquedaFormAvanz")  # Ajusta el NAME real
    boton_buscar.click()

    # Encuentra todas las filas de la tabla con la clase 'resultados'
    resultados = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".resultados tbody tr")))

    enlaces = []  
    
    # Verifica si hay resultados
    if len(resultados) == 0:
        print("No se encontraron resultados.")
    else:
        for resultado in resultados:
            #columnas = resultado.find_elements(By.TAG_NAME, "td")  # Extraer columnas de cada fila
            #datos = [col.text.strip() for col in columnas]  # Obtener el texto de cada celda
            # Extraer el enlace de la primera columna (suponiendo que está en la primera columna)
            enlace = None
            enlace_elemento = resultado.find_element(By.CSS_SELECTOR, "a")
            if enlace_elemento:
                enlace = enlace_elemento.get_attribute("href")  # Obtener el atributo href del enlace
                enlaces.append(enlace)  # Guardar todos los enlaces en la 
    print("enlaces", enlaces)
    # Cerrar el navegador cuando termine
    driver.quit()
    return enlaces
    
    
def generar():
    enlaces= buscar()
    datos = ejecutar_API(enlaces)
    generar_informe(datos)





    

