import subprocess
import sys

def ejecutar_script(script_name):
    """Ejecuta un script de Python y maneja errores."""
    try:
        # Ejecuta el script y muestra la salida en consola
        print(f"Ejecutando {script_name}...")
        subprocess.run([sys.executable, script_name], check=True)
        print(f"{script_name} ejecutado con éxito.")
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar {script_name}: {e}")
        sys.exit(1)

def ejecutar_orden():
    """Ejecuta los scripts en el orden correcto."""
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
