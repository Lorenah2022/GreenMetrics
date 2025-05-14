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
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from dotenv import load_dotenv
from fpdf import FPDF
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.chrome.options import Options

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Agregar `src` al sys.path para poder importar `config.py`
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from config import cargar_configuracion

# Variable global
base_dir = os.path.dirname(__file__)
load_dotenv()
# Configuración de la API
config = cargar_configuracion()
base_url = config["base_url"]
api_key = config["api_key"]
myModel = config["model"]


carpeta = os.path.join(base_dir, 'UBU_Verde_informes')




def extraer_anhos(year_range):
    """Extrae los años desde un string tipo '2022-2025' y devuelve una lista [2022, 2023, 2024, 2025]."""
    match = re.match(r"(\d{4})-(\d{4})", year_range)
    if match:
        inicio, fin = int(match.group(1)), int(match.group(2))
        
        return [f"{año}-{str(año+1)[-2:]}" for año in range(inicio, fin)]
    return []




def buscar_ficheros(cursos, carpeta):
    """Busca archivos que terminan con _AÑO-AÑO.docx dentro de la carpeta."""
    archivos_encontrados = []
    for archivo in os.listdir(carpeta):
        for curso in cursos:
            curso_formato = curso.replace("-", "")  # Eliminar el guion para coincidir con 22-23 y 2022-23
            if re.search(rf"{curso}|\b{curso_formato}\b", archivo) and archivo.endswith(".docx"):
                archivos_encontrados.append((curso, os.path.join(carpeta, archivo)))
    return archivos_encontrados



def leer_contenido_docx(ruta_fichero):
    """Lee el texto de un archivo Word (.docx)."""
    try:
        doc = Document(ruta_fichero)
        texto = "\n".join([p.text for p in doc.paragraphs])
        return texto
    except Exception as e:
        print(f"Error al leer {ruta_fichero}: {e}")
        return None


def fill_description(doc, year_range, resultados):
    """Llena la descripción con los datos de eventos sostenibles por año."""
    
    # Calcular el número total de años y el total de actividades sostenibles
    num_years = len(resultados)
    if resultados:
        total = sum(resultados.values())
    else:
        total = 0
    
    if num_years > 0:
        average = total // num_years 
    else:
       average = 0

    # Construcción de la descripción
    description_text = (
        f"Events related to environment and sustainability hosted or organized by the University of Burgos "
        f"in the academic year {year_range}\n\n"
        f"Total number of sustainability/environment related events in:\n\n"
    )

    # Agregar cada año y su número de actividades
    for year, count in resultados.items():
        description_text += f"{year}: {count}.\n\n"

    description_text += (
        f"A total average per annum over the last {num_years} years is {average} events "
        f"(e.g. conferences, workshops, awareness raising, practical training, etc.).\n\n"
    )

    # Reemplazar el texto en el documento
    for para in doc.paragraphs:
        if "Description:" in para.text:
            para.text = f"Description:\n\n{description_text}"
            break




# API para buscar en los ficheros en funcion del años introducidos, que saque el numeor de actividades sostenibles.

  
def extraer_datos_llm(texto):
        if not texto:
            return None

        body = {
            "model": myModel,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You will receive a text containing a list of activities. "
                        "Identify which activities are related to environmental sustainability. "
                        "Count only those activities and return the number.\n\n"
                        "Return ONLY the number, with no extra text, explanation, or formatting."
                    )
                },
                {
                    "role": "user",
                    "content": texto
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

        #  Obtener respuesta limpia
        message_content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        #  Eliminar `</think>` si existe
        if "</think>" in message_content:
            message_content = message_content.split("</think>")[-1].strip()
        match = re.search(r"\d+", message_content)
        if match:
            return int(match.group())
        print(f"⚠️ No se encontró un número válido en la respuesta del modelo:\n{message_content}")
        return None

       

def procesar_documentos(rango_cursos, carpeta):
    """Procesa los documentos en el rango de cursos y extrae la información relevante."""
    cursos = extraer_anhos(rango_cursos)
    archivos = buscar_ficheros(cursos, carpeta)
    
    resultados = {}
    for curso, ruta in archivos:
        texto = leer_contenido_docx(ruta)
        num_actividades = extraer_datos_llm(texto)
        resultados[curso] = num_actividades

    return resultados
  



      

# Función que genera el informe
def generar(anho):
    print(anho)
    resultados = procesar_documentos(anho, carpeta)

    print(resultados)  

    """Genera el informe en memoria sin leer de Excel."""
    template_path = os.path.join(base_dir, 'informe_general.docx')
   
    if not os.path.exists(template_path):
        print(f"Error: No se encontró la plantilla {template_path}")
        return

    output_filename = "University_Country_6_8_Number_of_events_related_to_environment_and_sustainability"
    
    doc = Document(template_path)

    # Reemplazar texto en la plantilla
    for paragraph in doc.paragraphs:
        if  "[6] Education and Research (ED)" in paragraph.text:
            paragraph.text = f" [6] Education and Research (ED) \n\n [6.8] Number of Events Related to Sustainability"   
            break
   

    fill_description(doc,anho, resultados)

    report_dir = os.path.join(SRC_DIR, "generated_reports", "report_6_8", anho)
    os.makedirs(report_dir, exist_ok=True)  # Crea la carpeta si no existe

    output_docx_path = os.path.join(report_dir, f"{output_filename}.docx")
    output_pdf_path = os.path.join(report_dir, f"{output_filename}.pdf")

    doc.save(output_docx_path)

    try:
        convert(output_docx_path, output_pdf_path)
    except Exception as e:
        print(f"Error al convertir a PDF: {e}")

    print(f"Documento PDF generado en: {output_pdf_path}")

 


    

