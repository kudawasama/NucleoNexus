"""
Skill — Archivos Locales
=========================
Lee, escribe y lista archivos en el sistema.
Opera solo dentro del directorio del proyecto por seguridad.
"""

import os
import glob
from pathlib import Path
from skills.registry import Skill

BASE = Path(__file__).parent.parent.parent  # NucleoNexus/

def register() -> Skill:
    skill = Skill(name="archivos", description="Lee, escribe y lista archivos locales", version="1.0.0")

    def _leer_archivo(ruta: str = ""):
        full = (BASE / ruta).resolve()
        if not str(full).startswith(str(BASE)):
            return {"respuesta": "No puedo acceder a archivos fuera del proyecto."}
        if not full.exists() or not full.is_file():
            return {"respuesta": f"Archivo no encontrado: {ruta}"}
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
            return {"respuesta": f"Archivo: {ruta}\n---\n{content[:1000]}"}
        except Exception as e:
            return {"respuesta": f"Error leyendo {ruta}: {e}"}

    skill.register_action("leer_archivo", "Lee el contenido de un archivo", _leer_archivo,
        parameters={"ruta": {"type": "string", "description": "Ruta relativa al proyecto"}})

    def _escribir_archivo(ruta: str = "", contenido: str = ""):
        full = (BASE / ruta).resolve()
        if not str(full).startswith(str(BASE)):
            return {"respuesta": "No puedo escribir fuera del proyecto."}
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(contenido, encoding="utf-8")
            return {"respuesta": f"Archivo guardado: {ruta} ({len(contenido)} bytes)"}
        except Exception as e:
            return {"respuesta": f"Error escribiendo {ruta}: {e}"}

    skill.register_action("escribir_archivo", "Escribe contenido en un archivo", _escribir_archivo,
        parameters={"ruta": {"type": "string"}, "contenido": {"type": "string"}})

    def _listar_archivos(patron: str = "*"):
        full = BASE.resolve()
        files = list(full.rglob(patron))
        files = [f for f in files if f.is_file() and "__pycache__" not in str(f)]
        if not files:
            return {"respuesta": f"No encontre archivos con patron: {patron}"}
        lines = [str(f.relative_to(BASE)) for f in files[:20]]
        return {"respuesta": f"Archivos encontrados ({len(files)}):\n" + "\n".join(lines)}

    skill.register_action("listar_archivos", "Lista archivos del proyecto", _listar_archivos,
        parameters={"patron": {"type": "string", "description": "Patron glob (ej: *.py)"}})

    return skill
