import pandas as pd
from docx import Document
from docx.shared import Inches
from docx2pdf import convert
import os
import sys

def generar(anho):
   
    base_dir = os.path.dirname(__file__)  # Directorio base donde se encuentra el script
    template_path = os.path.join(base_dir, 'informe_general.docx')
    
    if not os.path.exists(template_path):
        print(f"Error: No se encontró la plantilla {template_path}")
        sys.exit(1)
    

    excel_data_path = combinar_excels()
    output_filename = f"University_Country_6_1_Number_of_courses_or_modules_related_to_environment_and_sustainability_offered"
    headers_custom = ["Course Title", "Degree", "Degree link", "Notes"]
    
    if not os.path.exists(excel_data_path):
        print(f"Error: No se encontró el archivo de datos {excel_data_path}")
        sys.exit(1)
    
    output_docx_path = os.path.join(base_dir, f"{output_filename}.docx")
    output_pdf_path = os.path.join(base_dir, f"{output_filename}.pdf")
    
    def extract_data_from_excel(path):
        df = pd.read_excel(path)
        df = df[df['Competences'].notna()]
        headers = df.columns.tolist() if headers_custom is None else headers_custom
        return headers, df.values.tolist(), anho, df.shape[0]
    
   
    def fill_table(doc, headers, data):
        for table in doc.tables:
            # Limpiar la tabla existente
            for row in table.rows:
                for cell in row.cells:
                    cell.text = ""
            
            # Ajustar el número de columnas
            num_columns = len(headers)
            while len(table.columns) < num_columns:
                table.add_column(width=Inches(1.5))
            
            # Insertar encabezados
            for i, header in enumerate(headers):
                table.cell(0, i).text = header
            
            # Insertar datos
            for row_idx, row in enumerate(data):
                if row_idx + 1 >= len(table.rows):
                    table.add_row()
                for col_idx, value in enumerate(row):
                    table.cell(row_idx + 1, col_idx).text = str(value)
            break


    
    def fill_description(doc, year, num_courses):
        description_text = f"The list above includes courses directly related to sustainability offered by the University in the {year} academic year.\n\nTotal number of courses with sustainability embedded for courses running in {year}: {num_courses}"
        for para in doc.paragraphs:
            if "Description:" in para.text:
                para.text = f"Description:\n\n{description_text}"
                break
    
    doc = Document(template_path)
    
    headers, data_from_excel, year, num_courses = extract_data_from_excel(excel_data_path)
    fill_table(doc, headers, data_from_excel)
    fill_description(doc, year, num_courses)
    doc.save(output_docx_path)
    
    try:
        convert(output_docx_path, output_pdf_path)
    except Exception as e:
        print(f"Error al convertir a PDF: {e}")
    
    print(f"Documento PDF generado en: {output_pdf_path}")
    
    
def combinar_excels(debug=False):
    base_dir = os.path.dirname(__file__)
    excel_courses = os.path.join(base_dir, '../sostenibilidad/data/datos_asignaturas_masteres.xlsx')
    excel_guias = os.path.join(base_dir, '../sostenibilidad/data/resultados_guias.xlsx')

    if not os.path.exists(excel_courses) or not os.path.exists(excel_guias):
        print("Error: No se encontraron los archivos de datos necesarios.")
        sys.exit(1)

    # Leer los archivos de Excel
    df_courses = pd.read_excel(excel_courses)
    df_guias = pd.read_excel(excel_guias)

    # Asegurar que los valores de "Code" y "codigo_asignatura" sean del mismo tipo
    df_guias["Code"] = df_guias["Code"].astype(str).str.strip()
    df_courses["codigo_asignatura"] = df_courses["codigo_asignatura"].astype(str).str.strip()

    # Realizar el merge basado en la clave correcta
    df_combined = df_guias.merge(df_courses[['codigo_asignatura', 'basic_link']], 
                                 left_on="Code", right_on="codigo_asignatura", how="right")

    # Renombrar la columna "basic_link" a "Link"
    df_combined.rename(columns={"basic_link": "Link"}, inplace=True)
    
    #Filtrar solo filas donde "Competences" no esté vacío
    df_combined = df_combined[df_combined["Competences"].notna() & (df_combined["Competences"].str.strip() != "")]

    # Seleccionar solo las columnas necesarias
    columnas_deseadas = ["Name", "Degree_Master", "Link","Competences"]
    df_combined = df_combined[columnas_deseadas]

    # Guardar el nuevo Excel con solo las columnas seleccionadas
    combined_path = os.path.join(base_dir, 'resultados_guias_con_link.xlsx')
    df_combined.to_excel(combined_path, index=False)

    return combined_path

