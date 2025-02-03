# Importar librerías necesarias
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# Definir la ruta base para "data"
ruta_data = os.path.join(os.getcwd(), "data")

# Cargar el archivo Excel con los enlaces
ruta_excel = os.path.join(ruta_data, "enlaces_filtrados_masteres_ubu.xlsx")
degrees = pd.read_excel(ruta_excel)

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
        f"{basic_link}/informacion-basica/guias-docentes/guias-docentes-de-cursos-anteriores/guias-docentes-2022-2023",
        f"{basic_link}/informacion-basica/guias-docentes/guias-docentes-de-cursos-anteriores-0/guias-docentes-2022-2023"
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

        time.sleep(2)  # Pausa de 2 segundos entre descargas para no sobrecargar el servidor

# Convertir la lista de datos a un DataFrame
df_subjects = pd.DataFrame(subject_data)

# Ruta del archivo Excel dentro de "data"
ruta_excel_salida = os.path.join(ruta_data, "datos_asignaturas_masteres.xlsx")

# Guardar el DataFrame en un archivo Excel en la carpeta "data"
df_subjects.to_excel(ruta_excel_salida, index=False)
