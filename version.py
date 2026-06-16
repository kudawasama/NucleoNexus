"""
Núcleo Nexus — Versionado Automático
=====================================
Lee la información de versión desde git (commits) para generar
un versionado semántico automático: 0.1.0+build.COMMIT_COUNT

La versión se lee UNA VEZ al importar el módulo (sin ejecutar git).
"""

from pathlib import Path
import re

# ─── Raíz del proyecto ────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
GIT_DIR = BASE_DIR / ".git"

# ─── Cache de versión (se llena al importar) ──────────────────
VERSION = "0.1.0"
BUILD = 0
COMMIT = "?"
FULL_VERSION = "0.1.0"


def _load_git_info():
    """Lee commit hash + build number desde .git sin ejecutar git."""
    global VERSION, BUILD, COMMIT, FULL_VERSION

    if not GIT_DIR.exists():
        FULL_VERSION = f"{VERSION}+local"
        return

    sha = "?"
    build = 0

    try:
        # Leer HEAD
        head = GIT_DIR / "HEAD"
        if not head.exists():
            FULL_VERSION = f"{VERSION}+local"
            return

        ref = head.read_text("utf-8", errors="replace").strip()
        if ref.startswith("ref: "):
            ref_path = GIT_DIR / ref[5:]
            if ref_path.exists():
                sha = ref_path.read_text("utf-8", errors="replace").strip()[:7]
            else:
                sha = "detached"
        else:
            sha = ref[:7]

        # Contar commits desde packed-refs o desde reflog
        # Estrategia: leer .git/logs/HEAD y contar líneas
        log_file = GIT_DIR / "logs" / "HEAD"
        if log_file.exists():
            build = len(log_file.read_text("utf-8", errors="replace").splitlines())

        COMMIT = sha
        BUILD = build
        FULL_VERSION = f"{VERSION}+build.{build}"
    except Exception:
        FULL_VERSION = f"{VERSION}+local"


# Cargar al importar
_load_git_info()
