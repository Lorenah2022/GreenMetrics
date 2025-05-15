# Importar librerías necesarias
import os
import sys
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
# Agregar el directorio raíz de tu proyecto al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, Busqueda, db  
from sqlalchemy.exc import IntegrityError


from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time


""" Función principal que procesa las guías docentes utilizando el año proporcionado. """
def procesar_guias(anho, tipo_estudio):
        
    # Definir la ruta base para "data"
    ruta_data = os.path.join("sostenibilidad", "data")

    if tipo_estudio == 'master':
        ruta_excel = os.path.join(ruta_data, "enlaces_filtrados_masteres_ubu.xlsx")
        degrees = pd.read_excel(ruta_excel)
        degrees['tipo_programa'] = 'master'
    elif tipo_estudio == 'grado':
        ruta_excel = os.path.join(ruta_data, "enlaces_filtrados_grados_ubu.xlsx")
        degrees = pd.read_excel(ruta_excel)
        degrees['tipo_programa'] = 'grado'
    elif tipo_estudio == 'ambos':
        ruta_excel_grados = os.path.join(ruta_data, "enlaces_filtrados_grados_ubu.xlsx")
        ruta_excel_masteres = os.path.join(ruta_data, "enlaces_filtrados_masteres_ubu.xlsx")
        
        grados = pd.read_excel(ruta_excel_grados)
        masteres = pd.read_excel(ruta_excel_masteres)

        grados['tipo_programa'] = 'grado'
        masteres['tipo_programa'] = 'master'
        
        degrees = pd.concat([grados, masteres], ignore_index=True)

    subject_data = []

    ruta_guias = os.path.join(ruta_data, "guias")
    if not os.path.exists(ruta_guias):
        os.makedirs(ruta_guias)

    for i in range(len(degrees)):

        basic_link = str(degrees.iloc[i, 0])
        modalidad = "online" if "online" in basic_link else "presencial"
        
        # Configuración de Selenium para modo headless
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Habilitar el modo headless
        chrome_options.add_argument("--disable-gpu")  # Deshabilitar el uso de GPU
        chrome_options.add_argument("--no-sandbox")  # Deshabilitar el sandbox (útil en entornos virtuales)

        # Iniciar el navegador con las opciones configuradas
        driver = webdriver.Chrome(options=chrome_options)

        # Ir a la URL de la página
        url = f"{basic_link}/informacion-basica/guias-docentes"
        driver.get(url)

        # Esperar un poco para que la página cargue completamente (ajustar si es necesario)
        time.sleep(5)

        # Encontrar los enlaces de las guías docentes
        enlaces = driver.find_elements(By.XPATH, "//a[contains(@href, 'asignatura')]")

        # Extraer los enlaces y procesarlos
        for enlace in enlaces:
            url_asignatura = enlace.get_attribute('href')
            print(f"Enlace encontrado: {url_asignatura}")
            anho2 = anho.split('-')[0]
            # Construir la URL para descargar el archivo PDF
            url_descarga = f"https://ubuvirtual.ubu.es/mod/guiadocente/get_guiadocente.php?asignatura={url_asignatura.split('asignatura=')[-1].split('&')[0]}&cursoacademico={anho2}"

            # Intentar descargar el archivo de la asignatura
            try:
                response = requests.get(url_descarga)
                response.raise_for_status()  # Lanza una excepción si la respuesta es un error

                # Definir el nombre del archivo y guardarlo
                codigo_asignatura = url_asignatura.split("asignatura=")[-1].split("&")[0]
                nombre_archivo = f"{codigo_asignatura}_{modalidad}.pdf"
                ruta_archivo = os.path.join(ruta_guias, nombre_archivo)

                with open(ruta_archivo, "wb") as f:
                    f.write(response.content)

                print(f"Guía descargada: {nombre_archivo}")

            except requests.exceptions.RequestException as e:
                print(f"Error al descargar la guía {url_asignatura}: {e}")

        # Cerrar el navegador después de terminar
        driver.quit()
                
        subject_data.append({
                "basic_link": basic_link,
                "codigo_asignatura": codigo_asignatura,
                "modalidad": modalidad,
                "nombre_archivo": nombre_archivo
        })

        print("Depuración de datos guardados:")
        print(f"basic_link: {basic_link}")
        print(f"codigo_asignatura: {codigo_asignatura}")
        print(f"modalidad: {modalidad}")
        print(f"nombre_archivo: {nombre_archivo}")
        print("-" * 50)

        try:
                with app.app_context():
                    registro_existente = Busqueda.query.filter_by(
                        anho=anho,
                        codigo_asignatura=codigo_asignatura,
                        modalidad=modalidad
                    ).first()
                    
                    if not registro_existente:
                        tipo_programa = degrees.iloc[i].get("tipo_programa", tipo_estudio)
                        nuevo_registro = Busqueda(
                            anho=anho,
                            tipo_programa=tipo_programa,
                            codigo_asignatura=codigo_asignatura,
                            nombre_archivo=nombre_archivo,
                            modalidad=modalidad
                        )
                        db.session.add(nuevo_registro)
                        db.session.commit()
                    else:
                        print(f"El registro para {codigo_asignatura} ({modalidad} {basic_link}) ya existe, ignorado.")
                        
        except IntegrityError:
                print(f"Error de integridad para {codigo_asignatura} ({modalidad}).")

        time.sleep(2)

    df_subjects = pd.DataFrame(subject_data)

    if tipo_estudio == 'master':
        ruta_excel_salida = os.path.join(ruta_data, "datos_asignaturas_masteres.xlsx")           
    elif tipo_estudio == 'grado':
        ruta_excel_salida = os.path.join(ruta_data, "datos_asignaturas_grados.xlsx")                 
    elif tipo_estudio == 'ambos':
        ruta_excel_salida = os.path.join(ruta_data, "datos_asignaturas_grados_masteres.xlsx")

    df_subjects.to_excel(ruta_excel_salida, index=False)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso correcto: python script.py <anho> <tipo_estudio>")
        sys.exit(1)
        
    anho = sys.argv[1]
    tipo_estudio = sys.argv[2]
    procesar_guias(anho, tipo_estudio)
