
import json
import os
import sys


import re

import os
import pandas as pd
from docx import Document
from docx2pdf import convert
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt  # Asegúrate de tener esta importación al principio


import pandas as pd
import requests

from dotenv import load_dotenv


import numpy as np


from datetime import datetime
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook



# Obtener la ruta absoluta del directorio `src`
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Agregar `src` al sys.path para poder importar `config.py`
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from config import cargar_configuracion


# Variable global
base_dir = os.path.dirname(__file__)
load_dotenv()
# Configuración de la API
config = cargar_configuracion()
base_url = config["base_url"]
api_key = config["api_key"]
myModel = config["model"]

# ------------------  PREPROCESADO DE FECHAS ------------------
def preparar_fechas(df):
    # Conversión vectorizada (rápida y garantiza que las columnas sean datetime64)
    df['Fecha Inicio'] = pd.to_datetime(df['Fecha Inicio'], dayfirst=True, errors='coerce')
    df['Fecha Fin'] = pd.to_datetime(df['Fecha Fin'], dayfirst=True, errors='coerce')

    # Verificar si alguna fila tiene ambas fechas vacías
    filas_vacias = df[df[['Fecha Inicio', 'Fecha Fin']].isna().all(axis=1)]
    if not filas_vacias.empty:
        print("Se encontraron filas con ambas fechas vacías. Deteniendo el procesamiento.")
        return df

    # Calcular la duración de forma vectorizada
    df['Duration'] = (df['Fecha Fin'] - df['Fecha Inicio']).dt.days + 1

    return df

# ------------------  CALCULAR IMPUTACIÓN DIARIA ------------------
def calcular_imputacion_diaria(df):
    df['CUANTÍA TOTAL'] = (
        df['CUANTÍA TOTAL']
        .astype(str)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .astype(float)
    )
    df['Daily Imputation'] = df['CUANTÍA TOTAL'] / df['Duration']
    return df

# ------------------ IMPUTACIÓN POR AÑO ------------------
def imputar_por_año(df):
    if df.empty:
        print("No hay datos válidos para procesar.")
        return df

    # Determinar rango de años
    years = range(df['Fecha Inicio'].dt.year.min(), df['Fecha Inicio'].dt.year.max() + 1)

    # Inicializar columnas
    for year in years:
        df[str(year)] = 0.0
        df[f"{year}_sostenible"] = 0.0

    # Calcular imputación anual y llenar las columnas
    for i, row in df.iterrows():
        if pd.isna(row['Fecha Inicio']) or pd.isna(row['Fecha Fin']):
            print(f"Fila {i} tiene fechas vacías. Saltando.")
            continue

        for year in years:
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31)
            effective_start = max(row['Fecha Inicio'], year_start)
            effective_end = min(row['Fecha Fin'], year_end)

            if effective_start <= effective_end:
                days_in_year = (effective_end - effective_start).days + 1
                imputacion = round(days_in_year * row['Daily Imputation'], 2)

                df.at[i, str(year)] = imputacion

                if str(row.get("Sostenible", "no")).lower().strip() == "yes":
                    df.at[i, f"{year}_sostenible"] = imputacion

    return df

# ------------------ DETERMINAR SI ES SOSTENIBLE ------------------
def es_sostenible_api(excel):
        if not excel:
            return None

        body = {
            "model": myModel,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that classifies if a project is related to sustainability. Answer only 'yes' or 'no'\n"
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

                            )
                },
                {
                    "role": "user",
                    "content": excel
                }
            ],
            "temperature": 0.2
        }
        
        body_json = json.dumps(body)

        response = requests.post(
            f"{base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            data=body_json
        )

        if response.status_code != 200:
            print(f"Error en la API para {excel}: {response.status_code} - {response.text}")
            return "no"
       

        #  Obtener respuesta limpia
        message_content = response.json()['choices'][0]['message']['content'].strip().lower()
        # Filtrar solo el contenido posterior a </think>
        if "</think>" in message_content:
            message_content = message_content.split("</think>")[-1].strip()  # Solo lo que sigue después de </think>
        return message_content
 

def marcar_sostenibles_api(df, columna_titulo='Título'):
    df['Sostenible'] = df[columna_titulo].apply(lambda x: es_sostenible_api(x))
    return df      
   
# ----------------- CARGA EL EXCEL CON ENCABEZADO DINÁMICO Y LIMPIA LOS DATOS ------------------  
def cargar_excel_con_header_dinamico(path, columnas_esperadas):
    import pandas as pd

    df_bruto = pd.read_excel(path, header=None)

    for i in range(len(df_bruto)):
        posibles_columnas = df_bruto.iloc[i].tolist()

        if all(col in posibles_columnas for col in columnas_esperadas):
            df = pd.read_excel(path, header=i)

            # Limpiar nombres de columnas
            df.columns = df.columns.str.strip()

            # Eliminar columnas tipo "Unnamed"
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            
            # Detectar fila con "Total:" antes de limpiar
            for j, row in df.iterrows():
                if any(str(cell).strip().lower() == "total:" for cell in row):
                    df = df.iloc[:j]
                    break

            # Eliminar NaNs después de cortar el DataFrame
            df_limpio = df.dropna(subset=columnas_esperadas)
            
            return df_limpio

    raise ValueError("❌ No se encontraron todas las columnas esperadas en ninguna fila.")

# ------------------  AÑADE LA FILA DE TOTAL ------------------
def añadir_fila_total(df):
    # Columnas que contienen números (años y sostenibles)
    columnas_suma = [col for col in df.columns if col.isdigit() or col.endswith('_sostenible')]

    # Creamos la fila vacía
    fila_vacia = pd.Series({col: "" for col in df.columns})

    # Creamos la fila de suma
    fila_suma = {}
    for col in df.columns:
        if col in columnas_suma:
            fila_suma[col] = df[col].sum()
        else:
            fila_suma[col] = ""
            
    primera_columna= df.columns[0]
    fila_suma[primera_columna]= 'TOTAL '

    fila_suma = pd.Series(fila_suma)

    # Añadimos ambas filas al final del DataFrame
    df = pd.concat([df, pd.DataFrame([fila_vacia]), pd.DataFrame([fila_suma])], ignore_index=True)

    return df

# ------------------  DETERMINAR SI ES SOSTENIBLE ------------------
def duplicar_valores_sostenibles(df):
    # Años detectados (solo columnas con nombres numéricos)
    columnas_años = [col for col in df.columns if col.isdigit()]
    
    # Columnas sostenibles correspondientes
    columnas_sostenibles = [f"{año}_sostenible" for año in columnas_años if f"{año}_sostenible" in df.columns]

    for año, año_sostenible in zip(columnas_años, columnas_sostenibles):
        df.loc[df["Sostenible"].str.lower() == "yes", año_sostenible] = df.loc[df["Sostenible"].str.lower() == "yes", año]

    return df

# ------------------  EXPORTAR RESULTADO ------------------
def exportar_resultado(df, path_salida_temp):

    columnas_base = ['Referencia Interna', 'Título', 'Fecha Inicio', 'Fecha Fin', 'CUANTÍA TOTAL', 'Duration', 'Daily Imputation']

    # Años: solo números
    columnas_años = sorted([col for col in df.columns if col.isdigit()])

    # Años sostenibles: tipo "2024_sostenible"
    columnas_sostenibles = sorted([col for col in df.columns if col.endswith('_sostenible') and col.split('_')[0].isdigit()])

    # Construimos columnas finales sin duplicar nada
    columnas_finales = []

    # Añadimos columnas base
    columnas_finales += [col for col in columnas_base if col in df.columns]

    if 'Sostenible' in df.columns:
        columnas_finales.append('Sostenible')

   
    # Añadimos los años normales
    columnas_finales += columnas_años

    # Añadimos los años sostenibles
    columnas_finales += columnas_sostenibles

    df[columnas_finales].to_excel(path_salida_temp, index=False)
    
    return path_salida_temp

# ------------------ OBTENER EL VALOR DEL DOLAR CON RESPECTO AL EURO PARA UN AÑO DADO ------------------
def obtener_tipo_cambio(anio):
    url = f"https://data.fixer.io/api/{anio}-12-31"
    params = {        "access_key": "d1e71d969c6f68cbf05213033123001b","base": "EUR", "symbols": "USD"}
    try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()

            # Depuración: Mostrar toda la respuesta
            print(f"Respuesta de la API para {anio}: {data}")

            # Verificar si la respuesta tiene la clave 'rates'
            if "rates" not in data:
                print(f"❌ No se encontró la clave 'rates' en la respuesta para {anio}. Respuesta completa: {data}")
                return None

            # Asegurarse de que la clave 'USD' está en 'rates'
            if "USD" not in data["rates"]:
                print(f"❌ No se encontró 'USD' en 'rates' para {anio}. Respuesta: {data['rates']}")
                return None

            return data["rates"]["USD"]

    except requests.exceptions.RequestException as e:
        print(f"Error en la solicitud HTTP: {e}")
        return None

# ------------------ GENERA EL EXCEL CON LA TABLA DE LOS CAMBIOS DE MONEDA ------------------
def generar_tabla_resumen(path_salida_temp, path_salida_final):
    df = pd.read_excel(path_salida_temp)


    idx_sostenible = df.columns.get_loc('Sostenible')
    columnas_despues = df.columns[idx_sostenible + 1:]

    anios_normales = [col for col in columnas_despues if not col.endswith('_sostenible')]
    anios_sostenibles = [col for col in columnas_despues if col.endswith('_sostenible')]


    # Eliminar primer y último año (solo intermedios)
    if len(anios_normales) > 2:
        anios_normales = anios_normales[1:-1]

    if len(anios_sostenibles) > 2:
        anios_sostenibles = anios_sostenibles[1:-1]
        
    fila_total = df.iloc[-1]

    total_research_euros = [float(fila_total[a]) for a in anios_normales]
    sustainable_research_euros = [float(fila_total[a]) for a in anios_sostenibles]

    tipos_cambio = {}
    for a in anios_normales:
        cambio = obtener_tipo_cambio(a)
        if cambio is None:
            cambio = 0

            print(f"Advertencia: No se obtuvo el tipo de cambio para el año {a}, usando valor por defecto {cambio}")
        tipos_cambio[a] = cambio

    total_research_usd = [round(e * tipos_cambio[a], 2) for e, a in zip(total_research_euros, anios_normales)]
    sustainable_research_usd = [round(e * tipos_cambio[a], 2) for e, a in zip(sustainable_research_euros, anios_normales)]

    total_usd = sum(total_research_usd)
    sustainable_usd = sum(sustainable_research_usd)
    print (total_usd, sustainable_usd)
    if total_usd == 0.0 or sustainable_usd ==0.0:
        ratio = 0
    else:
        ratio = round((sustainable_usd / total_usd) * 100, 1)

    df_resumen = pd.DataFrame({
        ("Total research", año): [f"{eur:,.2f} €", tipos_cambio[año], f"${usd:,.1f}"]
        for año, eur, usd in zip(anios_normales, total_research_euros, total_research_usd)
    } | {
        ("Sustainability research", año.split('_')[0]): [f"{eur:,.2f} €", tipos_cambio[año.split('_')[0]], f"${usd:,.1f}"]
        for año, eur, usd in zip(anios_sostenibles, sustainable_research_euros, sustainable_research_usd)
    }, index=["Euros", "US Dollar Spot Exchange Rates", "Dolars"])

    df_totales = pd.DataFrame({
        "": [
            "Total research funds (in US Dollars)",
            "Total research funds dedicated to sustainability research",
            "The ratio of sustainability research funding to total research funding"
        ],
        "Resultados": [
            f"${total_usd:,.1f}",
            f"${sustainable_usd:,.1f}",
            f"{ratio}%",
        ]
    })
   
    wb = load_workbook(path_salida_temp)

    # Estilos con openpyxl
    
    with pd.ExcelWriter(path_salida_temp, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Datos Originales", index=False)
        df_resumen.to_excel(writer, sheet_name="Resumen Financiero", startrow=0)
        df_totales.to_excel(writer, sheet_name="Resumen Financiero", startrow=len(df_resumen.index) + 4, index=False)

        
    wb = load_workbook(path_salida_temp)
    ws = wb["Resumen Financiero"]
  
    max_col = ws.max_column
    
    # Estilos
    header_fill_total = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")  # Azul
    header_fill_sust = PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid")   # Verde
    pink_font = Font(color="8A2BE2", bold=True)
    bold_font = Font(bold=True)
    center_align = Alignment(horizontal="center", vertical="center")
    # Guardar la categoría activa (porque solo la primera celda fusionada la contiene)
    current_fill = None

    for col in range(2, max_col + 1):
        col_letter = get_column_letter(col)
        cat_cell = ws[f"{col_letter}1"]
        year_cell = ws[f"{col_letter}2"]
        

        # Si hay una nueva categoría, actualizamos
        if cat_cell.value:
            if "Total research" in str(cat_cell.value):
                current_fill = header_fill_total
                data_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")


            elif "Sustainability research" in str(cat_cell.value):
                current_fill = header_fill_sust
                data_fill = PatternFill(start_color="EBF1DE", end_color="EBF1DE", fill_type="solid")

            cat_cell.fill = current_fill
            
        # Solo aplicar si hay una categoría activa
        if current_fill:
            # Año (fila 2)
            year_cell.fill = current_fill
            year_cell.font = pink_font
            year_cell.alignment = center_align

            # Filas de contenido (por ejemplo 4-7: Euros, Cambio, Dólares)
            for row in range(4, 7):
                cell = ws[f"{col_letter}{row}"]
                cell.fill = data_fill
                cell.alignment = center_align
    
    start_totales_row = len(df_resumen.index) + 5
    for row in range(start_totales_row, start_totales_row + 3):
        label_cell = ws[f"A{row}"]  # Columna A

        if label_cell.value:
            if "Total research funds (in US Dollars)" in str(label_cell.value):
                result_cell = ws[f"B{row}"]
                result_cell.fill = header_fill_total
                result_cell.font = bold_font
                result_cell.alignment = center_align

            elif "Total research funds dedicated to sustainability research" in str(label_cell.value):
                result_cell = ws[f"B{row}"]
                result_cell.fill = header_fill_sust
                result_cell.font = bold_font
                result_cell.alignment = center_align
    
    wb.save(path_salida_final)
    print(f"Tabla de resumen exportada con éxito en el archivo: {path_salida_final}")

 

# ------------------ ELIMINA LAS TABLAS VACÍAS ------------------
def eliminar_tablas_vacias(doc):
    """Elimina las tablas vacías (sin contenido) del documento Word."""
    tablas_a_eliminar = []

    for table in doc.tables:
        vacia = True
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():  # Si hay contenido en alguna celda
                    vacia = False
                    break
            if not vacia:
                break
        if vacia:
            tablas_a_eliminar.append(table)

    for table in tablas_a_eliminar:
        tbl_element = table._element
        tbl_element.getparent().remove(tbl_element)

    print(f"Se eliminaron {len(tablas_a_eliminar)} tabla(s) vacía(s).")



def fill_description(doc, ruta_archivo):
    """Llena la descripción"""
    anio_rango = re.search(r'(\d{4})-(\d{4})', ruta_archivo)

    if anio_rango:
        # Extraemos los años de inicio y fin del rango
        anio_inicio = int(anio_rango.group(1))
        anio_fin = int(anio_rango.group(2))
        
        # Generamos una lista con los años intermedios
        anios_intermedios = list(range(anio_inicio + 1, anio_fin))  # excluyendo los límites
        
        print("Años intermedios:", anios_intermedios)
        # Construcción de la descripción
        description_text = (
            f"The complete list of research projects (years {anio_rango.group(0)}), their amount, their start and end date and their distribution in annual amounts is provided as evidence. "
            f"It also includes whether the project is sustainable research or not. "
            f"For the calculation, the distribution has been made based on the days included in each year and the amount has been determined for the three-year evaluation period ({', '.join(map(str, anios_intermedios))})."
        )

    else:
        print("No se encontró un rango de años.")
        
    
    # Reemplazar el texto en el documento
    for para in doc.paragraphs:
        if "Description:" in para.text:
            para.text = f"Description:\n\n{description_text}"
            break


def set_cell_background(cell, color_hex):
    """Aplica color de fondo hexadecimal a una celda."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex)
    tcPr.append(shd)

   

def insertar_tablas_en_documento(doc, df_resumen, df_datos):
    if isinstance(df_resumen.columns, pd.MultiIndex):
        df_resumen.columns = ['' if 'Unnamed' in str(col) else ' '.join([str(c) for c in col if 'Unnamed' not in str(c)]) for col in df_resumen.columns]

    eliminar_tablas_vacias(doc)

    colores_encabezado = {
        "total research": "93c5fd",
        "sustainability": "86efac",
        "ratio": "fde68a",
    }

    colores_filas = {
        "ratio of sustainability": "fde68a", 
        "total research funds (in us dollars)": "dbeafe",
        "total research funds dedicated to sustainability research": "dcfce7",
    }

    for paragraph in doc.paragraphs:
        if 'Additional' in paragraph.text:
            # Tabla resumen
            new_paragraph_arriba = paragraph.insert_paragraph_before()
            table_resumen = doc.add_table(rows=1, cols=len(df_resumen.columns))
            table_resumen.style = 'Table Grid'

            hdr_cells = table_resumen.rows[0].cells
            columnas_verdes = set()
            columnas_azules = set()
            for j, col in enumerate(df_resumen.columns):
                col_str = str(col).replace("\n", " ").strip()
                hdr_cells[j].text = ""  # Limpiar texto anterior
                run = hdr_cells[j].paragraphs[0].add_run(col_str)
                run.bold = True

                col_str_clean = col_str.lower()

                # Color del encabezado
                if "sustainability" in col_str_clean:
                    color = colores_encabezado["sustainability"]
                    columnas_verdes.add(j)

                elif "total research" in col_str_clean:
                    color = colores_encabezado["total research"]
                    columnas_azules.add(j)

                else:
                    color = None

                if color:
                    set_cell_background(hdr_cells[j], color)

            for _, row in df_resumen.iterrows():
                row_cells = table_resumen.add_row().cells
                fila_no_vacia = False
                for j, value in enumerate(row):
                    val = "" if pd.isna(value) else str(value)
                    row_cells[j].text = val
                    if val != "":
                        fila_no_vacia = True

                    # Pintar celdas según su columna (encabezados verdes o azules)
                    if j in columnas_azules and val:
                        set_cell_background(row_cells[j], "dbeafe")  # Azul
                    elif j in columnas_verdes and val:
                        set_cell_background(row_cells[j], "dcfce7")  # Verde

                if fila_no_vacia:
                    # Pintar toda la fila si la primera columna coincide con claves específicas
                    texto = ' '.join(str(row.iloc[0]).split()).lower()
                    for clave, color in colores_filas.items():
                        clave_limpia = clave.strip().lower()
                        if clave_limpia in texto:
                            for cell in row_cells:
                                if cell.text.strip():  # Solo pintar si no está vacía
                                    set_cell_background(cell, color)
                            break

            new_paragraph_arriba._element.addnext(table_resumen._element)

            # Tabla de datos sin colorear
            new_paragraph_arriba = paragraph.insert_paragraph_before()            
            table_datos = doc.add_table(rows=1, cols=len(df_datos.columns))
            table_datos.style = 'Table Grid'

            hdr_cells = table_datos.rows[0].cells

            # Guardamos índices de columnas por color
            columnas_verdes = set()
            columnas_azules = set()

            # Pintar encabezados según el contenido
            for j, col in enumerate(df_datos.columns):
                col_str = str(col).replace("\n", " ").strip()
                hdr_cells[j].text = ""  # Limpiar texto anterior

                # hdr_cells[j].text = col_str
                run = hdr_cells[j].paragraphs[0].add_run(col_str)
                run.bold = True
                run.font.size = Pt(9)

                col_str_clean = col_str.lower()

                if re.search(r'\b20\d{2}\b', col_str_clean) and "sostenible " not in col_str_clean:
                    set_cell_background(hdr_cells[j], "93c5fd")  # azul
                    columnas_azules.add(j)
                elif re.search(r'20\d{2}.*sostenible', col_str_clean):
                    set_cell_background(hdr_cells[j], "86efac")  # verde
                    columnas_verdes.add(j)

            # Pintar celdas de cada columna que coincide
            for _, row in df_datos.iterrows():
                row_cells = table_datos.add_row().cells
                for j, value in enumerate(row):
                    val = "" if pd.isna(value) else str(value)
                    row_cells[j].text = val

                    # Pintar celdas según su columna
                    if j in columnas_azules and val:
                        set_cell_background(row_cells[j], "dbeafe")
                    elif j in columnas_verdes and val:
                        set_cell_background(row_cells[j], "dcfce7")
            break

        
def generar_informe(excel_path, excel):
    """Genera informe Word y PDF a partir de un Excel generado."""
    base_dir = os.path.dirname(__file__)
    plantilla_path = os.path.join(base_dir, 'informe_general.docx')

    if not os.path.exists(plantilla_path) or not os.path.exists(excel_path):
        print("❌ Plantilla o Excel no encontrado")
        return

    output_filename = "University_Country_6_4_Total Research Funds Dedicated to Sustainability Research (in US Dollars)"
    docx_output = os.path.join(base_dir, f"{output_filename}.docx")
    pdf_output = os.path.join(base_dir, f"{output_filename}.pdf")

    doc = Document(plantilla_path)

    # Reemplazo del texto
    for p in doc.paragraphs:
        if "[6] Education and Research (ED)" in p.text:
            p.text = "[6] Education and Research (ED)\n\n[6.4] Total Research Funds Dedicated to Sustainability Research (in US Dollars)\n"

    fill_description(doc, excel)
    # Leer datos
    df_resumen = pd.read_excel(excel_path, sheet_name='Resumen Financiero', header=[0, 1])
    df_datos = pd.read_excel(excel_path, sheet_name='Datos Originales')

    # Insertar tablas
    insertar_tablas_en_documento(doc, df_resumen, df_datos)

    # Guardar y convertir
    doc.save(docx_output)
    print(f"✅ Informe Word guardado: {docx_output}")

    try:
        convert(docx_output, pdf_output)
        print(f"✅ Informe PDF guardado: {pdf_output}")
    except Exception as e:
        print(f"⚠️ Error al convertir a PDF: {e}")



def generar(excel):

    columnas_esperadas = ['Fecha Inicio', 'Fecha Fin', 'CUANTÍA TOTAL']
    df = cargar_excel_con_header_dinamico(excel, columnas_esperadas)
    df = df.head(5) #quitar
    df = preparar_fechas(df)
    df = calcular_imputacion_diaria(df)
    df = imputar_por_año(df)
    df = marcar_sostenibles_api(df)
    df = duplicar_valores_sostenibles(df)
    df = añadir_fila_total(df)
    path_salida_temp = exportar_resultado(df, "resultados_finales.xlsx")
    path_salida_final = "archivo_final.xlsx"
    generar_tabla_resumen(path_salida_temp, path_salida_final)
    os.remove(path_salida_temp)
    generar_informe(path_salida_final, excel)
    
#     print("EXCEL RECIBIDO", excel)
#     print("PROGRAMA LISTO PARA GENERAR INFORME")
    




    

