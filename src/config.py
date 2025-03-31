import os
import json

# Ruta del archivo de configuración
SRC_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SRC_PATH, "config.json")

# Valores por defecto
DEFAULT_CONFIG = {
    "base_url": "http://127.0.0.1:1234",
    "api_key": os.getenv("API_KEY"),
    "model": "lmstudio-community/DeepSeek-R1-Distill-Llama-8B-GGUF"
}

def cargar_configuracion():
    """Carga la configuración desde config.json y usa valores por defecto si es necesario."""
    try:
        with open(CONFIG_PATH, "r") as file:
            config = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    # Devolver valores de config.json, o valores por defecto si no existen
    return {
        "base_url": config.get("base_url", DEFAULT_CONFIG["base_url"]),
        "api_key": config.get("api_key", DEFAULT_CONFIG["api_key"]),
        "model": config.get("model", DEFAULT_CONFIG["model"]),
    }

def guardar_configuracion(nueva_config):
    """Guarda la nueva configuración en config.json."""
    with open(CONFIG_PATH, "w") as file:
        json.dump(nueva_config, file, indent=4)

