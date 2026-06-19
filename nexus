#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus CLI — Punto de entrada con subcomandos
=============================================
Uso desde cualquier terminal:
  nexus                  Inicia el chat interactivo
  nexus start            Igual que arriba
  nexus update           git pull desde GitHub
  nexus restart          Reinicia (git pull + estado fresco)
  nexus status           Muestra estado del sistema
  nexus model list       Lista modelos instalados (Ollama)
  nexus model use <m>    Cambia al modelo especificado
  nexus model test [q]   Compara todos los backends
  nexus config           Muestra config actual
  nexus config edit      Abre config.py en editor
  nexus backup           Backup del estado y memoria
  nexus logs             Muestra ultimas lineas del log
  nexus version          Version, commit, build
  nexus clean            Limpia cache y archivos temporales
  nexus help             Esta ayuda
"""

import sys
import os
import subprocess
from pathlib import Path

# ─── Raiz del proyecto ─────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# ─── Comandos ───────────────────────────────────────────────────

def cmd_start():
    """Inicia el chat interactivo de Nexus."""
    from main import main as nexus_main
    return nexus_main()


def cmd_update():
    """Actualiza Nexus desde GitHub (git pull)."""
    print("⬇️  git pull...")
    result = subprocess.run(
        ["git", "pull", "origin", "master"],
        cwd=str(BASE_DIR), capture_output=False
    )
    if result.returncode == 0:
        print("✅ Nexus actualizado.")
        # Recargar version
        from version import refresh_version
        refresh_version()
        from version import FULL_VERSION
        print(f"   Version: {FULL_VERSION}")
    else:
        print("❌ Error al actualizar. ¿Hay cambios sin commit?")
    return result.returncode


def cmd_restart():
    """Reinicia Nexus (update + fresh state)."""
    print("🔄 Reiniciando Nexus...")
    # 1. git pull
    subprocess.run(["git", "pull", "origin", "master"], cwd=str(BASE_DIR),
                   capture_output=True)
    # 2. Recargar version
    from version import refresh_version
    refresh_version()
    from version import FULL_VERSION
    print(f"   Version: {FULL_VERSION}")
    # 3. Iniciar
    return cmd_start()


def cmd_status():
    """Muestra el estado actual del sistema."""
    from config import SYSTEM, ENGINE, MEMORY
    from engine.state import StateEngine
    from config import DATA_DIR

    state = StateEngine(str(DATA_DIR / "state"))
    snapshot = state.get_snapshot()
    n = snapshot.get("nexus", {})
    cap = snapshot.get("capabilities", {})
    perf = snapshot.get("performance", {})
    pers = snapshot.get("personality", {})

    print(f"""
╔══ Estado de Nexus ══╗
  Version:      {n.get('version', '?')}
  Commit:       #{n.get('commit', '?')}
  Fase:         {n.get('phase', 'Proto')}
  Backend:      {cap.get('backend', 'symbolic')}
  SLM cargado:  {'🟢 Si' if cap.get('slm_loaded') else '🔴 No'}
  Modelo config: {ENGINE['llm']['model_name']}
  Interacciones: {n.get('total_interactions', 0)}
  Hechos aprendidos: {n.get('total_learned_facts', 0)}
  Skills:        {n.get('total_skills', 0)}
  Confianza:     {n.get('confidence_level', 0):.1%}
  Personalidad:  {pers.get('tone', '?')} (form: {pers.get('formality', 0):.0%})
  Exitos:        {perf.get('successful_responses', 0)}/{perf.get('responses_given', 0)}
  Memoria:       {MEMORY['episodic_limit']:,} episodica, {MEMORY['semantic_limit']:,} semantica
    """)

    # Mostrar modelos Ollama disponibles
    try:
        import urllib.request, json
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            models = data.get("models", [])
            if models:
                print("  Modelos Ollama:")
                for m in models:
                    name = m["name"]
                    size_gb = m.get("size", 0) / 1e9
                    params = m.get("details", {}).get("parameter_size", "?")
                    mark = "⭐" if name == ENGINE['llm']['model_name'] else "  "
                    print(f"    {mark} {name} ({size_gb:.1f}GB, {params})")
    except Exception:
        print("  Ollama: no detectado")


def cmd_model(args: list):
    """Gestion de modelos: list, use, test."""
    if not args:
        print("Uso: nexus model [list|use|test]")
        return 1

    subcmd = args[0]

    if subcmd == "list":
        print("\n╔══ Modelos Ollama Instalados ══╗\n")
        try:
            import urllib.request, json
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                models = data.get("models", [])
                for m in models:
                    name = m["name"]
                    size_gb = m.get("size", 0) / 1e9
                    params = m.get("details", {}).get("parameter_size", "?")
                    family = m.get("details", {}).get("family", "")
                    print(f"  🧠 {name}")
                    print(f"     {size_gb:.1f} GB | {params} params | {family}")
                print(f"\n  Total: {len(models)} modelos")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        print()

    elif subcmd == "use":
        if len(args) < 2:
            print("Uso: nexus model use <nombre>")
            print("  Ej: nexus model use hermes3:3b")
            return 1
        model_name = args[1]
        print(f"Cambiando a modelo: {model_name}...")
        # Actualizar config en memoria y estado
        import config as _cfg
        from engine.state import StateEngine
        from config import DATA_DIR
        _cfg.ENGINE["llm"]["model_name"] = model_name
        state = StateEngine(str(DATA_DIR / "state"))
        state.set("model_state", "backend", value="ollama")
        state.set("model_state", "model_name", value=model_name)
        print(f"✅ Modelo cambiado a: {model_name}")
        print(f"   Reinicia Nexus para aplicar: nexus restart")

    elif subcmd == "test":
        query = " ".join(args[1:]) if len(args) > 1 else "explicame brevemente que es la fotosintesis"
        print(f"🧪 Comparando backends con: \"{query}\"\n")
        # Usar el mismo codigo que el CLI
        from main import NexusCore
        from interface.cli import NexusCLI
        core = NexusCore()
        cli = NexusCLI(core)
        cli._run_model_comparison(query)
        core.shutdown()

    else:
        print(f"Subcomando desconocido: {subcmd}")
        print("  Usa: nexus model [list|use|test]")
        return 1
    return 0


def cmd_config(args: list = None):
    """Muestra o edita la configuracion."""
    if args and args[0] == "edit":
        config_path = BASE_DIR / "config.py"
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "notepad"))
        print(f"Abriendo {config_path} con {editor}...")
        subprocess.run([editor, str(config_path)], shell=True)
        return 0

    from config import ENGINE, MEMORY, LEARNING, INTERFACE, SYSTEM
    print(f"""
╔══ Configuracion de Nexus ══╗

  Engine:
    Modo:     {ENGINE['mode']}
    Backend:  {ENGINE['llm']['backend']}
    Modelo:   {ENGINE['llm']['model_name']}
    API:      {ENGINE['llm']['api_base']}

  Memoria:
    Episodica:  {MEMORY['episodic_limit']:,} entradas
    Semantica:  {MEMORY['semantic_limit']:,} hechos

  Aprendizaje:
    Extraccion: {'on' if LEARNING['pattern_extraction'] else 'off'}
    Refuerzo:   {'on' if LEARNING['reinforcement'] else 'off'}
    Auto-skill: {'on' if LEARNING['auto_skill_create'] else 'off'}

  Interfaz: {INTERFACE['type']}
    """)


def cmd_backup():
    """Backup del estado y base de datos de memoria."""
    import shutil
    import time
    from config import DATA_DIR, MEMORY_DB_PATH

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    files_to_backup = [
        DATA_DIR / "state" / "nexus_state.json",
        Path(MEMORY_DB_PATH) if os.path.exists(MEMORY_DB_PATH) else None,
    ]

    backup_path = backup_dir / f"nexus_backup_{timestamp}"
    backup_path.mkdir(exist_ok=True)

    for f in files_to_backup:
        if f and f.exists():
            shutil.copy2(f, backup_path / f.name)
            print(f"  ✅ {f.name}")

    print(f"\n✅ Backup guardado en: {backup_path}")
    return 0


def cmd_logs(lines: int = 20):
    """Muestra las ultimas lineas del log."""
    from config import LOG_FILE
    log_path = Path(LOG_FILE)
    if not log_path.exists():
        print("No hay archivo de log.")
        return 1

    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    for line in all_lines[-lines:]:
        print(line.rstrip())

    print(f"\n── {len(all_lines)} lineas totales ── Log: {log_path}")
    return 0


def cmd_version():
    """Muestra version, commit y build."""
    from version import FULL_VERSION, VERSION, BUILD, COMMIT
    from config import SYSTEM
    print(f"""
╔══ Nucleo Nexus ══╗
  Version:  {FULL_VERSION}
  Semver:   {VERSION}
  Build:    {BUILD}
  Commit:   #{COMMIT}
  Fase:     {SYSTEM.get('phase', 'Proto')}
  Autor:    {SYSTEM.get('author', 'Jose Cespedes')}
  Repo:     {SYSTEM.get('repository', 'github.com/kudawasama/NucleoNexus')}
    """)


def cmd_clean():
    """Limpia cache y archivos temporales."""
    import shutil

    dirs_to_clean = [
        BASE_DIR / "__pycache__",
        BASE_DIR / "data" / "logs",
    ]

    for d in dirs_to_clean:
        if d.exists():
            if d.is_dir():
                shutil.rmtree(d)
                print(f"  🗑️  {d.name}/")
            else:
                d.unlink()

    # Limpiar __pycache__ recursivo
    for pycache in BASE_DIR.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)

    # Recrear directorios necesarios
    from config import LOGS_DIR
    Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)

    print("✅ Cache y temporales limpiados.")
    return 0


def cmd_help():
    """Muestra esta ayuda."""
    print(__doc__)
    return 0


# ─── Tabla de comandos ──────────────────────────────────────────

COMMANDS = {
    "start":   (cmd_start,   "Inicia el chat interactivo (default)"),
    "update":  (cmd_update,  "git pull desde GitHub"),
    "restart": (cmd_restart, "git pull + reiniciar Nexus"),
    "status":  (cmd_status,  "Muestra estado del sistema"),
    "model":   (cmd_model,   "model list|use|test — Gestion de modelos"),
    "config":  (cmd_config,  "Muestra o edita configuracion"),
    "backup":  (cmd_backup,  "Backup del estado y memoria"),
    "logs":    (cmd_logs,    "Muestra ultimas lineas del log"),
    "version": (cmd_version, "Version, commit y build"),
    "clean":   (cmd_clean,   "Limpia cache y temporales"),
    "help":    (cmd_help,    "Esta ayuda"),
}


def main():
    args = sys.argv[1:]

    if not args:
        return cmd_start()

    cmd = args[0].lower()

    if cmd in COMMANDS:
        handler, _ = COMMANDS[cmd]
        if cmd == "model":
            return handler(args[1:])
        elif cmd == "config":
            return handler(args[1:] if len(args) > 1 else None)
        elif cmd == "logs":
            lines = int(args[1]) if len(args) > 1 and args[1].isdigit() else 20
            return handler(lines)
        else:
            return handler()
    else:
        print(f"❌ Comando desconocido: {cmd}")
        print(f"   Comandos: {', '.join(COMMANDS.keys())}")
        print(f"   Usa 'nexus help' para mas info.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
