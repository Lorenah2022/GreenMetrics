import pandas as pd
from docx import Document
from docx.shared import Inches
from docx2pdf import convert
import os

# Rutas de los archivos
base_dir = os.path.dirname(__file__)  # Directorio base donde se encuentra el script
template_path =  os.path.join(base_dir, 'modelo_base.docx')
output_docx_path =  os.path.join(base_dir, 'output_filled.docx')
output_pdf_path =  os.path.join(base_dir, 'output_filled.pdf')
excel_path = os.path.join('generar_informe', 'courses.xlsx')
logo_path = os.path.join(base_dir, '../static/images/logo-UBU.jpg') 

# Datos de la Universidad de Burgos
university_name = "University of Burgos"
country_name = "Spain"
web_address = "https://www.ubu.es/"

# Leer los datos del archivo Excel
df = pd.read_excel(excel_path)

# Crear una copia del documento para modificarlo
doc = Document(template_path)

# Es necesaria la conversión de centimetros a pulgadas ya que la biblioteca "pyhton-docx" usa pulgadas.
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
        
# Función para rellenar la información de la universidad
def fill_university_info(doc, university_name, country_name, web_address):
    for para in doc.paragraphs:
        if "University" in para.text:
            para.text = f"University : {university_name}"
        elif "Country" in para.text:
            para.text = f"Country : {country_name}"
        elif "Web Address" in para.text:
            para.text = f"Web Address : {web_address}"

# Llamar a la función para reemplazar el marcador del logo
replace_logo_placeholder(doc, logo_path)

# Llamar a la función para rellenar la información de la universidad
fill_university_info(doc, university_name, country_name, web_address)

# Guardar el documento modificado
doc.save(output_docx_path)

# Convertir el documento a PDF
convert(output_docx_path, output_pdf_path)

print(f"Documento PDF generado en: {output_pdf_path}")
