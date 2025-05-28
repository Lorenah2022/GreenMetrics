# Importar librerías necesarias
import pandas as pd
import os
import sys
import re
from PyPDF2 import PdfReader

# Agregar el directorio raíz de tu proyecto al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def obtener_ruta_excel(tipo_estudio, ruta_data):
    """
    Obtiene la ruta completa al archivo Excel de datos de asignaturas
    basado en el tipo de estudio.

    Args:
        tipo_estudio (str): El tipo de estudio ('master', 'grado', 'ambos').
        ruta_data (str): La ruta al directorio que contiene los archivos de datos.

    Returns:
        str: La ruta completa al archivo Excel.

    Raises:
        ValueError: Si el tipo de estudio no es válido.
        FileNotFoundError: Si el archivo Excel esperado no se encuentra en la ruta especificada.
    """
    archivos = {
        'master': "datos_asignaturas_masteres.xlsx",
        'grado': "datos_asignaturas_grados.xlsx",
        'ambos': "datos_asignaturas_grados_masteres.xlsx"
    }
    archivo = archivos.get(tipo_estudio)
    if not archivo:
        raise ValueError("Tipo de estudio no válido.")

    ruta_excel = os.path.join(ruta_data, archivo)
    if not os.path.exists(ruta_excel):
        raise FileNotFoundError(f"No se encontró el archivo {ruta_excel}")
    
    return ruta_excel

def leer_pdf(ruta_pdf):
    """
    Lee el texto de cada página de un archivo PDF.

    Args:
        ruta_pdf (str): La ruta completa al archivo PDF.

    Returns:
        list[str]: Una lista de strings, donde cada string es el texto extraído
                   de una página del PDF. Las páginas sin texto son omitidas.
    """
    with open(ruta_pdf, "rb") as file:
        reader = PdfReader(file)
        return [page.extract_text() for page in reader.pages if page.extract_text()]

def extraer_info_pdf(pdf_text):
    """
    Extrae información específica (titulación, denominación, código y página con asteriscos)
    del texto de un PDF, asumiendo que la información clave está en la primera página.

    Args:
        pdf_text (list[str]): Una lista de strings, donde el primer string
                              contiene el texto de la primera página del PDF.

    Returns:
        tuple[str | None, str | None, str | None, int | None]: Una tupla que contiene:
            - titulacion (str | None): La titulación extraída, o None si no se encuentra.
            - denominacion (str | None): La denominación de la asignatura, o None si no se encuentra.
            - codigo (str | None): El código de la asignatura, o None si no se encuentra.
            - pagina_con_asteriscos (int | None): El número de la primera página que contiene
                                                 al menos un asterisco, o None si ninguna página lo contiene.
    """
    def extraer_patron(patron):
        """
        Función auxiliar para buscar un patrón regex en el texto de la primera página.
        """
        match = re.search(patron, pdf_text[0])
        return match.group().strip() if match else None

    denominacion = extraer_patron(r"(?<=1. Denominación de la asignatura:\n).*")
    titulacion = extraer_patron(r"(?<=Titulación\n).*")
    codigo = extraer_patron(r"(?<=Código\n).*")

    asteriscos = [text.count("*") for text in pdf_text if text]
    pagina_con_asteriscos = max((i + 1 for i, count in enumerate(asteriscos) if count > 0), default=None)

    return titulacion, denominacion, codigo, pagina_con_asteriscos

def procesar_fila(index, row, ruta_guias):
    """
    Procesa una única fila del DataFrame de asignaturas.

    Lee el nombre del archivo PDF de la fila, construye la ruta completa,
    lee el contenido del PDF y extrae la información relevante.

    Args:
        index (int): El índice de la fila en el DataFrame.
        row (pd.Series): La fila actual del DataFrame.
        ruta_guias (str): La ruta al directorio que contiene los archivos PDF de las guías.

    Returns:
        tuple[str | None, str | None, str | None, int | None]: Una tupla con la titulación,
            denominación, código y página con asteriscos extraídos del PDF.

    Raises:
        ValueError: Si el nombre del archivo PDF en la fila no es válido.
        FileNotFoundError: Si el archivo PDF especificado no existe.
        ValueError: Si no se pudo extraer texto del PDF.
    """
    nombre_pdf = row.get("nombre_archivo")
    
    if pd.isna(nombre_pdf) or not isinstance(nombre_pdf, str):
        raise ValueError(f"Nombre de PDF no válido en la fila {index}: {nombre_pdf}")

    ruta_pdf = os.path.join(ruta_guias, nombre_pdf)
    if not os.path.exists(ruta_pdf):
        raise FileNotFoundError(f"El archivo {ruta_pdf} no existe.")

    pdf_text = leer_pdf(ruta_pdf)
    if not pdf_text:
        raise ValueError(f"No se pudo extraer texto del PDF: {ruta_pdf}")

    return extraer_info_pdf(pdf_text)

def guardar_excel(asignaturas, tipo_estudio, ruta_data):
    """
    Guarda el DataFrame procesado en un nuevo archivo Excel.

    El nombre del archivo de salida depende del tipo de estudio.

    Args:
        asignaturas (pd.DataFrame): El DataFrame con los datos de asignaturas procesados.
        tipo_estudio (str): El tipo de estudio ('master', 'grado', 'ambos').
        ruta_data (str): La ruta al directorio donde se guardará el archivo de salida.

    Raises:
        ValueError: Si el tipo de estudio no es válido para determinar el nombre del archivo de salida.
    """
    rutas_salida = {
        'master': "datos_asignaturas_masteres_actualizado.xlsx",
        'grado': "datos_asignaturas_grados_actualizado.xlsx",
        'ambos': "enlaces_filtrados_grados_masteres_ubu.xlsx"
    }
    salida = rutas_salida.get(tipo_estudio)
    if not salida:
        raise ValueError("Tipo de estudio no válido para guardar archivo.")
    
    ruta_excel_actualizado = os.path.join(ruta_data, salida)
    asignaturas.to_excel(ruta_excel_actualizado, index=False)

def procesar_asignaturas(tipo_estudio):
    """
    Función principal para procesar las asignaturas.

    Carga el archivo Excel de entrada, inicializa nuevas columnas para la información
    a extraer, itera sobre cada fila, llama a `procesar_fila` para obtener los datos
    del PDF asociado y actualiza el DataFrame. Finalmente, guarda el DataFrame procesado.

    Args:
        tipo_estudio (str): El tipo de estudio ('master', 'grado', 'ambos').
    """
    ruta_data = os.path.join("sostenibilidad", "data")
    ruta_excel = obtener_ruta_excel(tipo_estudio, ruta_data)
    asignaturas = pd.read_excel(ruta_excel)

    asignaturas["titulacion"] = None
    asignaturas["denominacion"] = None
    asignaturas["codigo"] = None
    asignaturas["pagina_con_asteriscos"] = None

    ruta_guias = os.path.join(ruta_data, "guias")

    for index, row in asignaturas.iterrows():
        try:
            titulacion, denominacion, codigo, pagina_con_asteriscos = procesar_fila(index, row, ruta_guias)

            asignaturas.at[index, "titulacion"] = titulacion
            asignaturas.at[index, "denominacion"] = denominacion
            asignaturas.at[index, "codigo"] = codigo
            asignaturas.at[index, "pagina_con_asteriscos"] = pagina_con_asteriscos

        except Exception as e:
            print(f"Error en el archivo para fila {index}: {str(e)}")
            continue

    guardar_excel(asignaturas, tipo_estudio, ruta_data)

    
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso correcto: python script.py <tipo_estudio>")
        sys.exit(1)
    tipo_estudio = sys.argv[1]
    procesar_asignaturas(tipo_estudio)
