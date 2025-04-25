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

        urls = [
            f"{basic_link}/informacion-basica/guias-docentes/guias-docentes-de-cursos-anteriores/guias-docentes-{anho}",
            f"{basic_link}/informacion-basica/guias-docentes/guias-docentes-de-cursos-anteriores-0/guias-docentes-{anho}"
        ]

        page = None
        for url in urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                page = BeautifulSoup(response.content, "html.parser")
                break
            except requests.exceptions.RequestException:
                print(f"Error al leer la página: {url} - Probando la siguiente opción.")
                continue

        if page is None:
            print(f"No se pudo acceder a una página válida para: {basic_link}")
            continue

        links = [a["href"] for a in page.find_all("a", href=True)]
        subject_links = [link for link in links if "asignatura" in link]

        for link in subject_links:

            if not link.startswith("http"):
                enlace_completo = f"https://ubuvirtual.ubu.es{link}"
            else:
                enlace_completo = link

            codigo_asignatura = enlace_completo.split("asignatura=")[-1].split("&")[0]
            
            if "_online" in codigo_asignatura:
                codigo_asignatura = codigo_asignatura.replace("_online", "")

            nombre_archivo = f"{codigo_asignatura}_{modalidad}.pdf"
            ruta_archivo = os.path.join(ruta_guias, nombre_archivo)

            success = False
            for retry_count in range(3):
                try:
                    response = requests.get(enlace_completo)
                    response.raise_for_status()
                    with open(ruta_archivo, "wb") as f:
                        f.write(response.content)
                    success = True
                    break
                except requests.exceptions.RequestException:
                    print(f"Error descargando: {enlace_completo} - Intento {retry_count + 1} de 3.")
                    time.sleep(5)

            if not success:
                print(f"Fallo final al descargar: {enlace_completo} - Pasando al siguiente archivo.")

            subject_data.append({
                "basic_link": basic_link,
                "enlace_completo": enlace_completo,
                "codigo_asignatura": codigo_asignatura,
                "modalidad": modalidad,
                "nombre_archivo": nombre_archivo
            })

            print("Depuración de datos guardados:")
            print(f"basic_link: {basic_link}")
            print(f"enlace_completo: {enlace_completo}")
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
