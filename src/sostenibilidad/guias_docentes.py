# Importar librerías necesarias
import os
import sys
from flask import app
import pandas as pd
import requests
import time
from sqlalchemy.exc import IntegrityError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from app import app, Busqueda, db  


# Agregar el directorio raíz de tu proyecto al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



def cargar_datos(tipo_estudio, ruta_data):
    """
    Carga los datos de enlaces de grados o másteres desde archivos Excel.

    Args:
        tipo_estudio (str): El tipo de estudio a cargar ('grado', 'master', o 'ambos').
        ruta_data (str): La ruta al directorio que contiene los archivos Excel.

    Returns:
        pandas.DataFrame: Un DataFrame que contiene los enlaces cargados.

    Raises:
        ValueError: Si el tipo de estudio no es válido.
    """
    
    rutas = {
        'grado': "enlaces_filtrados_grados_ubu.xlsx",
        'master': "enlaces_filtrados_masteres_ubu.xlsx"
    }

    if tipo_estudio in rutas:
        ruta_excel = os.path.join(ruta_data, rutas[tipo_estudio])
        df = pd.read_excel(ruta_excel)
        df['tipo_programa'] = tipo_estudio
        return df

    elif tipo_estudio == 'ambos':
        grados = cargar_datos('grado', ruta_data)
        masteres = cargar_datos('master', ruta_data)
        return pd.concat([grados, masteres], ignore_index=True)

    raise ValueError("Tipo de estudio no válido.")

def configurar_driver():
    """
    Configura y devuelve una instancia del driver de Chrome en modo headless.

    Returns:
        webdriver.Chrome: Una instancia del driver de Selenium Chrome.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=chrome_options)

def obtener_enlaces_guias(driver, url):
    """
    Navega a una URL y extrae los enlaces a las guías docentes.

    Args:
        driver (webdriver.Chrome): La instancia del driver de Selenium.
        url (str): La URL de la página donde buscar los enlaces.

    Returns:
        list: Una lista de elementos web (enlaces) encontrados.
    """
    driver.get(url)
    time.sleep(5)
    return driver.find_elements(By.XPATH, "//a[contains(@href, 'asignatura')]")

def descargar_guia(url_asignatura, anho2, modalidad, ruta_guias):
    """
    Descarga un archivo PDF de guía docente desde una URL.

    Args:
        url_asignatura (str): La URL de la página de la asignatura.
        anho2 (str): El año académico (formato 'YYYY').
        modalidad (str): La modalidad de estudio ('online' o 'presencial').
        ruta_guias (str): La ruta al directorio donde guardar el archivo PDF.

    Returns:
        tuple: Una tupla que contiene el código de la asignatura y el nombre del archivo descargado,
               o (None, None) si ocurre un error.
    """
    codigo = url_asignatura.split("asignatura=")[-1].split("&")[0]
    url_descarga = f"https://ubuvirtual.ubu.es/mod/guiadocente/get_guiadocente.php?asignatura={codigo}&cursoacademico={anho2}"
    nombre_archivo = f"{codigo}_{modalidad}.pdf"
    ruta_archivo = os.path.join(ruta_guias, nombre_archivo)

    try:
        response = requests.get(url_descarga)
        response.raise_for_status()
        with open(ruta_archivo, "wb") as f:
            f.write(response.content)
        print(f"Guía descargada: {nombre_archivo}")
        return codigo, nombre_archivo
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar la guía {url_asignatura}: {e}")
        return None, None

def registrar_en_bd(anho, codigo, nombre, modalidad, tipo_programa):
    """
    Registra la información de una guía docente en la base de datos.

    Verifica si el registro ya existe antes de añadir uno nuevo.

    Args:
        anho (str): El año académico (ej. "2023-2024").
        codigo (str): El código de la asignatura.
        nombre (str): El nombre del archivo de la guía descargada.
        modalidad (str): La modalidad de estudio ('online' o 'presencial').
        tipo_programa (str): El tipo de programa ('grado' o 'master').
    """
    with app.app_context():
        existente = Busqueda.query.filter_by(anho=anho, codigo_asignatura=codigo, modalidad=modalidad).first()
        if not existente:
            nuevo = Busqueda(
                anho=anho,
                tipo_programa=tipo_programa,
                codigo_asignatura=codigo,
                nombre_archivo=nombre,
                modalidad=modalidad
            )
            db.session.add(nuevo)
            db.session.commit()
        else:
            print(f"Registro ya existe: {codigo} ({modalidad})")

def procesar_guias(anho, tipo_estudio):
    """
    Procesa las guías docentes para un año y tipo de estudio dados.

    Carga los enlaces de los programas, navega a las páginas de guías docentes
    usando Selenium, extrae los enlaces a las guías individuales, descarga
    cada guía, y registra la información en la base de datos. Finalmente,
    guarda los datos de las asignaturas procesadas en un archivo Excel.

    Args:
        anho (str): El año académico (ej. "2023-2024").
        tipo_estudio (str): El tipo de estudio ('grado', 'master', o 'ambos').
    """
    ruta_data = os.path.join("sostenibilidad", "data")
    degrees = cargar_datos(tipo_estudio, ruta_data)

    ruta_guias = os.path.join(ruta_data, "guias")
    os.makedirs(ruta_guias, exist_ok=True)

    subject_data = []
    anho2 = anho.split('-')[0]

    for idx, row in degrees.iterrows():
        basic_link = str(row[0])
        modalidad = "online" if "online" in basic_link else "presencial"
        tipo_programa = row.get("tipo_programa", tipo_estudio)

        url = f"{basic_link}/informacion-basica/guias-docentes"
        driver = configurar_driver()
        enlaces = obtener_enlaces_guias(driver, url)
        driver.quit()

        for enlace in enlaces:
            url_asignatura = enlace.get_attribute('href')
            print(f"Enlace encontrado: {url_asignatura}")
            codigo, nombre_archivo = descargar_guia(url_asignatura, anho2, modalidad, ruta_guias)

            if codigo and nombre_archivo:
                subject_data.append({
                    "basic_link": basic_link,
                    "codigo_asignatura": codigo,
                    "modalidad": modalidad,
                    "nombre_archivo": nombre_archivo
                })

                print("Depuración de datos guardados:")
                print(f"basic_link: {basic_link}")
                print(f"codigo_asignatura: {codigo}")
                print(f"modalidad: {modalidad}")
                print(f"nombre_archivo: {nombre_archivo}")
                print("-" * 50)

                try:
                    registrar_en_bd(anho, codigo, nombre_archivo, modalidad, tipo_programa)
                except IntegrityError:
                    print(f"Error de integridad para {codigo} ({modalidad})")

        time.sleep(2)

    df_subjects = pd.DataFrame(subject_data)
    salida_map = {
        'master': "datos_asignaturas_masteres.xlsx",
        'grado': "datos_asignaturas_grados.xlsx",
        'ambos': "datos_asignaturas_grados_masteres.xlsx"
    }
    ruta_salida = os.path.join(ruta_data, salida_map[tipo_estudio])
    df_subjects.to_excel(ruta_salida, index=False)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso correcto: python script.py <anho> <tipo_estudio>")
        sys.exit(1)
        
    anho = sys.argv[1]
    tipo_estudio = sys.argv[2]
    procesar_guias(anho, tipo_estudio)
