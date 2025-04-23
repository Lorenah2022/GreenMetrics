import pandas as pd
from docx import Document
from docx.shared import Inches
import os
import sys
import importlib  # Importar dinámicamente el código de los informes
import tkinter as tk
from tkinter import ttk

def crear_word_documento():
    """
    Crea el documento Word utilizando la plantilla y rellena los datos generales.
    """
    base_dir = os.path.dirname(__file__)  # Directorio base donde se encuentra el script
    template_path = os.path.join(base_dir, 'modelo_base.docx')
    output_docx_path = os.path.join(base_dir, f"informe_general.docx")
    logo_path = os.path.join(base_dir, '../static/images/logo-UBU.jpg')

    if not os.path.exists(template_path):
        print(f"Error: No se encontró la plantilla {template_path}")
        sys.exit(1)

    university_name = "University of Burgos"
    country_name = "Spain"
    web_address = "https://www.ubu.es/"

    def cm_to_inches(cm):
        return cm / 2.54
    
    # Función para insertar el logo en lugar del texto "Put your university logo here"
    def replace_logo_placeholder(doc, logo_path):
        header = doc.sections[0].header  # Acceder a la cabecera de la primera sección

        for para in header.paragraphs:
            if "Put your university logo here" in para.text:
                inline_shapes = para._element.xpath(".//w:t[text()='Put your university logo here']")
                if inline_shapes:
                    inline_shapes[0].getparent().remove(inline_shapes[0])  # Elimina solo el texto del marcador
                    run = para.add_run()
                    run.add_picture(logo_path, width=Inches(cm_to_inches(3.06)), height=Inches(cm_to_inches(2.25)))  # Ajustado a centímetros
                break
    
    def fill_university_info(doc):
        for para in doc.paragraphs:
            if "University" in para.text:
                para.text = f"University: {university_name}"
            elif "Country" in para.text:
                para.text = f"Country: {country_name}"
            elif "Web Address" in para.text:
                para.text = f"Web Address: {web_address}"

    # Crear el documento con la plantilla
    doc = Document(template_path)
    replace_logo_placeholder(doc, logo_path)
    fill_university_info(doc)
    doc.save(output_docx_path)
    print(f"Documento Word creado en: {output_docx_path}")

def ejecutar_informe_especifico(anho, informe, excel):
    """
    Ejecuta el código específico de cada informe.
    """
    try:
         # Importa dinámicamente los ficheros py
        if  informe == "1_19":
            informe_1_19 = importlib.import_module('informe_1_19') 
            informe_1_19.generar()
        elif informe == "6_1":
            informe_6_1 = importlib.import_module('informe_6_1') 
            informe_6_1.generar(anho)  
        elif informe == "6_2":
            print("entra")
            informe_6_2 = importlib.import_module('informe_6_2') 
            informe_6_2.generar(anho) 
        elif informe == "6_4":
            informe_6_4 = importlib.import_module('informe_6_4') 
            informe_6_4.generar(excel) 
        elif informe == "6_7":
            informe_6_7 = importlib.import_module('informe_6_7')  
            informe_6_7.generar(anho)
        elif informe == "6_8":
            informe_6_8 = importlib.import_module('informe_6_8') 
            informe_6_8.generar(anho)
       
    except Exception as e:
        print(f"Error al cargar informe_{informe}.py: {e}")

def generar_informe(anho, informe,excel):
    """
    Función principal que coordina la creación del Word y la ejecución de los informes específicos.
    """
    # Primero, crear el documento de Word
    crear_word_documento()
    
    # Luego, ejecutar el informe específico
    ejecutar_informe_especifico(anho, informe,excel)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso correcto: python script.py <anho> <informe><excel>")
        sys.exit(1)
    
    anho = sys.argv[1]
    informe = sys.argv[2]
    excel = sys.argv[3]
    generar_informe(anho, informe, excel)
