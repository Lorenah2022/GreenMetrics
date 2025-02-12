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
        # Cargar el archivo Excel con los enlaces
        ruta_excel = os.path.join(ruta_data, "enlaces_filtrados_masteres_ubu.xlsx")
        degrees = pd.read_excel(ruta_excel)
    elif tipo_estudio == 'grado':
         # Cargar el archivo Excel con los enlaces
        ruta_excel = os.path.join(ruta_data, "enlaces_filtrados_grados_ubu.xlsx")
        degrees = pd.read_excel(ruta_excel)
        
    elif tipo_estudio=='ambos':
        #hacer ambos
        ruta_excel_grados = os.path.join(ruta_data, "enlaces_filtrados_grados_ubu.xlsx")
        ruta_excel_masteres = os.path.join(ruta_data, "enlaces_filtrados_masteres_ubu.xlsx")
        
        grados = pd.read_excel(ruta_excel_grados)
        masteres = pd.read_excel(ruta_excel_masteres)
        
        # Concatenar los DataFrames de grados y másteres
        degrees = pd.concat([grados, masteres], ignore_index=True)
        

    # Lista para almacenar los datos
    subject_data = []

    # Definir la ruta para guardar las guías dentro de "data"
    ruta_guias = os.path.join(ruta_data, "guias")

    # Crear la carpeta "guias" dentro de "data" si no existe
    if not os.path.exists(ruta_guias):
        os.makedirs(ruta_guias)

    # Iterar sobre cada enlace en el DataFrame de grados
    for i in range(len(degrees)):

        # Obtener el enlace base
        basic_link = str(degrees.iloc[i, 0])

        # Determinar la modalidad (online o presencial)
        modalidad = "online" if "online" in basic_link else "presencial"

        # Definir las dos posibles URLs
        urls = [
            f"{basic_link}/informacion-basica/guias-docentes/guias-docentes-de-cursos-anteriores/guias-docentes-{anho}",
            f"{basic_link}/informacion-basica/guias-docentes/guias-docentes-de-cursos-anteriores-0/guias-docentes-{anho}"
        ]

        # Intentar acceder a la primera URL válida
        page = None
        for url in urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                page = BeautifulSoup(response.content, "html.parser")
                break  # Si se obtiene una página válida, salir del bucle
            except requests.exceptions.RequestException:
                print(f"Error al leer la página: {url} - Probando la siguiente opción.")
                continue

        # Si no se pudo acceder a ninguna URL válida, continuar con el siguiente enlace
        if page is None:
            print(f"No se pudo acceder a una página válida para: {basic_link}")
            continue

        # Extraer todos los enlaces de la página
        links = [a["href"] for a in page.find_all("a", href=True)]

        # Filtrar los enlaces que contienen "asignatura" en la URL
        subject_links = [link for link in links if "asignatura" in link]

        # Descargar las guías usando los enlaces filtrados
        for link in subject_links:

            # Verificar si el enlace es absoluto o relativo
            if not link.startswith("http"):
                enlace_completo = f"https://ubuvirtual.ubu.es{link}"
            else:
                enlace_completo = link

            # Extraer el código de asignatura desde la URL
            codigo_asignatura = enlace_completo.split("asignatura=")[-1].split("&")[0]

            # Definir el nombre del archivo PDF con la modalidad incluida
            nombre_archivo = f"{codigo_asignatura}_{modalidad}.pdf"

            # Ruta completa para guardar el archivo en "data/guias"
            ruta_archivo = os.path.join(ruta_guias, nombre_archivo)

            # Intentar descargar el archivo (hasta 3 veces)
            success = False
            for retry_count in range(3):
                try:
                    response = requests.get(enlace_completo)
                    response.raise_for_status()
                    with open(ruta_archivo, "wb") as f:
                        f.write(response.content)
                    success = True
                    break  # Salir del bucle si la descarga fue exitosa
                except requests.exceptions.RequestException:
                    print(f"Error descargando: {enlace_completo} - Intento {retry_count + 1} de 3.")
                    time.sleep(5)  # Esperar 5 segundos antes de reintentar

            if not success:
                print(f"Fallo final al descargar: {enlace_completo} - Pasando al siguiente archivo.")

            # Guardar la información en la lista
            subject_data.append({
                "basic_link": basic_link,
                "enlace_completo": enlace_completo,
                "codigo_asignatura": codigo_asignatura,
                "modalidad": modalidad,
                "nombre_archivo": nombre_archivo
            })


            # Insertar la información directamente en la base de datos
            try:
                with app.app_context():
                    # Comprobar si ya existe un registro con el mismo año, código de asignatura y modalidad
                    registro_existente = Busqueda.query.filter_by(
                        anho=anho,
                        codigo_asignatura=codigo_asignatura,
                        modalidad=modalidad
                    ).first()
                    
                    # Solo insertar si no existe aún esa combinación exacta
                    if not registro_existente:
                        nuevo_registro = Busqueda(
                            anho=anho,
                            tipo_programa=tipo_estudio,
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

            time.sleep(2)  # Pausa de 2 segundos entre descargas para no sobrecargar el servidor

    # Convertir la lista de datos a un DataFrame
    df_subjects = pd.DataFrame(subject_data)


    if tipo_estudio == 'master':
        ruta_excel_salida = os.path.join(ruta_data, "datos_asignaturas_masteres.xlsx")           
    elif tipo_estudio == 'grado':
        ruta_excel_salida = os.path.join(ruta_data, "datos_asignaturas_grados.xlsx")                 
    elif tipo_estudio=='ambos':
       ruta_excel_salida = os.path.join(ruta_data, "enlaces_filtrados_grados_masteres_ubu.xlsx")

    # Guardar el DataFrame en un archivo Excel en la carpeta "data"
    df_subjects.to_excel(ruta_excel_salida, index=False)

if __name__ == "__main__":
    # Obtener el año académico desde los argumentos de la línea de comandos
    if len(sys.argv) != 3:
        print("Uso correcto: python script.py <anho> <tipo_estudio>")
        sys.exit(1)
        
    anho = sys.argv[1]
    tipo_estudio = sys.argv[2]
    procesar_guias(anho, tipo_estudio)
