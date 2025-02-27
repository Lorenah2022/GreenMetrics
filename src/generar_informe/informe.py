import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
from fpdf import FPDF
import os


def ask_confirmation(question):
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

def ask_input(question):
    """Muestra una ventana emergente con un campo de texto para que el usuario ingrese un valor."""
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal

    response = simpledialog.askstring("Entrada", question)
    return response

def ask_checkbox(question):
    """Muestra una ventana emergente con opciones de Sí o No para que el usuario decida si marcar la casilla."""
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal
    
    respuesta = messagebox.askyesno("Pregunta", question)
    return respuesta


# Iniciar el navegador
driver = webdriver.Chrome()
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
# Obtener las opciones del desplegable de Modalidad
opciones_modalidad = [option.text for option in select_modalidad.options if option.text.strip() != ""]
# Mostrar las opciones de Modalidad usando una ventana emergente
modalidad_seleccionada = ask_input("Elige una modalidad: \n" + "\n".join(opciones_modalidad))

if modalidad_seleccionada in opciones_modalidad:
    select_modalidad.select_by_visible_text(modalidad_seleccionada)
else:
    print("No se seleccionó Modalidad o la opción no es válida, continuando...")


# Seleccionar "Procedimiento"
select_procedimiento = Select(driver.find_element(By.ID, "tipoPro"))  

# Obtener las opciones del desplegable de Modalidad
opciones_procedimiento = [option.text for option in select_procedimiento.options if option.text.strip() != ""]
procedimiento_seleccionado = ask_input("Elige un Procedimiento: \n" + "\n".join(opciones_procedimiento))

if procedimiento_seleccionado in opciones_procedimiento:
    select_procedimiento.select_by_visible_text(procedimiento_seleccionado)
else:
    print("No se seleccionó Procedimiento o la opción no es válida, continuando...")



# Seleccionar "Forma de Adjudicación"
select_adjudicacion = Select(driver.find_element(By.ID, "tipoReso"))  

# Obtener las opciones del desplegable de Modalidad
opciones_adjudicacion = [option.text for option in select_adjudicacion.options if option.text.strip() != ""]
adjudicacion_seleccionado = ask_input("Elige una forma de adjudicación: \n" + "\n".join(opciones_adjudicacion))

if adjudicacion_seleccionado in opciones_adjudicacion:
    select_adjudicacion.select_by_visible_text(adjudicacion_seleccionado)
else:
    print("No se seleccionó Procedimiento o la opción no es válida, continuando...")



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

sistema_seleccionado = ask_input("Elige un sistema de contratación: \n" + "\n".join(opciones_sistema))

if sistema_seleccionado in opciones_sistema:
    select_sistema.select_by_visible_text(sistema_seleccionado)
else:
    print("No se seleccionó Procedimiento o la opción no es válida, continuando...")


# Seleccionar "Fase Expediente"
select_fase = Select(driver.find_element(By.ID, "faseExpt"))  
# Obtener las opciones del desplegable de Expediente
opciones_fase = [option.text for option in select_fase.options if option.text.strip() != ""]
fase_seleccionado = ask_input("Elige una fase de expediente: \n" + "\n".join(opciones_fase))

if fase_seleccionado in opciones_fase:
    select_fase.select_by_visible_text(fase_seleccionado)
else:
    print("No se seleccionó Procedimiento o la opción no es válida, continuando...")




# Marcar la casilla "Ver expedientes de organismos dependientes"
casilla_organismos = driver.find_element(By.NAME, "descendientes")  # Ajusta el NAME real
seleccion_organismos = ask_checkbox("¿Deseas ver expedientes de organismos dependientes?")
if seleccion_organismos:
    if not casilla_organismos.is_selected():
        casilla_organismos.click()  # Marcar la casilla si no está seleccionada

# Hacer clic en el botón de búsqueda
boton_buscar = driver.find_element(By.NAME, "busquedaFormAvanz")  # Ajusta el NAME real
boton_buscar.click()

# Extraer los resultados de la tabla

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
        


base_dir = os.path.dirname(__file__)


# Encuentra todas las filas de la tabla con la clase 'resultados'
resultados = driver.find_elements(By.CSS_SELECTOR, ".resultados tbody tr")

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
            pdf_path2 = os.path.join(base_dir, "enlaces_busqueda.pdf")
            crear_pdf_con_enlaces([enlace],pdf_path2)

            
        print(enlace)  # Imprimir los resultados con el enlace

       
       

# Cerrar el navegador cuando termine
driver.quit()