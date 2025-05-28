import http.client
import re
import pandas as pd
import os

# Definir la ruta absoluta a la carpeta 'data' dentro de 'src/sostenibilidad'
ruta_data = os.path.join("sostenibilidad", "data")

# Crear la carpeta "data" dentro de "sostenibilidad" si no existe
if not os.path.exists(ruta_data):
    os.makedirs(ruta_data)
    print(f"Carpeta 'data' creada en: {ruta_data}")
else:
    print(f"Carpeta 'data' ya existe en: {ruta_data}")

def obtener_html(host, path):
    """
    Recupera el contenido HTML de una página web usando HTTP/1.1 sobre HTTPS.

    Args:
        host (str): El nombre de host del sitio web (ej. "www.ubu.es").
        path (str): La ruta a la página específica (ej. "/grados-ordenados-por-ramas-de-conocimiento").

    Returns:
        str: El contenido HTML de la página como una cadena decodificada en UTF-8.

    Raises:
        Exception: Si la solicitud HTTP falla (el código de estado no es 200).
    """
    conn = http.client.HTTPSConnection(host)
    conn.request("GET", path)
    response = conn.getresponse()
    if response.status == 200:
        return response.read().decode("utf-8")
    else:
        raise Exception(f"Error al obtener la página: {response.status}")

def procesar_enlaces(host, path, filtro_incluir, filtro_excluir, archivo_salida):
    """
    Extrae enlaces de una URL dada, los filtra basándose en criterios de inclusión y exclusión,
    convierte los enlaces relativos a absolutos y guarda los resultados en un archivo Excel.

    Args:
        host (str): El nombre de host del sitio web.
        path (str): La ruta a la página específica.
        filtro_incluir (list[str]): Una lista de cadenas; los enlaces deben contener al menos una de ellas.
        filtro_excluir (list[str]): Una lista de cadenas; los enlaces no deben contener ninguna de ellas.
        archivo_salida (str): El nombre del archivo Excel de salida (ej. "enlaces_filtrados_grados_ubu.xlsx").
                              Este archivo se guardará en el directorio 'data'.
    """
    # Verificar si la carpeta de salida existe antes de intentar guardar el archivo
    if not os.path.exists(ruta_data):
        print(f"Error: La carpeta de salida no existe: {ruta_data}")
        return
    
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
    archivo_completo = os.path.join(ruta_data, archivo_salida)
    try:
        df = pd.DataFrame(enlaces_absolutos, columns=["link"])
        df.to_excel(archivo_completo, index=False, engine="openpyxl")
        print(f"Enlaces guardados en '{archivo_completo}'")
    except Exception as e:
        print(f"Error al guardar el archivo Excel: {e}")

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
