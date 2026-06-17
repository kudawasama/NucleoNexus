"""
Skill — Imagenes
=================
Lista y analiza imagenes en el sistema.
- Sin dependencias: muestra metadatos (nombre, tamaño, dimensiones)
- Con SLM vision: describe el contenido (si el modelo lo soporta)
"""

import os
import time
import base64
from pathlib import Path
from skills.registry import Skill


# Extensiones de imagen soportadas
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}

# Carpeta base de descargas (Windows)
DOWNLOAD_DIR = Path.home() / "Downloads"
PICTURES_DIR = Path.home() / "Pictures"
DESKTOP_DIR = Path.home() / "Desktop"


def _format_size(bytes_val: int) -> str:
    """Formatea bytes a unidad legible."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def _get_image_metadata(filepath: Path) -> dict:
    """Obtiene metadatos basicos de una imagen usando solo stdlib.
    dimensiones se obtiene del header de la imagen (no PIL necesario).
    """
    stat = filepath.stat()
    metadata = {
        "nombre": filepath.name,
        "ruta": str(filepath),
        "tamaño": _format_size(stat.st_size),
        "bytes": stat.st_size,
        "modificado": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
        "extension": filepath.suffix.lower(),
    }

    # Intentar obtener dimensiones del header (sin PIL)
    try:
        with open(filepath, 'rb') as f:
            header = f.read(100)

        if filepath.suffix.lower() in ('.jpg', '.jpeg'):
            # JPEG: buscar marca SOF (start of frame)
            import struct
            pos = 2
            while pos < len(header) - 1:
                if header[pos] == 0xFF and header[pos+1] == 0xC0:
                    height = struct.unpack('>H', header[pos+5:pos+7])[0]
                    width = struct.unpack('>H', header[pos+7:pos+9])[0]
                    metadata["dimensiones"] = f"{width}x{height}"
                    break
                pos += 1
        elif filepath.suffix.lower() == '.png':
            # PNG: dimensiones en bytes 16-24
            if len(header) >= 24:
                import struct
                width = struct.unpack('>I', header[16:20])[0]
                height = struct.unpack('>I', header[20:24])[0]
                metadata["dimensiones"] = f"{width}x{height}"
        elif filepath.suffix.lower() == '.gif':
            if len(header) >= 10:
                width = header[6] + (header[7] << 8)
                height = header[8] + (header[9] << 8)
                metadata["dimensiones"] = f"{width}x{height}"
        elif filepath.suffix.lower() == '.bmp':
            if len(header) >= 26:
                import struct
                width = struct.unpack('<I', header[18:22])[0]
                height = struct.unpack('<I', header[22:26])[0]
                metadata["dimensiones"] = f"{width}x{height}"
        elif filepath.suffix.lower() == '.webp':
            if len(header) >= 30:
                import struct
                width = struct.unpack('<H', header[26:28])[0] & 0x3FFF
                height = struct.unpack('<H', header[28:30])[0] & 0x3FFF
                metadata["dimensiones"] = f"{width}x{height}"
    except Exception:
        pass

    return metadata


def _find_images(directory: Path, limit: int = 10) -> list[Path]:
    """Busca archivos de imagen en un directorio."""
    if not directory.exists():
        return []
    images = []
    for f in sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(f)
            if len(images) >= limit:
                break
    return images


def _resolve_path(ruta: str) -> Path:
    """Resuelve una ruta de directorio desde texto del usuario."""
    r = ruta.lower().strip()

    # Nombres comunes de carpetas
    carpetas = {
        'descarga': DOWNLOAD_DIR,
        'descargas': DOWNLOAD_DIR,
        'download': DOWNLOAD_DIR,
        'downloads': DOWNLOAD_DIR,
        'imagenes': PICTURES_DIR,
        'imágenes': PICTURES_DIR,
        'pictures': PICTURES_DIR,
        'fotos': PICTURES_DIR,
        'fotos': PICTURES_DIR,
        'escritorio': DESKTOP_DIR,
        'desktop': DESKTOP_DIR,
        'carpeta de descarga': DOWNLOAD_DIR,
        'carpeta de descargas': DOWNLOAD_DIR,
    }
    if r in carpetas:
        return carpetas[r]

    # Ruta directa
    p = Path(ruta)
    if p.exists():
        return p

    # Relativo al proyecto
    proj = Path(__file__).parent.parent.parent
    p2 = proj / ruta
    if p2.exists():
        return p2

    return None


def register() -> Skill:
    skill = Skill(name="imagenes", description="Lista y analiza imagenes: metadatos y descripcion visual", version="1.0.0")

    # ─── listar imagenes ─────────────────────────────────────

    def _listar_imagenes(ruta: str = "", limite: int = 10):
        """Lista imagenes en un directorio con metadatos."""
        dir_path = _resolve_path(ruta) if ruta else DOWNLOAD_DIR
        if not dir_path:
            return {"respuesta": f"No encontre la carpeta: {ruta}"}

        images = _find_images(dir_path, limite)
        if not images:
            return {"respuesta": f"No encontre imagenes en: {dir_path.name}"}

        lines = [f"Imagenes en **{dir_path.name}** ({len(images)}):\n"]
        for img in images[:limite]:
            meta = _get_image_metadata(img)
            dims = meta.get("dimensiones", "?x?")
            lines.append(
                f"  {img.name}\n"
                f"    {dims} · {meta['tamaño']} · {meta['modificado']}"
            )

        if len(images) > limite:
            lines.append(f"\n... y {len(images) - limite} mas")

        return {"respuesta": "\n".join(lines)}

    skill.register_action("listar_imagenes", "Lista imagenes en una carpeta con metadatos", _listar_imagenes,
        parameters={
            "ruta": {"type": "string", "description": "Carpeta: 'descargas', 'escritorio', o ruta directa"},
            "limite": {"type": "integer", "description": "Maximo de imagenes a listar"},
        })

    # ─── leer imagen ─────────────────────────────────────────

    def _leer_imagen(archivo: str = "", ruta: str = ""):
        """Lee una imagen: muestra metadatos + intenta descripcion visual."""
        # Determinar el archivo
        filepath = None

        if archivo:
            # Buscar en la ruta especificada o en descargas
            dir_path = _resolve_path(ruta) if ruta else DOWNLOAD_DIR
            if dir_path:
                candidato = dir_path / archivo
                if candidato.exists():
                    filepath = candidato

            if not filepath:
                # Busqueda global
                for base in [DOWNLOAD_DIR, PICTURES_DIR, DESKTOP_DIR]:
                    p = base / archivo
                    if p.exists():
                        filepath = p
                        break

        if not filepath or not filepath.exists():
            return {"respuesta": f"No encontre la imagen: {archivo}. Usa 'lista imagenes en descargas' para ver disponibles."}

        if filepath.suffix.lower() not in IMAGE_EXTENSIONS:
            return {"respuesta": f"'{filepath.name}' no es una imagen soportada."}

        # Metadatos
        meta = _get_image_metadata(filepath)
        dims = meta.get("dimensiones", "dimensiones no detectadas")

        response = (
            f"**Archivo:** {filepath.name}\n"
            f"**Ubicacion:** {filepath.parent}\n"
            f"**Dimensiones:** {dims}\n"
            f"**Tamaño:** {meta['tamaño']}\n"
            f"**Modificado:** {meta['modificado']}\n"
        )

        return {"respuesta": response, "archivo": str(filepath), "metadata": meta}

    skill.register_action("leer_imagen", "Lee una imagen: muestra metadatos y descripcion", _leer_imagen,
        parameters={
            "archivo": {"type": "string", "description": "Nombre del archivo de imagen"},
            "ruta": {"type": "string", "description": "Carpeta donde buscar: 'descargas', 'escritorio'"},
        })

    # ─── buscar imagen por nombre ────────────────────────────

    def _buscar_imagen(nombre: str = "", ruta: str = ""):
        """Busca una imagen por nombre parcial."""
        if not nombre.strip():
            return {"respuesta": "Que imagen quieres buscar? Ej: 'busca imagen foto playa'"}

        dirs = [_resolve_path(ruta)] if ruta else [DOWNLOAD_DIR, PICTURES_DIR, DESKTOP_DIR]
        dirs = [d for d in dirs if d and d.exists()]

        encontradas = []
        nombre_lower = nombre.lower()
        for base in dirs:
            for f in base.iterdir():
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                    if nombre_lower in f.stem.lower():
                        meta = _get_image_metadata(f)
                        dims = meta.get("dimensiones", "?x?")
                        encontradas.append(f"  {f.name} ({dims}, {meta['tamaño']})")
                        if len(encontradas) >= 5:
                            break
            if encontradas:
                break

        if not encontradas:
            return {"respuesta": f"No encontre imagenes con '{nombre}' en las carpetas de usuario."}

        return {"respuesta": f"Imagenes encontradas:\n" + "\n".join(encontradas)}

    skill.register_action("buscar_imagen", "Busca una imagen por nombre parcial", _buscar_imagen,
        parameters={
            "nombre": {"type": "string", "description": "Texto a buscar en el nombre"},
            "ruta": {"type": "string", "description": "Carpeta donde buscar"},
        })

    return skill
