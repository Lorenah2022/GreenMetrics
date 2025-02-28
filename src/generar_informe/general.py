import pandas as pd
from docx import Document
from docx.shared import Inches
import os
import sys
import importlib  # Importar dinámicamente el código de los informes
import tkinter as tk
from tkinter import ttk

def pedir_tipo_busqueda():
    """Muestra una ventana emergente personalizada para que el usuario confirme si desea realizar la búsqueda mediante RSS."""

    def on_yes():
        nonlocal user_response
        user_response = "RSS"  # Asignar respuesta positiva
        root.destroy()  # Cerrar la ventana

    def on_no():
        nonlocal user_response
        user_response = "BUSCAR"  # Asignar respuesta negativa
        root.destroy()  # Cerrar la ventana

    root = tk.Tk()  # Crear la ventana
    root.title("Confirmación")  # Título de la ventana
    root.geometry("400x250")  # Tamaño de la ventana
    root.configure(bg="#f0f0f0")  # Configuración del fondo
    
    # Frame principal
    frame = tk.Frame(root, bg="#f0f0f0")
    frame.pack(padx=20, pady=20, fill="both", expand=True)
    
    # Etiqueta con el texto de la pregunta
    label = tk.Label(frame, text="¿Desea realizar la búsqueda mediante RSS?", font=("Arial", 14, "bold"), bg="#006400", fg="white", pady=10)
    label.pack(pady=(0, 10))
    
    # Botones de respuesta
    button_frame = tk.Frame(frame, bg="#f0f0f0")
    button_frame.pack(pady=10)
    
    # Estilo de los botones
    style = ttk.Style()
    style.configure("TButton", font=("Arial", 12), padding=10)
    style.configure("Green.TButton", background="#008000", foreground="#008000")
    
    # Botón "Sí"
    yes_button = ttk.Button(button_frame, text="Sí", command=on_yes, style="Green.TButton")
    yes_button.pack(side="left", padx=20)
    
    # Botón "No"
    no_button = ttk.Button(button_frame, text="No", command=on_no, style="Green.TButton")
    no_button.pack(side="right", padx=20)
    
    user_response = None  # Variable para almacenar la respuesta del usuario
    
    # Ejecutar el ciclo de eventos de Tkinter
    root.mainloop()
    
    return user_response

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

def ejecutar_informe_especifico(anho, informe):
    """
    Ejecuta el código específico de cada informe.
    """
    try:
        if informe == "6_1":
            informe_6_1 = importlib.import_module('informe_6_1')  # Importa dinámicamente el archivo informe_6_1.py
            informe_6_1.generar_informe(anho)  # Ejecuta la función específica de informe_6_1
        if informe == "1_19":
            metodo = pedir_tipo_busqueda()
            informe_1_19 = importlib.import_module('informe_1_19')  # Importa dinámicamente el archivo informe_6_1.py
            informe_1_19.generar(metodo)
        else:
            informe_X = importlib.import_module(f'informe_{informe}')  # Importa el informe genérico, ejemplo: informe_X.py
            informe_X.generar_descripcion(anho)  # Ejecuta la función específica del informe
    except Exception as e:
        print(f"Error al cargar informe_{informe}.py: {e}")

def generar_informe(anho, informe):
    """
    Función principal que coordina la creación del Word y la ejecución de los informes específicos.
    """
    # Primero, crear el documento de Word
    crear_word_documento()
    
    # Luego, ejecutar el informe específico
    ejecutar_informe_especifico(anho, informe)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso correcto: python script.py <anho> <informe>")
        sys.exit(1)
    
    anho = sys.argv[1]
    informe = sys.argv[2]
    generar_informe(anho, informe)
