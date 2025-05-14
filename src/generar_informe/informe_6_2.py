import sqlite3
import os
import subprocess
import sys
from docx import Document
from docx2pdf import convert
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.oxml import OxmlElement
from docx.table import Table
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table


SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Agregar `src` al sys.path 
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ------------------ CONSULTA LA BASE DE DATOS ------------------
def verificar_tipos_programa(anio, db_path):
    """
    Verifica si existen datos para los tipos de programa 'grado' y 'master' en un año dado.

    Parámetros:
    - anio (int o str): El año que se desea verificar.
    - db_path (str): Ruta a la base de datos SQLite.

    Retorna:
    - bool: True si hay datos para ambos tipos, False en caso contrario.
    """
    # Verificar que la base de datos exista
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No se encontró la base de datos en {db_path}")

    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tipos = ['grado', 'master']
    resultado = {}
    try:
        for tipo in tipos:
            cursor.execute("""
                SELECT COUNT(*)
                FROM busqueda
                WHERE anho = ? AND tipo_programa = ?
            """, (anio, tipo))
            cantidad = cursor.fetchone()[0]
            resultado[tipo] = {
                'existe': cantidad > 0,
                'cantidad': cantidad
            }

        return resultado

    finally:
        conn.close()


# ------------------ AÑADE HIPERVINCULO ------------------
# Función que crea un hipervínculo, para el correcto funcionamiento de los enlaces
def add_hyperlink(paragraph, url, text):
    """Agrega un hipervínculo a un párrafo en un documento Word."""
    # Limpiar espacios no rompibles y espacios finales/iniciales
    url = url.replace("\u00A0", "").strip()

    # Crear la relación del hipervínculo en el documento
    part = paragraph._element
    rId = paragraph._parent.part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rId)

    # Crear el run del enlace
    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    # Color azul
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0000FF")  # Azul
    rPr.append(color)

    # Subrayado manual
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")  # Subrayado
    rPr.append(u)

    new_run.append(rPr)

    # Agregar el texto visible
    text_element = OxmlElement("w:t")
    text_element.text = text
    new_run.append(text_element)

    hyperlink.append(new_run)
    part.append(hyperlink)


# ------------------AÑADE LA DESCRIPCIÓN ------------------
def insert_table_after_paragraph(paragraph: Paragraph, doc: Document, rows: int, cols: int) -> Table:
    """Inserta una tabla justo después de un párrafo dado y con estilo visual."""
    # Insertar un párrafo nuevo justo después del original
    new_para_element = OxmlElement("w:p")
    paragraph._element.addnext(new_para_element)
    new_paragraph = Paragraph(new_para_element, paragraph._parent)

    # Insertar la tabla en ese nuevo párrafo
    table = doc.add_table(rows=rows, cols=cols)
    table.style = 'Table Grid'  # Asegura líneas visibles

    # Mover la tabla al lugar correcto
    tbl_element = table._element
    new_paragraph._element.addnext(tbl_element)

    return table

def fill_description(doc, anho, total):
    """Llena la sección de descripción con texto, tabla y texto adicional."""
    description_text = (
        "(Please describe the total of courses/subjects offered on your campus. "
        "The following is an example of the description. You can describe more related items if needed.)"
    )

    for para in doc.paragraphs:
        if "Description:" in para.text:
            # Reemplazar el texto con el texto de introducción
            para.clear()

            # Añadimos el texto "Description:" en negrita
            run_desc = para.add_run("Description:\n\n")
            run_desc.bold = True

            # Añadimos el texto descriptivo en cursiva
            run_italic = para.add_run(description_text)
            run_italic.italic = True

            # Insertar tabla justo después de este párrafo
            table = insert_table_after_paragraph(para, doc, 2, 2)

            # Llenar tabla
            table.cell(0, 0).text = "Year"
            table.cell(0, 1).text = "Total Courses"
            table.cell(1, 0).text = anho
            table.cell(1, 1).text = str(total)

            tbl_element = table._element
            new_para_element = OxmlElement("w:p")
            tbl_element.addnext(new_para_element)
            new_paragraph = Paragraph(new_para_element, para._parent)
            new_paragraph.add_run(f"Total number of courses offered in {anho} = {total} courses (not modules)")


            break

# ------------------ INSERTAR LOS ENLACES DESPUES DEL ENCABEZADO ------------------
def insert_paragraph_after(paragraph: Paragraph, text: str = "", style: str = None) -> Paragraph:
    """Inserta un nuevo párrafo justo después del párrafo dado."""
    new_p = OxmlElement("w:p")
    paragraph._element.addnext(new_p)
    new_paragraph = Paragraph(new_p, paragraph._parent)
    if text:
        new_paragraph.add_run(text)
    if style:
        new_paragraph.style = style
    return new_paragraph

   
# ------------------ GENERA EL INFORME ------------------
# Función que genera el informe
def generar_informe(total, anio):
    base_dir = os.path.dirname(__file__)  # Directorio base donde se encuentra el script
    template_path = os.path.join(base_dir, 'informe_general.docx')
    
    if not os.path.exists(template_path):
        print(f"❌ Error: No se encontró la plantilla en {template_path}")
        sys.exit(1)

    output_filename = "University_Country_6_2_Total_number_of_courses_or_modules_offered"
    
    doc = Document(template_path)

    # 1. Eliminar cualquier tabla vacía en el documento
    eliminar_tablas_vacias(doc)

    # 2. Reemplazar encabezado
    for paragraph in doc.paragraphs:
        if "[6] Education and Research (ED)" in paragraph.text:
            paragraph.text = "[6] Education and Research (ED)\n\n[6.2]  Total Number of Courses/Subjects Offered\n\n"          
            # Agregar el primer enlace debajo de la sección "[6.2]"
            p1 =insert_paragraph_after(paragraph)

            enlace1 = "https://www.ubu.es/grados-ordenados-por-ramas-de-conocimiento"
            add_hyperlink(p1, enlace1, enlace1)

            # Agregar el segundo enlace debajo del primero
            p2 = insert_paragraph_after(paragraph)

            enlace2 = "https://www.ubu.es/estudios/oferta-de-estudios/masteres-universitarios-oficiales"
            add_hyperlink(p2, enlace2, enlace2)
            
            break
        

    # 4. Añadir la descripción con tabla y datos
    fill_description(doc, anio, total)

    report_dir = os.path.join(SRC_DIR, "generated_reports", "report_6_2", anio)
    os.makedirs(report_dir, exist_ok=True)  # Crea la carpeta si no existe

    output_docx_path = os.path.join(report_dir, f"{output_filename}.docx")
    output_pdf_path = os.path.join(report_dir, f"{output_filename}.pdf")

    # 5. Guardar en Word
    doc.save(output_docx_path)

    # 6. Intentar conversión a PDF
    try:
        convert(output_docx_path, output_pdf_path)
        print(f"\nDocumento PDF generado en: {output_pdf_path}")
    except Exception as e:
        print(f"Error al convertir a PDF: {e}")

 
 

# ------------------ ELIMINA LAS TABLAS VACÍAS ------------------
def eliminar_tablas_vacias(doc):
    """Elimina las tablas vacías (sin contenido) del documento Word."""
    tablas_a_eliminar = []

    for table in doc.tables:
        vacia = True
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():  # Si hay contenido en alguna celda
                    vacia = False
                    break
            if not vacia:
                break
        if vacia:
            tablas_a_eliminar.append(table)

    for table in tablas_a_eliminar:
        tbl_element = table._element
        tbl_element.getparent().remove(tbl_element)

    print(f"Se eliminaron {len(tablas_a_eliminar)} tabla(s) vacía(s).")



# ------------------ FUNCIÓN PRINCIPAL ------------------
def generar(anio):
    db_path = 'instance/busqueda.db'
    max_intentos = 2  # uno antes y uno después de intentar descargar
    intento = 0

    while intento < max_intentos:
        resultados = verificar_tipos_programa(anio, db_path)

        if all(info['existe'] for info in resultados.values()):
            print("\nDatos completos. Generando informe...")
            # Extraer las cantidades para cada tipo
            total_grado = resultados['grado']['cantidad']
            total_master = resultados['master']['cantidad']
            total_general = total_grado + total_master  
            generar_informe(total_general, anio)
            break
        else:
            print("\nFaltan datos para alguno de los tipos de programa:\n")
            for tipo, info in resultados.items():
                if not info['existe']:
                    print(f"- No hay datos para '{tipo}'. Se procede a descargar las guías docentes.")

                    # Ejecutar scripts de descarga
                    ruta_grados = os.path.join(os.getcwd(), 'sostenibilidad', 'grados.py')
                    subprocess.run(['python3', ruta_grados, anio, tipo], check=True)

                    ruta_guias = os.path.join(os.getcwd(), 'sostenibilidad', 'guias_docentes.py')
                    subprocess.run(['python3', ruta_guias, anio, tipo], check=True)

        intento += 1

    else:
        print("\nAún faltan datos después de intentar descargar. Revisa manualmente.")




    

