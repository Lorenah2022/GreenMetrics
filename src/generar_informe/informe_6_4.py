def generar(excel):
    print("EXCEL RECIBIDO", excel)
    print("PROGRAMA LISTO PARA GENERAR INFORME")
    
    
    
    


import csv
import io
import json
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import pandas as pd
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
from docx2pdf import convert
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from dotenv import load_dotenv
from fpdf import FPDF
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException


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

    fila_total = df.iloc[-1]

    total_research_euros = [float(fila_total[a]) for a in anios_normales]
    sustainable_research_euros = [float(fila_total[a]) for a in anios_sostenibles]

    tipos_cambio = {}
    for a in anios_normales:
        cambio = obtener_tipo_cambio(a)
        if cambio is None:
            cambio = 0

            print(f"⚠️ Advertencia: No se obtuvo el tipo de cambio para el año {a}, usando valor por defecto {cambio}")
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
    print(f"✅ Tabla de resumen exportada con éxito en el archivo: {path_salida_final}")


if __name__ == "__main__":

    columnas_esperadas = ['Fecha Inicio', 'Fecha Fin', 'CUANTÍA TOTAL']
    df = cargar_excel_con_header_dinamico("Proyectos UBU (2020-2024)2.xlsx", columnas_esperadas)
    df = df.head(5)
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





# # Función para reemplazar texto en un documento de Word
# def replace_text_in_docx(doc, old_text, new_text):
#     for paragraph in doc.paragraphs:
#         if old_text in paragraph.text:
#             paragraph.text = new_text

# def remove_text_from_docx(doc, text_to_remove):
#     """Elimina cualquier párrafo que contenga el texto especificado."""
#     for paragraph in doc.paragraphs:
#         if text_to_remove in paragraph.text:
#             paragraph.text = ""  # Eliminar el texto

# def fill_description(doc, year_range, anhos):
#     """Llena la descripción"""
    
#     # Construcción de la descripción
#     description_text = (
#         f"The complete list of research projects (years {year_range}), their amount, their start and end date and their "
#         f"distribution in annual amounts is provided as evidence. It also includes whether the project is sustainable "
#         f"research or not. For the calculation, the distribution has been made based on the days included in each year "
#         f"and the amount has been determined for the three‐year evaluation period ({anhos}).  "
     
#     )

#     # Reemplazar el texto en el documento
#     for para in doc.paragraphs:
#         if "Description:" in para.text:
#             para.text = f"Description:\n\n{description_text}"
#             break




# def initialize_table(doc, headers):
#     """Inicializa la tabla en el documento de Word con los encabezados."""
#     for table in doc.tables:
#         while len(table.columns) < len(headers):
#             table.add_column(width=Inches(1.5))
#         for i, header in enumerate(headers):
#             table.cell(0, i).text = header
#         return table  # Retornamos la primera tabla encontrada
#     return None

# def fill_table(table, headers, data):
#     """Llena la tabla con encabezados y datos, asegurando que no haya duplicados."""
    
#     # Eliminar todas las filas existentes si la tabla está vacía
#     while len(table.rows) > 0:
#         table._element.remove(table.rows[0]._element)

#     # Crear la fila de encabezados
#     header_row = table.add_row()
#     for i, header in enumerate(headers):
#         header_row.cells[i].text = header

#     # Agregar filas con datos
#     for row_data in data:
#         row = table.add_row()
#         for col_idx, value in enumerate(row_data):
#             cell = row.cells[col_idx]
#             if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
#                 add_hyperlink(cell.paragraphs[0], value, "Link")
#             else:
#                 cell.text = str(value)

 
     
# # Función que genera el informe
# def generar_informe(datos):
#     """Genera el informe en memoria sin leer de Excel."""
#     base_dir = os.path.dirname(__file__)
#     template_path = os.path.join(base_dir, 'informe_general.docx')
#     print("Datos recibidos ", datos)
#     if not os.path.exists(template_path):
#         print(f"Error: No se encontró la plantilla {template_path}")
#         return

#     output_filename = "University_Country_6_4_Total Research Funds Dedicated to Sustainability Research (in US Dollars)"
#     output_docx_path = os.path.join(base_dir, f"{output_filename}.docx")
#     output_pdf_path = os.path.join(base_dir, f"{output_filename}.pdf")

#     doc = Document(template_path)

#     # Reemplazar texto en la plantilla
#     for paragraph in doc.paragraphs:
#         paragraph.text = paragraph.text.replace(
#             "[6] Education and Research (ED)", 
#             "[6.4] Total Research Funds Dedicated to Sustainability Research (in US Dollars) \n\n"
#         )

#     # Crear la tabla
#     headers = ["Building", "Contract", "Maintenance Type", "File", "Link"]
#     table = initialize_table(doc, headers)

#     fill_table(table, headers, [list(d.values()) for d in datos])


#     doc.save(output_docx_path)

#     try:
#         convert(output_docx_path, output_pdf_path)
#     except Exception as e:
#         print(f"Error al convertir a PDF: {e}")

#     print(f"Documento PDF generado en: {output_pdf_path}")


    
    
# def generar():
#     docx_path =os.path.join(base_dir, 'Campus_Building_Maintenance.docx')
#     enlaces= ejecutar_busquedas(docx_path)
#     "HA BUSCADO ENLACES"
#     datos = ejecutar_API(enlaces)
#     "GENERA DATOS"
#     generar_informe(datos)





    

