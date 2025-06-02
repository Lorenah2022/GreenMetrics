from docx import Document, Paragraph, Table
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def add_hyperlink(paragraph, url, text):
    """
    Agrega un hipervínculo a un párrafo en un documento Word.

    Parámetros:
    - paragraph (Paragraph): El objeto Paragraph al que se añadirá el hipervínculo.
    - url (str): La URL del hipervínculo.
    - text (str): El texto visible del hipervínculo.
    """
    # Limpiar espacios no rompibles y espacios finales/iniciales
    url = url.replace("\u00A0", "").strip()

    # Crear la relación del hipervínculo en el documento
    part = paragraph._element
    rid = paragraph._parent.part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rid)

    # Crear el run del enlace
    new_run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")

    # Color azul
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0000FF")  # Azul
    rpr.append(color)

    # Subrayado manual
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")  # Subrayado
    rpr.append(u)

    new_run.append(rpr)

    # Agregar el texto visible
    text_element = OxmlElement("w:t")
    text_element.text = text
    new_run.append(text_element)

    hyperlink.append(new_run)
    part.append(hyperlink)

def insert_table_after_paragraph(paragraph: Paragraph, doc: Document, rows: int, cols: int) -> Table:
    """
    Inserta una tabla justo después de un párrafo dado y con estilo visual.

    Parámetros:
    - paragraph (Paragraph): El párrafo después del cual se insertará la tabla.
    - doc (Document): El objeto Document de python-docx.
    - rows (int): Número de filas para la nueva tabla.
    - cols (int): Número de columnas para la nueva tabla.

    Retorna:
    - Table: El objeto Table recién creado.
    """
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



 

def eliminar_tablas_vacias(doc):
    """
    Elimina las tablas vacías (sin contenido) del documento Word.

    Parámetros:
    - doc (Document): El objeto Document de python-docx.
    """
    for table in doc.tables:
        if es_tabla_vacia(table):
            eliminar_tabla(table)

def es_tabla_vacia(table):
    """
    Verifica si una tabla no contiene texto en ninguna de sus celdas.

    Parámetros:
    - table (Table): El objeto Table de python-docx.

    Retorna:
    - bool: True si la tabla está vacía, False en caso contrario.
    """
    for row in table.rows:
        if fila_contiene_texto(row):
            return False
    return True



def fila_contiene_texto(row):
    """
    Verifica si alguna celda de una fila contiene texto.

    Parámetros:
    - row: El objeto Row de python-docx.

    Retorna:
    - bool: True si la fila contiene texto, False en caso contrario.
    """
    return any(cell.text.strip() for cell in row.cells)


def eliminar_tabla(table):
    """
    Elimina una tabla del documento.

    Parámetros:
    - table (Table): El objeto Table de python-docx a eliminar.
    """
    tbl_element = table._element
    tbl_element.getparent().remove(tbl_element)

