import os
from pathlib import Path


def load_dotenv(path: str = None) -> bool:
    """Carga variables de entorno desde un archivo .env

    Lee el archivo linea por linea, ignora comentarios (#) y lineas vacias.
    Solo soporta formato CLAVE=VALOR (sin expansion de variables).
    No requiere dependencias externas.

    Args:
        path: Ruta al archivo .env. Por defecto busca .env en el directorio
              raiz del proyecto.

    Returns:
        True si se cargo el archivo, False si no existe.
    """
    if path is None:
        path = str(Path(__file__).parent.parent / ".env")

    env_path = Path(path)
    if not env_path.exists():
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    return True


def get_env(key: str, default: str = None) -> str | None:
    """Obtiene una variable de entorno, con soporte opcional para .env

    Primero busca en os.environ. Si no existe, intenta cargar .env
    y vuelve a buscar. Devuelve default si no se encuentra.
    """
    value = os.environ.get(key)
    if value is not None:
        return value

    # Intenta cargar .env una vez
    load_dotenv()
    return os.environ.get(key, default)
