"""
Núcleo Nexus — Versionado Automático
=====================================
Lee la información de versión desde git (commits) para generar
un versionado semántico automático: 0.1.0+build.COMMIT_COUNT

La versión se recalcula llamando refresh_version().
"""

from pathlib import Path
import re
import subprocess

# ─── Raíz del proyecto ────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
GIT_DIR = BASE_DIR / ".git"

# ─── Cache de versión ────────────────────────────────────────
VERSION = "0.1.0"
BUILD = 0
COMMIT = "?"
FULL_VERSION = "0.1.0"


def _count_commits_via_pack() -> int:
    """Cuenta commits leyendo .git/packed-refs y/o objetos.

    Estrategia robusta: parsear .git/packed-refs + refs/heads/master
    y contar el grafo desde ese SHA via indices.
    """
    # Estrategia 1: leer packed-refs + master ref
    ref_content = None
    ref_path = GIT_DIR / "refs" / "heads" / "master"
    if ref_path.exists():
        ref_content = ref_path.read_text("utf-8", errors="replace").strip()
    else:
        packed = GIT_DIR / "packed-refs"
        if packed.exists():
            for line in packed.read_text("utf-8", errors="replace").splitlines():
                if line.endswith("refs/heads/master"):
                    ref_content = line.split()[0]
                    break

    if not ref_content:
        return 0

    # Estrategia 2: parsear indice de objetos git (sin git CLI)
    # No es trivial parsear objetos git desde Python puro.
    # Solución: contar commits por el log del reflog + ajustar
    # Pero el reflog puede incluir operaciones no-commit.

    # Mejor estrategia: usar git CLI pero sin shell, con timeout
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(BASE_DIR),
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass

    return 0


def _load_git_info() -> None:
    """Lee commit hash + build number desde git.

    Estrategia:
    1. SHA: leer .git/HEAD -> refs/heads/master -> SHA
    2. BUILD: 'git rev-list --count HEAD' (proceso corto, 5s timeout)
    """
    global VERSION, BUILD, COMMIT, FULL_VERSION

    if not GIT_DIR.exists():
        FULL_VERSION = f"{VERSION}+local"
        return

    sha = "?"
    try:
        # ─── SHA ───
        head = GIT_DIR / "HEAD"
        if head.exists():
            ref = head.read_text("utf-8", errors="replace").strip()
            if ref.startswith("ref: "):
                ref_path = GIT_DIR / ref[5:]
                if ref_path.exists():
                    sha = ref_path.read_text("utf-8", errors="replace").strip()[:7]
                else:
                    # Buscar en packed-refs
                    packed = GIT_DIR / "packed-refs"
                    if packed.exists():
                        target = ref[5:]
                        for line in packed.read_text("utf-8", errors="replace").splitlines():
                            if line.endswith(target):
                                sha = line.split()[0][:7]
                                break
                            sha = "detached"
            else:
                sha = ref[:7]
    except Exception:
        sha = "?"

    # ─── BUILD (commits total) ───
    build = _count_commits_via_pack()

    COMMIT = sha
    BUILD = build
    FULL_VERSION = f"{VERSION}+build.{build}" if build > 0 else f"{VERSION}+{sha}"


def refresh_version() -> None:
    """Recarga la versión desde git. Llamar después de /update."""
    _load_git_info()


# Cargar al importar
_load_git_info()

