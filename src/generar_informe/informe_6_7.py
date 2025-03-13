import csv
import io
import json
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from io import BytesIO


import re
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


def generar_enlace (year_range) :
    start_year, end_year = map(int, year_range.split('-'))
    enlace = f"https://scholar.google.es/scholar?hl=es&as_sdt=0%2C5&as_ylo={start_year}&as_yhi={end_year}&q=%22Universidad+de+Burgos%22+%26+%28%22green%22+OR+%22environment%22+OR+%22sustainability%22+OR+%22renewable+energy%22+OR+%22climate+change%22%29&btnG="
    return enlace, start_year, end_year
            
def fill_description(doc, year_range, num_courses):
    enlace, start_year, end_year=generar_enlace(year_range)
    num_years = end_year - start_year + 1  # Calcular el número de años en el rango

    description_text = (
        f"Results obtained from the following query in the {num_years}-year interval set and using the keywords provided in the questionnaire.\n\n"
        f"\"Universidad de Burgos\" & (\"green\" OR \"environment\" OR \"sustainability\" OR \"renewable energy\" OR \"climate change\")\n\n"
        f"Scholarly publications on sustainability in the academic years {start_year}-{end_year}.\n\n"
        f"A total average per annum over the last {num_years} years of {num_courses} / {num_years} = {num_courses // num_years} publications.\n\n"
        
    )
    
    Additional_evidence_text=(
        f"Additional evidence link (i.e., for videos, more images, or other files that are not included in this file):\n\n"
        f"{enlace}"
    )

    for para in doc.paragraphs:
        if "Description:" in para.text:
            para.text = f"Description:\n\n{description_text}"
            
        elif "Additional evidence link (i.e., for videos, more images, or other files that are not included in this file):" in para.text:
            para.text = f"{Additional_evidence_text}"
            break
 
def agregar_imagen_a_tabla(doc, captura_pantalla):
    # Buscar la tabla en el documento (se asume que es la primera tabla en el documento)
    table = doc.tables[0]  # Suponiendo que es la primera tabla en el documento
    rows = table.rows
    
    # Insertar la captura de pantalla en la primera celda de la primera fila
    cell = rows[0].cells[0]
    image_stream = BytesIO(captura_pantalla)  # Convertir los bytes a un stream
    picture = cell.paragraphs[0].add_run().add_picture(image_stream)  # Añadir la imagen
    
    # Establecer un tamaño específico para la imagen si es necesario
    # Aquí ajustas el tamaño de la imagen según lo necesites (ejemplo: 2 pulgadas de ancho)
    picture.width = Inches(6)
    picture.height = Inches(3)  # Si también necesitas ajustar la altura

    # Después de insertar la imagen, la celda se ajustará automáticamente en tamaño para contenerla

    # Si la tabla ya tiene dos filas, vamos a insertar el texto en la segunda celda de la segunda fila
    if len(rows) > 1:
        text_cell = rows[1].cells[0]  # Asumimos que la segunda fila tiene la primera celda para el texto
        text_cell.text = 'Scholarly publications on sustainability (Universidad de Burgos, Spain)'

    else:
        # Si no hay suficientes filas, añadimos una nueva fila con dos celdas y el texto
        new_row = table.add_row()
        new_row.cells[0].text = 'Scholarly publications on sustainability (Universidad de Burgos, Spain)'
        # La segunda celda estará vacía (podrías agregar algo más si lo necesitas)
        new_row.cells[1].text = ''
  
# Función que genera el informe
def generar_informe(captura_pantalla,anho,numero_resultados):
        
    """Genera el informe en memoria sin leer de Excel."""
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, 'informe_general.docx')
   
    if not os.path.exists(template_path):
        print(f"Error: No se encontró la plantilla {template_path}")
        return

    output_filename = "University_Country_6_7_Number_of_scholarly_publications_on_sustainability_UBU"
    output_docx_path = os.path.join(base_dir, f"{output_filename}.docx")
    output_pdf_path = os.path.join(base_dir, f"{output_filename}.pdf")

    doc = Document(template_path)

    # Reemplazar texto en la plantilla
    for paragraph in doc.paragraphs:
        if  "[6] Education and Research (ED)" in paragraph.text:
            paragraph.text = f" [6] Education and Research (ED) \n\n [6.7] Number of scholarly publications on sustainability"   
            break
   

    agregar_imagen_a_tabla(doc, captura_pantalla)

    fill_description(doc,anho,numero_resultados)


    doc.save(output_docx_path)

    try:
        convert(output_docx_path, output_pdf_path)
    except Exception as e:
        print(f"Error al convertir a PDF: {e}")

    print(f"Documento PDF generado en: {output_pdf_path}")


def buscar(anho):
    # Configurar Selenium en modo headless
    chrome_options = Options()
    chrome_options.add_argument("--headless")  

    # Iniciar el navegador
    driver = webdriver.Chrome(options=chrome_options)
    enlace, start_year, end_year = generar_enlace(anho)
    driver.get(enlace)

    try:
        # Esperar hasta que el elemento que contiene el número de resultados esté presente
        resultado_elemento = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#gs_ab_md div.gs_ab_mdw"))
        )
        
        # Extraer el texto del elemento que contiene el número de resultados
        texto = resultado_elemento.text
        # Buscar el número de resultados con un patrón
        numero_resultados = re.search(r"Aproximadamente (\d{1,3}(?:\.\d{3})*) resultados", texto)

        if numero_resultados:
            numero_resultados = numero_resultados.group(1).replace(".", "")  # Eliminar los puntos y obtener el número limpio
        else:
            print("No se encontró el número de resultados.")
        
        # Captura de pantalla
        captura_pantalla = driver.get_screenshot_as_png()
        
    except Exception as e:
        print("Error al extraer los resultados:", e)
    numero_resultados_convertido=int(numero_resultados)
    # Cerrar el navegador
    driver.quit()
    return captura_pantalla, numero_resultados_convertido
    
 


def generar(anho):
    captura_pantalla, numero_resultados= buscar(anho)
    generar_informe(captura_pantalla,anho,numero_resultados)



    

