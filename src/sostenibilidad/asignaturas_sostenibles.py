import subprocess
import sys

def ejecutar_script(script_name):
    """
    Ejecuta un script de Python especificado por su nombre y maneja posibles errores.

    Utiliza `subprocess.run` para ejecutar el script como un proceso separado.
    Si el script se ejecuta correctamente, imprime un mensaje de éxito.
    Si el script devuelve un código de salida distinto de cero (indicando un error),
    imprime un mensaje de error y sale del script actual con un código de error.

    Args:
        script_name (str): El nombre del script de Python a ejecutar.
                           Se espera que el script esté en el mismo directorio
                           o en una ruta accesible.
    """
    try:
        # Ejecuta el script y muestra la salida en consola
        print(f"Ejecutando {script_name}...")
        subprocess.run([sys.executable, script_name], check=True)
        print(f"{script_name} ejecutado con éxito.")
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar {script_name}: {e}")
        sys.exit(1)

def ejecutar_orden():
    """
    Ejecuta una secuencia predefinida de scripts en un orden específico.

    Esta función define el flujo de trabajo principal para obtener y procesar
    los datos de asignaturas y guías docentes llamando a `ejecutar_script`
    para cada paso.
    """
    # Paso 1: Ejecutar el script grados.py
    ejecutar_script('grados.py')
    
    # Paso 2: Ejecutar el script guias_docentes.py
    ejecutar_script('guias_docentes.py')
    
    # Paso 3: Ejecutar el script procesadoAsignaturas.py
    ejecutar_script('procesadoAsignaturas.py')
    
    # Paso 4: Ejecutar el script Prueba API code5.py
    ejecutar_script('Prueba API code5.py')

if __name__ == "__main__":
    ejecutar_orden()
