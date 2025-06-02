import os
import sys
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# Configure the root directory of the project for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, Busqueda, db  

def get_excel_data(file_path, program_type=None):
    """Reads the Excel file and adds the program type."""
    data = pd.read_excel(file_path)
    if program_type:
        data['tipo_programa'] = program_type
    return data

def setup_chrome_driver():
    """Sets up and returns a headless Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=chrome_options)

def download_file(url, file_path):
    """Downloads a file from the given URL and saves it to the specified file path."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(response.content)
        print(f"Guía descargada: {file_path}")
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar el archivo: {e}")

def process_program_data(degrees, anho, tipo_estudio, ruta_data, ruta_guias):
    """Processes data for each program and stores the results."""
    subject_data = []
    for i, degree in degrees.iterrows():
        basic_link = str(degree[0])
        modalidad = "online" if "online" in basic_link else "presencial"
        driver = setup_chrome_driver()
        url = f"{basic_link}/informacion-basica/guias-docentes"
        driver.get(url)

        # Allow page to load
        time.sleep(5)

        # Find all links to the guides
        enlaces = driver.find_elements(By.XPATH, "//a[contains(@href, 'asignatura')]")
        for enlace in enlaces:
            url_asignatura = enlace.get_attribute('href')
            print(f"Enlace encontrado: {url_asignatura}")
            anho2 = anho.split('-')[0]
            url_descarga = f"https://ubuvirtual.ubu.es/mod/guiadocente/get_guiadocente.php?asignatura={url_asignatura.split('asignatura=')[-1].split('&')[0]}&cursoacademico={anho2}"

            # Define the file name and path
            codigo_asignatura = url_asignatura.split("asignatura=")[-1].split("&")[0]
            nombre_archivo = f"{codigo_asignatura}_{modalidad}.pdf"
            ruta_archivo = os.path.join(ruta_guias, nombre_archivo)

            # Download the file
            download_file(url_descarga, ruta_archivo)

            subject_data.append({
                "basic_link": basic_link,
                "codigo_asignatura": codigo_asignatura,
                "modalidad": modalidad,
                "nombre_archivo": nombre_archivo,
                "tipo_programa": degree.get('tipo_programa', tipo_estudio)  # <- Aquí está la magia

                
            })
        
        driver.quit()

    return subject_data

def save_to_database(subject_data, anho, degrees, tipo_estudio):
    """Saves the subject data to the database if not already present."""
    for data in subject_data:
        try:
            with app.app_context():
                registro_existente = Busqueda.query.filter_by(
                    anho=anho,
                    codigo_asignatura=data['codigo_asignatura'],
                    modalidad=data['modalidad']
                ).first()
                
                if not registro_existente:
                    tipo_programa = data.get('tipo_programa', tipo_estudio)

                    nuevo_registro = Busqueda(
                        anho=anho,
                        tipo_programa=tipo_programa,
                        codigo_asignatura=data['codigo_asignatura'],
                        nombre_archivo=data['nombre_archivo'],
                        modalidad=data['modalidad']
                    )
                    db.session.add(nuevo_registro)
                    db.session.commit()
                else:
                    print(f"El registro para {data['codigo_asignatura']} ({data['modalidad']}) ya existe, ignorado.")
        except IntegrityError:
            print(f"Error de integridad para {data['codigo_asignatura']} ({data['modalidad']}).")

def save_to_excel(subject_data, ruta_data, tipo_estudio):
    """Saves the processed data to an Excel file."""
    df_subjects = pd.DataFrame(subject_data)
    output_file = {
        'master': "datos_asignaturas_masteres.xlsx",
        'grado': "datos_asignaturas_grados.xlsx",
        'ambos': "datos_asignaturas_grados_masteres.xlsx"
    }.get(tipo_estudio, "datos_asignaturas_default.xlsx")

    df_subjects.to_excel(os.path.join(ruta_data, output_file), index=False)
    print(f"Datos guardados en {output_file}")

def procesar_guias(anho, tipo_estudio):
    """Main function to process the guides."""
    ruta_data = os.path.join("sostenibilidad", "data")
    ruta_guias = os.path.join(ruta_data, "guias")
    os.makedirs(ruta_guias, exist_ok=True)

    # Load program data
    if tipo_estudio == 'master':
        ruta_excel = os.path.join(ruta_data, "enlaces_filtrados_masteres_ubu.xlsx")
        degrees = get_excel_data(ruta_excel, 'master')
    elif tipo_estudio == 'grado':
        ruta_excel = os.path.join(ruta_data, "enlaces_filtrados_grados_ubu.xlsx")
        degrees = get_excel_data(ruta_excel, 'grado')
    elif tipo_estudio == 'ambos':
        grados = get_excel_data(os.path.join(ruta_data, "enlaces_filtrados_grados_ubu.xlsx"), 'grado')
        masteres = get_excel_data(os.path.join(ruta_data, "enlaces_filtrados_masteres_ubu.xlsx"), 'master')
        degrees = pd.concat([grados, masteres], ignore_index=True)

    subject_data = process_program_data(degrees, anho, tipo_estudio, ruta_data, ruta_guias)
    save_to_database(subject_data, anho, degrees, tipo_estudio)
    save_to_excel(subject_data, ruta_data, tipo_estudio)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso correcto: python script.py <anho> <tipo_estudio>")
        sys.exit(1)
    
    anho = sys.argv[1]
    tipo_estudio = sys.argv[2]
    procesar_guias(anho, tipo_estudio)