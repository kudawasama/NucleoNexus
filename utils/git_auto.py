"""
Núcleo Nexus — Git Automático
==============================
Commit + push + pull automático sin intervención del usuario.
Se ejecuta en background después de cada interacción.

Los tokens sensibles se leen desde .env, no estan hardcodeados.
"""
import subprocess
import os
import logging
import time
from pathlib import Path
from utils.dotenv import get_env

logger = logging.getLogger("nexus.git_auto")

# Directorio del repo
REPO_DIR = Path(__file__).parent.parent
REPO_GITHUB = "kudawasama/NucleoNexus"
CLEAN_REMOTE_URL = f"https://github.com/{REPO_GITHUB}.git"

# Tiempo mínimo entre pushes (evita spam)
LAST_PUSH = 0
PUSH_INTERVAL = 30  # segundos mínimos entre pushes

# Cache del token para no releer .env en cada llamada
_GITHUB_TOKEN = None


def _get_github_token() -> str | None:
    """Lee el token de GitHub desde .env (con cache)."""
    global _GITHUB_TOKEN
    if _GITHUB_TOKEN is None:
        _GITHUB_TOKEN = get_env("GITHUB_TOKEN")
    return _GITHUB_TOKEN


def _ensure_git_auth():
    """Configura el remote con el token de .env si existe.

    Cambia temporalmente el remote a una URL autenticada para que
    git push/pull funcionen sin intervencion manual.
    El token solo se usa en memoria, no se persiste en el remote.
    """
    token = _get_github_token()
    if not token:
        return

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(REPO_DIR), capture_output=True, text=True, timeout=5
    )
    current_url = result.stdout.strip()

    authed_url = f"https://x-access-token:{token}@github.com/{REPO_GITHUB}.git"
    if current_url != authed_url:
        subprocess.run(
            ["git", "remote", "set-url", "origin", authed_url],
            cwd=str(REPO_DIR), capture_output=True, timeout=5
        )


def _reset_remote_url():
    """Restaura el remote a la URL limpia (sin token)."""
    subprocess.run(
        ["git", "remote", "set-url", "origin", CLEAN_REMOTE_URL],
        cwd=str(REPO_DIR), capture_output=True, timeout=5
    )


def _run_git(*args, timeout=15):
    """Ejecuta un comando git en el directorio del repo.

    Configura autenticacion desde .env para comandos que la requieren
    (push, pull, fetch) y restaura la URL limpia al terminar.
    """
    needs_auth = args and args[0] in ("push", "pull", "fetch")
    try:
        if needs_auth:
            _ensure_git_auth()

        result = subprocess.run(
            ["git"] + list(args),
            cwd=str(REPO_DIR),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)
    finally:
        if needs_auth:
            _reset_remote_url()


def check_sensitive_files() -> list[str]:
    """Busca archivos sensibles que podrían subirse accidentalmente a Git."""
    rc, out, err = _run_git("status", "--porcelain")
    if rc != 0 or not out.strip():
        return []
        
    sensitive_patterns = [
        r"\.env",
        r"\.pem$",
        r"\.key$",
        r"secret",
        r"credential",
        r"token",
        r"\.db$",
        r"\.sqlite$"
    ]
    import re as _re
    
    flagged_files = []
    for line in out.split("\n"):
        line = line.strip()
        if not line or len(line) < 4:
            continue
        # XY path o XY "path"
        filepath = line[3:].strip().strip('"')
        filename = Path(filepath).name.lower()
        
        for pattern in sensitive_patterns:
            if _re.search(pattern, filename):
                flagged_files.append(filepath)
                break
                
    return flagged_files


def auto_commit_push(message: str = "auto: cambio de datos"):
    """Commit + push automático. Silencioso si no hay cambios.
    
    Se llama después de cada interacción para mantener el repo sincronizado.
    No hace push si pasaron menos de PUSH_INTERVAL segundos.
    """
    global LAST_PUSH
    
    # 1. Hacer pull primero (traer cambios remotos)
    rc, out, err = _run_git("pull", "--rebase", timeout=20)
    if rc == 0:
        logger.debug(f"git pull OK")
        
    # Verificar archivos sensibles antes de agregar
    flagged = check_sensitive_files()
    if flagged:
        logger.warning(f"AUTO-COMMIT BLOQUEADO: Se detectaron archivos sensibles listos para commit o untracked: {flagged}")
        try:
            # Auto-exclusión: añadir a .gitignore
            gitignore_path = REPO_DIR / ".gitignore"
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# Auto-excluido por seguridad de Nexus\n")
                for file in flagged:
                    f.write(f"{file}\n")
            logger.info(f"Archivos auto-excluidos añadidos a .gitignore: {flagged}")
            # Deshacer cualquier stage previo
            for file in flagged:
                _run_git("reset", "HEAD", file)
        except Exception as git_err:
            logger.error(f"Error al auto-excluir en .gitignore: {git_err}")
        return False
        
    # 2. Stage todos los cambios (datos, memoria, config)
    _run_git("add", "-A")
    
    # 3. Verificar si hay algo para commitear
    rc, out, err = _run_git("status", "--porcelain")
    if rc != 0 or not out.strip():
        logger.debug("Sin cambios para commit")
        return False
    
    # 4. Commit
    rc, out, err = _run_git("commit", "-m", message, timeout=10)
    if rc != 0 and "nothing to commit" not in (err + out):
        logger.warning(f"git commit falló: {err[:100]}")
        return False
    
    logger.debug(f"git commit OK: {message}")
    
    # 5. Push (con throttle para no spamear)
    now = time.time()
    if now - LAST_PUSH < PUSH_INTERVAL:
        logger.debug(f"Push throttled (esperando {PUSH_INTERVAL}s)")
        return True
    
    rc, out, err = _run_git("push", timeout=30)
    if rc == 0:
        LAST_PUSH = now
        logger.debug("git push OK")
        return True
    else:
        logger.warning(f"git push falló: {err[:100]}")
        return False


def auto_pull():
    """Pull al inicio de Nexus para sincronizar con remoto."""
    rc, out, err = _run_git("pull", "--rebase", timeout=20)
    if rc == 0:
        logger.debug("git pull inicial OK")
        return True
    else:
        logger.warning(f"git pull falló: {err[:100]}")
        return False


def get_status() -> dict:
    """Retorna estado del repo git."""
    rc, out, err = _run_git("status", "--short")
    changed = len(out.strip().split("\n")) if out.strip() else 0
    
    rc2, branch, _ = _run_git("branch", "--show-current")
    
    return {
        "branch": branch or "unknown",
        "changed_files": changed,
        "dirty": changed > 0,
    }