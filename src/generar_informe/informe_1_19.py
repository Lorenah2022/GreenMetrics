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


# Ventanas emergentes
def ask_confirmation(record):
    """Muestra una ventana emergente personalizada para que el usuario confirme si desea agregar un registro."""
    def on_yes():
        nonlocal user_response
        user_response = True
        root.destroy()
    
    def on_no():
        nonlocal user_response
        user_response = False
        root.destroy()
    
    root = tk.Tk()
    root.title("Confirmación")
    root.geometry("600x450") 
    root.configure(bg="#f0f0f0")
    
    frame = tk.Frame(root, bg="#f0f0f0")
    frame.pack(padx=20, pady=20, fill="both", expand=True)
    
    label = tk.Label(frame, text="¿Deseas agregar este registro?", font=("Arial", 14, "bold"), bg="#006400", fg="white", pady=10)
    label.pack(pady=(0, 10))
    
    record_text = "\n".join([f"{key}: {value}" for key, value in record.items()])
    text_widget = tk.Text(frame, height=6, wrap="word", font=("Arial", 10))
    text_widget.insert("1.0", record_text)
    text_widget.config(state="disabled")
    text_widget.pack(pady=(0, 10), fill="both", expand=True)
    
    button_frame = tk.Frame(frame, bg="#f0f0f0")
    button_frame.pack(pady=10)
    
    style = ttk.Style()
    style.configure("TButton", font=("Arial", 12), padding=10)
    style.configure("Green.TButton", background="#008000", foreground="#008000")
    
    yes_button = ttk.Button(button_frame, text="Sí", command=on_yes, style="Green.TButton")
    yes_button.pack(side="left", padx=20)
    
    no_button = ttk.Button(button_frame, text="No", command=on_no, style="Green.TButton")
    no_button.pack(side="right", padx=20)
    
    user_response = None
    root.mainloop()
    return user_response

def ask_download():
    """Muestra una ventana emergente personalizada para que el usuario confirme si desea continuar descargando o generar el informe."""
    def on_yes():
        nonlocal user_response
        user_response = True
        root.destroy()
    
    def on_no():
        nonlocal user_response
        user_response = False
        root.destroy()
    
    root = tk.Tk()
    root.title("Confirmación")
    root.geometry("600x450") 
    root.configure(bg="#f0f0f0")
    
    frame = tk.Frame(root, bg="#f0f0f0")
    frame.pack(padx=20, pady=20, fill="both", expand=True)
    
    label = tk.Label(frame, text="¿Deseas seguir descargando más archivos? No se preocupe si se descargan ficheros no deseados, ya que más adelante se le pedirá que los confirme.", font=("Arial", 14, "bold"), bg="#006400", fg="white", pady=10)
    label.pack(pady=(0, 10))
    
    button_frame = tk.Frame(frame, bg="#f0f0f0")
    button_frame.pack(pady=10)
    
    style = ttk.Style()
    style.configure("TButton", font=("Arial", 12), padding=10)
    style.configure("Green.TButton", background="#008000", foreground="#008000")
    
    yes_button = ttk.Button(button_frame, text="Sí", command=on_yes, style="Green.TButton")
    yes_button.pack(side="left", padx=20)
    
    no_button = ttk.Button(button_frame, text="No", command=on_no, style="Green.TButton")
    no_button.pack(side="right", padx=20)
    
    user_response = None
    root.mainloop()
    return user_response
def ask_input(question):
    """Muestra una ventana emergente con un campo de texto para que el usuario ingrese un valor."""
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal

    response = simpledialog.askstring("Entrada", question)
    if response is None:  # Si el usuario presiona 'Cancel'
        print("Operación cancelada por el usuario.")
        sys.exit()  # Finaliza la ejecución del script
    
    return response

def ask_checkbox(question):
    """Muestra una ventana emergente con opciones de Sí o No para que el usuario decida si marcar la casilla."""
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal
    
    respuesta = messagebox.askyesno("Pregunta", question)
    if respuesta is None:  # Si el usuario presiona 'Cancel'
        print("Operación cancelada por el usuario.")
        sys.exit()  # Finaliza la ejecución del script
    
    return respuesta



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

def guardar_enlaces_en_excel(enlaces, archivo_excel):
        # Convertir enlaces en un DataFrame de pandas
        df = pd.DataFrame(enlaces, columns=["Link"])
        # Eliminar duplicados en la columna "Link"
        df = df.drop_duplicates(subset=["Link"], keep="first")
        # Guardar en un archivo Excel
        df.to_excel(archivo_excel, index=False)
        print(f"Archivo Excel guardado en: {archivo_excel}")
    
    

def extraer_licitaciones():
    rss_url = "https://contratacion.ubu.es/licitacion/rest/rss/expediente/1753"
    def obtener_rss(url):
        response = requests.get(url)
        return response.text if response.status_code == 200 else None
    
    def extraer_enlaces_rss(contenido_rss):
        root = ET.fromstring(contenido_rss)
        return [item.find("link").text for item in root.findall(".//item") if item.find("link") is not None]
    
    contenido_rss = obtener_rss(rss_url)
    if contenido_rss:
        enlaces = extraer_enlaces_rss(contenido_rss)
        if enlaces:
            # Ruta corregida
            excel_path = os.path.join(base_dir, "enlaces.xlsx")
            guardar_enlaces_en_excel(enlaces, excel_path)


def ejecutar_API(excel_path):
    load_dotenv()
    base_url = "http://127.0.0.1:1234"
    api_key = os.getenv("API_KEY")
    myModel = "lmstudio-community/DeepSeek-R1-Distill-Llama-8B-GGUF"

    
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
    
    # Obtener los enlaces desde el archivo Excel
    df = pd.read_excel(excel_path)
    enlaces = df['Link'].tolist()
    
    resultados = [extraer_datos_llm(limpiar_html(obtener_html(enlace)), enlace) for enlace in enlaces if obtener_html(enlace)]
    
    # Filtrar valores None antes de crear el DataFrame
    resultados_filtrados = [res for res in resultados if res is not None]

    
    # Eliminar duplicados en la columna "File"
    df = pd.DataFrame(resultados_filtrados, columns=["Building", "Contract", "Maintenance Type", "File", "Link"])
    df = df.drop_duplicates(subset=["File"], keep="first")  # Se queda con el primer registro de cada "File"

    if not df.empty:
        df.to_excel("enlaces.xlsx", index=False)
        print("\nArchivo Excel guardado sin duplicados en 'File'.")
    else:
        print("No se generaron datos válidos. No se creó el archivo Excel.")

def initialize_table(doc, headers):
    """Inicializa la tabla en el documento de Word con los encabezados."""
    for table in doc.tables:
        while len(table.columns) < len(headers):
            table.add_column(width=Inches(1.5))
        for i, header in enumerate(headers):
            table.cell(0, i).text = header
        return table  # Retornamos la primera tabla encontrada
    return None

def fill_table_with_confirmation(table, headers, data):
    """Llena la tabla solo con los datos confirmados por el usuario."""
    for row in data:
        record = dict(zip(headers, row))
        if not ask_confirmation(record):
            print("Registro omitido.")
            continue

        new_row = table.add_row()
        for col_idx, value in enumerate(row):
            new_row.cells[col_idx].text = str(value)
  
# Función que genera el informe
def generar_informe():
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, 'informe_general.docx')
    if not os.path.exists(template_path):
        print(f"Error: No se encontró la plantilla {template_path}")
        sys.exit(1)
    
    excel_data_path = "enlaces.xlsx"
    output_filename = "University_Country_1_19_Percentage_of_operation_and_maintenance_activities_of_building_in_one_year_pe"
    headers_custom = ["Building", "Contract", "Maintenance Type", "File", "Link"]
    output_docx_path = os.path.join(base_dir, f"{output_filename}.docx")
    output_pdf_path = os.path.join(base_dir, f"{output_filename}.pdf")
    
    def extract_data_from_excel(path):
        df = pd.read_excel(path)
        df = df[df['Building'].notna()]
        return headers_custom, df.values.tolist()
       
    
    doc = Document(template_path)
    # Reemplazar el texto específico en la plantilla
    replace_text_in_docx(doc, "[6] Education and Research (ED)", 
        "[1] Setting and Infrastructure (SI)\n\n"
        "[1.19] Percentage of operation and maintenance activities of building in one year period\n\n"
        "*Min. at least five maintenance classification for each building"
    )
    headers, data_from_excel = extract_data_from_excel(excel_data_path)
    
    table = initialize_table(doc, headers)
    if table:
        fill_table_with_confirmation(table, headers, data_from_excel)
    
    doc.save(output_docx_path)
    # Eliminar "Description: " si aparece en el documento
    remove_text_from_docx(doc, "Description:")

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

    # Llenar el campo "Expediente"
    campo_expediente = driver.find_element(By.ID, "expediente")  # Usar ID correcto
    expediente = ask_input("El nombre del expediente (Ej. UBU/2023/0018 )")
    if expediente:
        campo_expediente.send_keys(expediente)


    # Llenar el campo "Objeto"
    campo_objeto = driver.find_element(By.ID, "ObjContrato")  # Ajusta el NAME real
    objeto = ask_input("Introduzca el Objeto: ")
    if objeto:
        campo_objeto.send_keys(objeto)


    # Seleccionar "Modalidad" en el desplegable
    select_modalidad = Select(driver.find_element(By.ID, "modContrato2"))  # Ajusta el NAME real
    opciones_modalidad = [option.text for option in select_modalidad.options if option.text.strip() != ""]
    opciones_numeradas = "\n".join([f"{i+1}. {opcion}" for i, opcion in enumerate(opciones_modalidad)])
    modalidad_seleccionada_numero = ask_input(f"Elige una modalidad (número): \n{opciones_numeradas}\n")
    if modalidad_seleccionada_numero and modalidad_seleccionada_numero.isdigit():
        modalidad_seleccionada_numero = int(modalidad_seleccionada_numero)
        if 1 <= modalidad_seleccionada_numero <= len(opciones_modalidad):
            modalidad_seleccionada = opciones_modalidad[modalidad_seleccionada_numero - 1]
            select_modalidad.select_by_visible_text(modalidad_seleccionada)
        else:
            print("Por favor, introduce un número válido.")
    else:
        print("Se omite")    
        
    # Seleccionar "Procedimiento"
    select_procedimiento = Select(driver.find_element(By.ID, "tipoPro"))
    opciones_procedimiento = [option.text for option in select_procedimiento.options if option.text.strip() != ""]
    opciones_numeradas = "\n".join([f"{i+1}. {opcion}" for i, opcion in enumerate(opciones_procedimiento)])
    procedimiento_seleccionada_numero = ask_input(f"Elige un procedimiento (número): \n{opciones_numeradas}\n")
    if procedimiento_seleccionada_numero and procedimiento_seleccionada_numero.isdigit():
        procedimiento_seleccionada_numero = int(procedimiento_seleccionada_numero)
        if 1 <= procedimiento_seleccionada_numero <= len(opciones_procedimiento):
            procedimiento_seleccionado = opciones_procedimiento[procedimiento_seleccionada_numero - 1]
            select_procedimiento.select_by_visible_text(procedimiento_seleccionado)
        else:
            print("Por favor, introduce un número válido.")
    else:
        print("Se omite")  
        
    # Seleccionar "Forma de Adjudicación"
    select_adjudicacion = Select(driver.find_element(By.ID, "tipoReso"))  
    # Obtener las opciones del desplegable de Modalidad
    opciones_adjudicacion = [option.text for option in select_adjudicacion.options if option.text.strip() != ""]
    # Mostrar las opciones numeradas para el usuario
    opciones_numeradas = "\n".join([f"{i+1}. {opcion}" for i, opcion in enumerate(opciones_adjudicacion)])
    # Solicitar al usuario que ingrese un número
    adjudicacion_seleccionada_numero = ask_input(f"Elige una forma de adjudicación (número): \n{opciones_numeradas}\n")
    # Validar si la entrada es un número válido y está dentro del rango de opciones
    if adjudicacion_seleccionada_numero and adjudicacion_seleccionada_numero.isdigit()  :
        adjudicacion_seleccionada_numero = int(adjudicacion_seleccionada_numero)
        if 1 <= adjudicacion_seleccionada_numero <= len(opciones_adjudicacion):
            adjudicacion_seleccionado = opciones_adjudicacion[adjudicacion_seleccionada_numero - 1]  # Restar 1 para la indexación en Python
            select_adjudicacion.select_by_visible_text(adjudicacion_seleccionado)
        else:
            print("Número de modalidad no válido.")
    else:
        print("Se omite")


    # Rellenar Importe Desde y Hasta
    campo_importe_desde = driver.find_element(By.ID, "importesDe")  
    fecha_importe_desde = ask_input("Ingresa el importe (desde):")
    if fecha_importe_desde:
        campo_importe_desde.send_keys(fecha_importe_desde)
    campo_importe_hasta = driver.find_element(By.ID, "importesHa")  
    fecha_importe_hasta = ask_input("Ingresa el importe (hasta):")
    if fecha_importe_hasta:
        campo_importe_hasta.send_keys(fecha_importe_hasta)
        
    # Fechas de Fin de Licitación
    campo_fecha_desde = driver.find_element(By.ID, "fechaDe")  
    fecha_desde = ask_input("Ingresa la fecha desde (formato DD/MM/AAAA):")
    if fecha_desde:
        campo_fecha_desde.send_keys(fecha_desde)

    campo_fecha_hasta = driver.find_element(By.ID, "fechaHa")  
    fecha_hasta = ask_input("Ingresa la fecha hasta (formato DD/MM/AAAA):")
    if fecha_hasta:
        campo_fecha_hasta.send_keys(fecha_hasta)


    # Seleccionar "Sistema de Contratación"
    select_sistema = Select(driver.find_element(By.ID, "tipoSisCont"))  
    # Obtener las opciones del desplegable de Sistema de contratación
    opciones_sistema = [option.text for option in select_sistema.options if option.text.strip() != ""]
    # Mostrar las opciones numeradas para el usuario
    opciones_numeradas = "\n".join([f"{i+1}. {opcion}" for i, opcion in enumerate(opciones_sistema)])
    # Solicitar al usuario que ingrese un número
    sistema_seleccionada_numero = ask_input(f"Elige un sistema de contratación (número): \n{opciones_numeradas}\n")
    # Validar si la entrada es un número válido y está dentro del rango de opciones
    if sistema_seleccionada_numero and sistema_seleccionada_numero.isdigit() :
        sistema_seleccionada_numero = int(sistema_seleccionada_numero)
        if 1 <= sistema_seleccionada_numero <= len(opciones_sistema):
            sistema_seleccionado = opciones_sistema[sistema_seleccionada_numero - 1]  # Restar 1 para la indexación en Python
            select_sistema.select_by_visible_text(sistema_seleccionado)
        else:
            print("Número de modalidad no válido.")
    else:
        print("Se omite")


    # Seleccionar "Fase Expediente"
    select_fase = Select(driver.find_element(By.ID, "faseExpt"))  
    # Obtener las opciones del desplegable de Expediente
    opciones_fase = [option.text for option in select_fase.options if option.text.strip() != ""]
    # Mostrar las opciones numeradas para el usuario
    opciones_numeradas = "\n".join([f"{i+1}. {opcion}" for i, opcion in enumerate(opciones_fase)])
    # Solicitar al usuario que ingrese un número
    fase_seleccionada_numero = ask_input(f"Elige un sistema de contratación (número): \n{opciones_numeradas}\n")
    # Validar si la entrada es un número válido y está dentro del rango de opciones
    if fase_seleccionada_numero and fase_seleccionada_numero.isdigit() :
        fase_seleccionada_numero = int(fase_seleccionada_numero)
        if 1 <= fase_seleccionada_numero <= len(opciones_fase):
            fase_seleccionado = opciones_fase[fase_seleccionada_numero - 1]  # Restar 1 para la indexación en Python
            select_fase.select_by_visible_text(fase_seleccionado)
        else:
            print("Número de modalidad no válido.")
    else:
        print("Se omite")

    # Marcar la casilla "Ver expedientes de organismos dependientes"
    casilla_organismos = driver.find_element(By.NAME, "descendientes")  # Ajusta el NAME real
    seleccion_organismos = ask_checkbox("¿Deseas ver expedientes de organismos dependientes?")
    if seleccion_organismos:
        if not casilla_organismos.is_selected():
            casilla_organismos.click()  # Marcar la casilla si no está seleccionada

    # Hacer clic en el botón de búsqueda
    boton_buscar = driver.find_element(By.NAME, "busquedaFormAvanz")  # Ajusta el NAME real
    boton_buscar.click()

    # Encuentra todas las filas de la tabla con la clase 'resultados'
    resultados = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".resultados tbody tr")))

    # Verifica si hay resultados
    if len(resultados) == 0:
        print("No se encontraron resultados.")
    else:
        for resultado in resultados:
            columnas = resultado.find_elements(By.TAG_NAME, "td")  # Extraer columnas de cada fila
            datos = [col.text.strip() for col in columnas]  # Obtener el texto de cada celda
            # Extraer el enlace de la primera columna (suponiendo que está en la primera columna)
            enlace = None
            enlace_elemento = resultado.find_element(By.CSS_SELECTOR, "a")
            if enlace_elemento:
                enlace = enlace_elemento.get_attribute("href")  # Obtener el atributo href del enlace
                # Guardar los enlaces en un archivo Excel
                excel_path = os.path.join(base_dir, "enlaces.xlsx")
                guardar_enlaces_en_excel([enlace], excel_path)

                print(enlace)  # Imprimir los resultados con el enlace

    # Cerrar el navegador cuando termine
    driver.quit()


# Función que llama en el orden correcto al resto de funciones.
def generar(metodo):
    
    if metodo == "RSS":
        extraer_licitaciones()
        continuar_o_generar()
        

    
    elif metodo == "BUSCAR":
        buscar()
        continuar_o_generar()



def continuar_o_generar():
    respuesta = ask_download()
    if respuesta:  # Si la respuesta es 'Sí', continuar descargando más
        messagebox.showinfo("Continuar", "Selecciona nuevamente un método para descargar más archivos.")
        metodo_selector()  # Vuelve a mostrar el selector de método
    else:  # Si la respuesta es 'No', generar el informe
        
        ejecutar_API(os.path.join(base_dir, "enlaces.xlsx"))
        generar_informe()
        messagebox.showinfo("Informe", "Informe generado con éxito.")


def metodo_selector():
    metodo = crear_gui()  # Aquí se obtiene el método seleccionado desde la interfaz gráfica
    if metodo:
        generar(metodo)
    else:
        messagebox.showwarning("Advertencia", "Por favor, selecciona un método para proceder.")

def crear_gui():
    global base_dir, metodo_var
    
    base_dir = os.getcwd()  # Directorio base, ajusta según sea necesario
    window = tk.Tk()
    window.title("Gestión de Descargas e Informes")

    # Variable para seleccionar el método
    metodo_var = tk.StringVar()

    # Selector de métodos
    tk.Label(window, text="Selecciona el método de descarga:").pack(pady=10)
    tk.Radiobutton(window, text="RSS", variable=metodo_var, value="RSS").pack()
    tk.Radiobutton(window, text="BUSCAR", variable=metodo_var, value="BUSCAR").pack()

    # Función para que el botón cierre la ventana y devuelva el valor seleccionado
    def on_select():
        window.destroy()

    # Botón para iniciar el proceso
    tk.Button(window, text="Iniciar Descarga y Selección de Método", command=on_select).pack(pady=10)

    # Iniciar la interfaz gráfica
    window.mainloop()

    # Devolver el valor del método seleccionado por el usuario
    return metodo_var.get()


    

