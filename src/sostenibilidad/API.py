import os
import requests
import json
import sys

import pandas as pd
from PyPDF2 import PdfReader
from dotenv import load_dotenv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, Busqueda, db  
from sqlalchemy import text

"""
Este script procesa guías docentes en formato PDF para extraer información sobre asignaturas,
incluyendo su nombre, grado/máster, código y competencias curriculares de sostenibilidad.
Utiliza una API externa para identificar competencias de sostenibilidad basándose en
Objetivos de Desarrollo Sostenible (ODS) predefinidos. Los datos extraídos y clasificados
se guardan luego en un archivo Excel y se actualizan en una base de datos.

El script espera archivos PDF en una estructura de directorio específica y requiere
la configuración de la API (URL base, clave API, modelo) cargada desde un archivo .env.
"""


# Configurar la base de datos manualmente si es necesario
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")  # O el nombre que tengas en .env
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Obtener la ruta absoluta del directorio `src`
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Agregar `src` al sys.path para poder importar `config.py`
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from config import cargar_configuracion

# Cargar variables desde .env, como no esta en el mismo directorio que el script, especifico la ubicación del fichero .env
directorio = os.path.join(os.path.dirname(__file__), 'data', 'guias')
load_dotenv()


# Definir rutas
directorio = os.path.join("sostenibilidad","data", "guias")  # Carpeta con los archivos PDF
archivo_salida = os.path.join("sostenibilidad","data", "resultados_guias.xlsx")  # Archivo de salida


# Verificar si el directorio de los archivos PDF existe
if not os.path.exists(directorio):
    print(f"❌ El directorio de los archivos PDF no existe: {directorio}")
    sys.exit(1)  # Salir del programa si no existe el directorio

# Verificar si el archivo de salida es una ruta válida
if not os.path.isdir(os.path.dirname(archivo_salida)):
    print(f"❌ La carpeta de salida no existe: {os.path.dirname(archivo_salida)}")
    sys.exit(1)  # Salir si no existe la carpeta



# Listar los archivos PDF en el directorio
archivos_guias = [f for f in os.listdir(directorio) if f.endswith('.pdf')]
if not archivos_guias:
    print("❌ No se encontraron archivos PDF en el directorio especificado.")
    sys.exit(1)  # Salir si no se encuentran archivos PDF
    
# Configuración de la API
config = cargar_configuracion()
base_url = config["base_url"]
api_key = config["api_key"]
myModel = config["model"]


# Verificar que las configuraciones se cargan correctamente
if not base_url or not api_key or not myModel:
    print("❌ Las configuraciones de la API no están completas. Verifica tu archivo .env.")
    sys.exit(1)



# Crear DataFrame vacío
resultados = pd.DataFrame(columns=["Name", "Degree_Master", "Code", "Competences"])

for pdf_file in archivos_guias:
    pdf_path = os.path.join(directorio, pdf_file)
    
    # Extraer texto del PDF
    with open(pdf_path, "rb") as file:
        reader = PdfReader(file)
        pdf_text = " ".join([page.extract_text() for page in reader.pages[:2]])

    if not pdf_text.strip():
        print(f"Advertencia: No se pudo extraer texto del archivo {pdf_file}. Saltando...")
        continue  # Si el PDF no tiene texto, pasamos al siguiente


    # Construcción del prompt para la IAf
    body = {
        "model": myModel,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You will receive the data of a teaching guide in Spanish. Do not translate it to English. "
                    "Extract and return only the following fields:\n"
                    "1. The name of the subject (without commas)\n"
                    "2. The degree\n"
                    "3. The code\n"
                    "4. The curricular sustainability competencies\n"
                    "Find section with the following title  Competencias que debe adquirir el alumno/a al cursar la asignatura. Identify only the competencies listed there that have an asterisk (*). "
                    " If no competencies have an asterisk, return 'None'.\n"
                    "If at least one competency has an asterisk, return only those that have one and for each competency, analyze its description and determine which of the following objectives it aligns with based on its content:\n"

                        "1. Fin de la pobreza\n"
                        "2. Hambre cero\n"
                        "3. Salud y bienestar\n"
                        "4. Educación de calidad\n"
                        "5. Igualdad de género\n"
                        "6. Agua limpia y saneamiento\n"
                        "7. Energía asequible y no contaminante\n"
                        "8. Trabajo decente y crecimiento económico\n"
                        "9. Industria, innovación e infraestructura\n"
                        "10. Reducción de las desigualdades\n"
                        "11. Ciudades y comunidades sostenibles\n"
                        "12. Producción y consumo responsables\n"
                        "13. Acción por el clima\n"
                        "14. Vida submarina\n"
                        "15. Vida de ecosistemas terrestres\n"
                        "16. Paz, justicia e instituciones sólidas\n"
                        "17. Alianzas para lograr los objetivos\n"
                    "If a competency clearly aligns with one or more objectives, list them next to the competency. SDG X (Y) - Competency Where:\n"
                        "X is the number of the corresponding objective.\n"
                        "Y is the name of the objective.\n"
                        "Competency is the code of the competency\n"
                    "If no clear alignment is found, leave that field empty. If no asterisk return None\n"
                    "Return the four fields separated by commas in this format:\n"
                    "Subject name, degree, code, Curricular sustainability competencies\n"
                    "Ensure that you return ONLY these four fields in a single line, without extra text."
                )
            },
            {
                "role": "user",
                "content": pdf_text
            }
        ],
        "temperature": 0.2
    }

    # Convertir a JSON
    body_json = json.dumps(body)

    # Enviar solicitud a la IA
    response = requests.post(
        f"{base_url}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        data=body_json
    )

    # Verificar si la respuesta es válida
    if response.status_code != 200:
        print(f" Error en la API para {pdf_file}: {response.status_code} - {response.text}")
        continue

    # Extraer la respuesta de la IA
    message_content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '').strip()

    print(f"\n **Respuesta de la IA para {pdf_file}:**\n{message_content}\n")  # DEPURACIÓN

    # Filtrar solo el contenido posterior a </think>
    if "</think>" in message_content:
        message_content = message_content.split("</think>")[-1].strip()  # Solo lo que sigue después de </think>

    # Separar la respuesta por comas
    contenido_separado = [x.strip() for x in message_content.split(",") if x.strip()]

    # Validar si hay al menos 3 elementos (para evitar errores)
    if len(contenido_separado) >= 3:
        competences = contenido_separado[3] if len(contenido_separado) > 3 else "None"
        
        # Aquí detectamos si el curso es sostenible
        es_sostenible = False
        if competences and competences.lower() != "none":
            es_sostenible = True
    
        # Añadimos sostenibilidad también en el DataFrame
        nuevo_resultado = pd.DataFrame([{
            "Name": contenido_separado[0],
            "Degree_Master": contenido_separado[1],
            "Code": contenido_separado[2],
            "Competences": competences,
            "Sostenibilidad": es_sostenible,
            "FileName": pdf_file.lower()  # <-- AÑADIDO AQUÍ

        }])
        resultados = pd.concat([resultados, nuevo_resultado], ignore_index=True)
    else:
        print(f" Error: La respuesta de la IA no tiene el formato correcto. Recibido:\n{message_content}")

# Convertir el valor booleano a "Sí" o "No" para el Excel
resultados["Sostenibilidad"] = resultados["Sostenibilidad"].apply(lambda x: "Sí" if x else "No")

# Guardar los resultados en CSV
if not resultados.empty:
    
    resultados.to_excel(archivo_salida, index=False)
    print(f"\n Archivo guardado correctamente en: {archivo_salida}")
else:
    print("\n No se guardaron datos porque ninguna respuesta fue válida.")


with app.app_context():
    # Verificar las columnas del DataFrame para asegurarse de que coinciden
    print("Columnas del DataFrame:", resultados.columns)
    for _, row in resultados.iterrows():
        # Verificar que las columnas necesarias existen en el DataFrame
        if 'Code' not in row or 'FileName' not in row or 'Sostenibilidad' not in row:
            print("❌ Columna faltante en la fila, asegurándose de que las columnas existan en el DataFrame")
            continue
        print(f"{row['Code']},{row['FileName']}")


        # Verificación de la consulta
        busqueda_existente = Busqueda.query.filter_by(
            codigo_asignatura=row["Code"],
            nombre_archivo=row["FileName"]  # ahora usamos el FileName directamente
        )

        # Imprimir la consulta SQL generada para depuración
        print("Consulta SQL generada:", str(busqueda_existente.statement))

        # Ejecutar la consulta y verificar si existe el resultado
        busqueda_existente = busqueda_existente.first()

        if busqueda_existente:
            busqueda_existente.sostenibilidad = row["Sostenibilidad"]
        else:
            print(f"❌ No encontrado para {row['Code']} {row['Name']}")

    db.session.commit()