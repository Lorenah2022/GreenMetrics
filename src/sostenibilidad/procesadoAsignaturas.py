# Importar librerías necesarias
import pandas as pd
import os
import re
from PyPDF2 import PdfReader

ruta_data = os.path.join("sostenibilidad", "data")

# Cargar el archivo Excel desde la carpeta "data"
ruta_excel = os.path.join(ruta_data, "datos_asignaturas_masteres.xlsx")

# Verificar si el archivo Excel existe
if not os.path.exists(ruta_excel):
    raise FileNotFoundError(f"No se encontró el archivo {ruta_excel}")

# Cargar el archivo de asignaturas
asignaturas = pd.read_excel(ruta_excel)

# Agregar nuevas columnas para almacenar la información extraída
asignaturas["titulacion"] = None
asignaturas["denominacion"] = None
asignaturas["codigo"] = None
asignaturas["pagina_con_asteriscos"] = None

# Definir la ruta donde se encuentran los PDFs
ruta_guias = os.path.join(ruta_data, "guias")

# Iterar sobre cada fila del DataFrame
for index in range(len(asignaturas)):
    error_occurred = False  # Bandera para controlar errores

    try:
        # Obtener el nombre del archivo PDF desde la columna correspondiente
        nombre_pdf = asignaturas.iloc[index, 4]
        ruta_pdf = os.path.join(ruta_guias, nombre_pdf)

        # Verificar si el archivo PDF existe antes de intentar leerlo
        if not os.path.exists(ruta_pdf):
            raise FileNotFoundError(f"El archivo {ruta_pdf} no existe.")

        # Extraer el texto del PDF
        with open(ruta_pdf, "rb") as file:
            reader = PdfReader(file)
            pdf_text = [page.extract_text() for page in reader.pages]

        # Extraer la denominación de la asignatura
        denominacion = re.search(r"(?<=1. Denominación de la asignatura:\n).*", pdf_text[0])
        if denominacion:
            denominacion = denominacion.group().strip()  # Limpiar espacios en blanco

        # Extraer la titulación
        titulacion = re.search(r"(?<=Titulación\n).*", pdf_text[0])
        if titulacion:
            titulacion = titulacion.group().strip()

        # Extraer el código de la asignatura
        codigo = re.search(r"(?<=Código\n).*", pdf_text[0])
        if codigo:
            codigo = codigo.group().strip()

        # Contar asteriscos en las páginas y determinar la última página con asteriscos
        asteriscos = [text.count("*") for text in pdf_text if text]  # Evitar errores con páginas vacías
        if any(count > 0 for count in asteriscos):
            pagina_con_asteriscos = max(i + 1 for i, count in enumerate(asteriscos) if count > 0)  # Números de página 1-based
        else:
            pagina_con_asteriscos = None  # Si no hay asteriscos, devolver None

        # Guardar los resultados en el DataFrame
        asignaturas.at[index, "titulacion"] = titulacion
        asignaturas.at[index, "denominacion"] = denominacion
        asignaturas.at[index, "codigo"] = codigo
        asignaturas.at[index, "pagina_con_asteriscos"] = pagina_con_asteriscos

    except Exception as e:
        # Si ocurre un error, mostrar mensaje y continuar con la siguiente fila
        print(f"Error en el archivo: {ruta_pdf} - {str(e)}")
        error_occurred = True

    # Si hubo un error, saltar a la siguiente iteración
    if error_occurred:
        continue

# Guardar el DataFrame actualizado en la carpeta "data"
ruta_excel_actualizado = os.path.join(ruta_data, "datos_asignaturas_masteres_actualizado.xlsx")
asignaturas.to_excel(ruta_excel_actualizado, index=False)