import os
import requests
import json
import pandas as pd
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# Cargar variables desde .env, como no esta en el mismo directorio que el script, especifico la ubicación del fichero .env
directorio = os.path.join(os.path.dirname(__file__), 'data', 'guias')
load_dotenv()

# Definir rutas
directorio = os.path.join("sostenibilidad","data", "guias")  # Carpeta con los archivos PDF
archivo_salida = os.path.join("sostenibilidad","data", "resultados_guias.xlsx")  # Archivo de salida

# Listar los archivos PDF en el directorio
archivos_guias = [f for f in os.listdir(directorio) if f.endswith('.pdf')]

# Configuración de la API
base_url = "http://127.0.0.1:1234"
api_key =  os.getenv("API_KEY")
myModel = "lmstudio-community/DeepSeek-R1-Distill-Llama-8B-GGUF"

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


    # Construcción del prompt para la IA
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
                    "Find section 9 in the document. Identify only the competencies listed there that have an asterisk (*). "
                    "If no competencies in section 9 have an asterisk, return 'None' in that field.\n"
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
        "temperature": 0.7
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
        
        nuevo_resultado = pd.DataFrame([{
            "Name": contenido_separado[0],
            "Degree_Master": contenido_separado[1],
            "Code": contenido_separado[2],
            "Competences": competences
        }])
        resultados = pd.concat([resultados, nuevo_resultado], ignore_index=True)
    else:
        print(f" Error: La respuesta de la IA no tiene el formato correcto. Recibido:\n{message_content}")

# Guardar los resultados en CSV
if not resultados.empty:
    resultados.to_excel(archivo_salida, index=False)
    print(f"\n Archivo guardado correctamente en: {archivo_salida}")
else:
    print("\n No se guardaron datos porque ninguna respuesta fue válida.")
