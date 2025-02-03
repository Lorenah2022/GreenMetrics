import http.client
import re
import pandas as pd
import os

# Crear la carpeta "data" si no existe
if not os.path.exists("data"):
    os.makedirs("data")

# Función para obtener el contenido HTML de una página
def obtener_html(host, path):
    conn = http.client.HTTPSConnection(host)
    conn.request("GET", path)
    response = conn.getresponse()
    if response.status == 200:
        return response.read().decode("utf-8")
    else:
        raise Exception(f"Error al obtener la página: {response.status}")

# Función para procesar los enlaces
def procesar_enlaces(host, path, filtro_incluir, filtro_excluir, archivo_salida):
    # Obtener el HTML
    html = obtener_html(host, path)
    
    # Buscar todos los enlaces con una expresión regular
    enlaces = re.findall(r'href="([^"]+)"', html)
    
    # Filtrar los enlaces
    enlaces_filtrados = [
        enlace for enlace in enlaces
        if any(filtro in enlace for filtro in filtro_incluir) and
        not any(filtro in enlace for filtro in filtro_excluir)
    ]
    
    # Convertir enlaces relativos a absolutos
    enlaces_absolutos = [
        enlace if enlace.startswith("http") else f"https://{host}{enlace}"
        for enlace in enlaces_filtrados
    ]
    
    # Guardar los enlaces en un archivo Excel dentro de la carpeta "data"
    archivo_completo = os.path.join("data", archivo_salida)  # Ruta completa dentro de "data"
    df = pd.DataFrame(enlaces_absolutos, columns=["link"])
    df.to_excel(archivo_completo, index=False, engine="openpyxl")
    
    print(f"Enlaces guardados en '{archivo_completo}'")

# Procesar los enlaces de los grados
host_grados = "www.ubu.es"
path_grados = "/grados-ordenados-por-ramas-de-conocimiento"
filtro_incluir_grados = ["grado"]
filtro_excluir_grados = ["grados", "acceso-admision", "mailto", "decreto", "servicio-de"]
archivo_salida_grados = "enlaces_filtrados_grados_ubu.xlsx"
procesar_enlaces(host_grados, path_grados, filtro_incluir_grados, filtro_excluir_grados, archivo_salida_grados)

# Procesar los enlaces de los másteres
host_masteres = "www.ubu.es"
path_masteres = "/estudios/oferta-de-estudios/masteres-universitarios-oficiales"
filtro_incluir_masteres = ["master"]
filtro_excluir_masteres = ["masteres", "mailto", "acceso-admision", "decreto", "servicio-de", "international-students"]
archivo_salida_masteres = "enlaces_filtrados_masteres_ubu.xlsx"
procesar_enlaces(host_masteres, path_masteres, filtro_incluir_masteres, filtro_excluir_masteres, archivo_salida_masteres)
