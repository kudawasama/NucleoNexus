"""
Núcleo Nexus — Interfaz CLI Interactiva
=========================================
Terminal interactiva con colores, historial y comandos.
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ─── Menu interactivo con teclado ──────────────────────────────
try:
    from interface.menu import interactive_menu, C as MC
    HAS_INTERACTIVE_MENU = True
except ImportError:
    HAS_INTERACTIVE_MENU = False

# ─── Autocompletado con readline ───────────────────────────────
try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

# ─── Herramientas externas ─────────────────────────────────────
try:
    from tools.pdf_renamer import procesar as pdf_renombrar
    HAS_PDF_RENAMER = True
except ImportError:
    HAS_PDF_RENAMER = False

# ─── Colores ANSI ─────────────────────────────────────────────
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    
    # Foreground
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    ORANGE = "\033[38;5;214m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"

    @classmethod
    def rgb(cls, r, g, b):
        return f"\033[38;2;{r};{g};{b}m"


# ─── ASCII Art ────────────────────────────────────────────────
NEXUS_ASCII = f"""
  {Color.rgb(0, 180, 255)}███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
  {Color.rgb(0, 195, 255)}████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
  {Color.rgb(0, 210, 255)}██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
  {Color.rgb(0, 225, 255)}██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
  {Color.rgb(0, 240, 255)}██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
  {Color.rgb(0, 255, 255)}╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝{Color.RESET}
  {Color.DIM}  IA Ultra-Ligera · Aprendizaje Incremental · SLM-Ready{Color.RESET}
"""


class NexusCLI:
    """Terminal interactivo de Núcleo Nexus."""

    def __init__(self, nexus_core):
        self.core = nexus_core
        self.history = []
        self.running = True
        self._git_info = self._load_git_info()
        self._setup_history()

    def _setup_history(self):
        """Carga historial de comandos previos si existe."""
        hist_file = Path(self.core.state.state_dir) / ".nexus_history"
        if hist_file.exists():
            try:
                self.history = hist_file.read_text().splitlines()
            except:
                pass

    def _load_git_info(self) -> str:
        """Obtiene el último commit de git para mostrar en metadata."""
        repo_base = Path(__file__).parent.parent
        git_dir = repo_base / ".git"
        if not git_dir.exists():
            return ""
        try:
            head = git_dir / "HEAD"
            if not head.exists():
                return ""
            ref = head.read_text().strip()
            if ref.startswith("ref: "):
                ref_path = git_dir / ref[5:]
                if ref_path.exists():
                    sha = ref_path.read_text().strip()[:7]
                else:
                    return ""
            else:
                sha = ref[:7]
            return sha
        except Exception:
            return ""

    def _save_history(self, line: str):
        """Guarda comando en historial."""
        self.history.append(line)
        hist_file = Path(self.core.state.state_dir) / ".nexus_history"
        try:
            hist_file.write_text("\n".join(self.history[-1000:]))
        except:
            pass

    def show_banner(self):
        """Muestra el banner de bienvenida."""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(NEXUS_ASCII)
        phase = self.core.state.get("nexus", "phase", default="Proto")
        version = self.core.state.get("nexus", "version", default="0.1.0")
        commit = self.core.state.get("nexus", "commit", default="?")
        backend = self.core.state.get("capabilities", "backend", default="symbolic")
        repo = "github.com/kudawasama/NucleoNexus"
        
        # Generar las lineas de forma alineada dinamica
        line1 = f"  Fase: {Color.YELLOW}{phase}{Color.RESET}  ·  v{version}  ·  #{commit}"
        line2 = f"  Backend: {Color.GREEN}{backend}{Color.RESET}  ·  {repo}"
        line3 = f"  Escribe '{Color.GREEN}/help{Color.RESET}' para comandos  ·  '{Color.GREEN}/exit{Color.RESET}' para salir"
        
        border = f"{Color.rgb(0, 180, 255)}─────────────────────────────────────────────────────────────────{Color.RESET}"
        print(border)
        print(line1)
        print(line2)
        print(line3)
        print(border)
        print()

    def run(self):
        """Bucle principal de la CLI."""
        self._setup_autocomplete()
        self.show_banner()

        while self.running:
            try:
                prompt = (f"{Color.rgb(0, 180, 255)}Nexus{Color.RESET}"
                          f"{Color.GRAY}@{Color.RESET}"
                          f"{Color.rgb(255, 200, 50)}φ{Color.RESET} ")
                user_input = self._get_input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                self._cmd_exit()
                break

            if not user_input.strip():
                continue

            # ─── Menu interactivo: si escribe solo "/" → mostrar menu ───
            if user_input.strip() == "/":
                self._show_command_menu()
                continue

            self._save_history(user_input)

            # Comandos del sistema
            if user_input.startswith("/"):
                self._handle_command(user_input)
                continue

            # Procesar input con Nexus
            # Callback de estado en vivo
            last_status = ""
            def on_status(msg):
                nonlocal last_status
                if msg != last_status:
                    last_status = msg
                    # Mostrar en la misma linea con \r
                    print(f"  {Color.DIM}{msg}{Color.RESET}\r", end="", flush=True)
            
            response, metadata = self.core.process(user_input, on_status=on_status)
            
            # Limpiar linea de status
            if last_status:
                print(" " * 60 + "\r", end="", flush=True)

            # Mostrar respuesta con estilo
            self._show_response(response, metadata)

    def _get_input(self, prompt: str) -> str:
        """Lee la entrada del usuario. En Windows sin readline, usa msvcrt para Tab y flechas."""
        if os.name != 'nt' or HAS_READLINE:
            return input(prompt)

        import msvcrt
        sys.stdout.write(prompt)
        sys.stdout.flush()

        buf = []
        hist_idx = len(self.history)
        
        # Para el autocompletado ciclico con Tab
        tab_prefix = None
        tab_matches = []
        tab_idx = 0
        last_was_tab = False

        while True:
            try:
                ch = msvcrt.getwch()
            except (KeyboardInterrupt, SystemExit):
                print()
                raise KeyboardInterrupt
            
            # Detectar Enter
            if ch == '\r' or ch == '\n':
                line = "".join(buf)
                print()
                return line
            
            # Detectar Backspace
            elif ch == '\x08':
                last_was_tab = False
                if buf:
                    buf.pop()
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            
            # Detectar Tab
            elif ch == '\t':
                current_text = "".join(buf)
                if current_text.startswith('/') or (last_was_tab and tab_prefix):
                    if not last_was_tab:
                        # Iniciar busqueda de coincidencias
                        tab_prefix = current_text
                        tab_matches = [cmd for cmd in self._all_commands if cmd.startswith(tab_prefix)]
                        tab_idx = 0
                    else:
                        # Rotar coincidencia si se presiona Tab consecutivamente
                        if tab_matches:
                            tab_idx = (tab_idx + 1) % len(tab_matches)
                    
                    if tab_matches:
                        match = tab_matches[tab_idx]
                        # Borrar la palabra actual en pantalla
                        sys.stdout.write('\b' * len(buf) + ' ' * len(buf) + '\b' * len(buf))
                        buf = list(match)
                        sys.stdout.write(match)
                        sys.stdout.flush()
                    
                    last_was_tab = True
                    continue
            
            # Detectar teclas especiales (Flechas)
            elif ch in ('\x00', '\xe0'):
                last_was_tab = False
                try:
                    ch2 = msvcrt.getwch()
                except Exception:
                    continue
                
                # Flecha Arriba (H)
                if ch2 == 'H' and self.history:
                    if hist_idx > 0:
                        hist_idx -= 1
                        sys.stdout.write('\b' * len(buf) + ' ' * len(buf) + '\b' * len(buf))
                        buf = list(self.history[hist_idx])
                        sys.stdout.write("".join(buf))
                        sys.stdout.flush()
                # Flecha Abajo (P)
                elif ch2 == 'P' and self.history:
                    if hist_idx < len(self.history) - 1:
                        hist_idx += 1
                        sys.stdout.write('\b' * len(buf) + ' ' * len(buf) + '\b' * len(buf))
                        buf = list(self.history[hist_idx])
                        sys.stdout.write("".join(buf))
                        sys.stdout.flush()
                    elif hist_idx == len(self.history) - 1:
                        hist_idx += 1
                        sys.stdout.write('\b' * len(buf) + ' ' * len(buf) + '\b' * len(buf))
                        buf = []
                        sys.stdout.flush()
            
            # Caracter normal
            else:
                last_was_tab = False
                buf.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()

    def _setup_autocomplete(self):
        """Configura autocompletado con Tab para comandos /."""
        if not HAS_READLINE:
            return
        try:
            # Lista de comandos para autocompletar
            self._all_commands = [
                "/help", "/status", "/stats", "/fase", "/hechos", "/memoria",
                "/skills", "/hora", "/buscar", "/aprende", "/aprende-web",
                "/recuerda", "/analiza", "/olvida", "/limpiar-web",
                "/model", "/model list", "/model use", "/model test",
                "/backend", "/personalidad", "/export", "/version",
                "/update", "/clear", "/reset", "/exit", "/agent",
                "/renombrar", "/verbose"
            ]
            def completer(text, state):
                options = [cmd for cmd in self._all_commands if cmd.startswith(text)]
                if state < len(options):
                    return options[state]
                return None
            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass

    def _get_installed_ollama_models(self):
        """Consulta Ollama API y retorna lista de modelos instalados."""
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                models = data.get("models", [])
                return [(m["name"], m.get("size", 0), m.get("details", {}).get("parameter_size", "?"))
                        for m in models]
        except Exception:
            return []

    def _show_command_menu(self):
        """Menu interactivo de comandos con navegacion por teclado."""
        commands_list = [
            ("/help",       "Ver ayuda de todos los comandos"),
            ("/status",     "Estado del sistema (fase, memoria)"),
            ("/stats",      "Estadisticas de memoria"),
            ("/fase",       "Fase actual de Nexus"),
            ("/hechos",     "Ver hechos aprendidos"),
            ("/memoria",    "Ver ultimos recuerdos"),
            ("/skills",     "Ver skills cargadas"),
            ("/hora",       "Fecha y hora actual"),
            ("/buscar X",   "Buscar en la web y aprender"),
            ("/aprende X",  "Guardar un hecho directo"),
            ("/aprende-web X", "Buscar y aprender sobre un tema"),
            ("/analiza X",  "Extraer hechos de un texto"),
            ("/olvida X",   "Borrar un hecho de la memoria"),
            ("/model",      "Gestionar modelos (menu interactivo)"),
            ("/model test X","Comparar todos los backends"),
            ("/backend",    "Cambiar backend (symbolic/slm/hybrid)"),
            ("/personalidad","Ver/ajustar personalidad"),
            ("/export",     "Exportar estado como JSON"),
            ("/version",    "Version, commit y build"),
            ("/update",     "git pull desde GitHub"),
            ("/clear",      "Limpiar pantalla"),
            ("/reset",      "Resetear Nexus"),
            ("/exit",       "Salir"),
            ("/agent X",    "Encadenar tools (investigar, explicar)"),
        ]

        if HAS_INTERACTIVE_MENU:
            opts = [f"{cmd:<18} {desc}" for cmd, desc in commands_list]
            choice = interactive_menu("Comandos Nexus", opts)
            if choice is not None and 0 <= choice < len(commands_list):
                cmd = commands_list[choice][0]
                # Si tiene 'X', pedir argumento
                if ' X' in cmd or 'X' in cmd:
                    base_cmd = cmd.replace(' X', '').replace('X', '')
                    arg = input(f"{Color.DIM}Argumento para {Color.GREEN}{base_cmd}{Color.DIM}:{Color.RESET} ").strip()
                    if arg:
                        self._handle_command(f"{base_cmd} {arg}")
                    else:
                        print(f"{Color.YELLOW}Comando '{base_cmd}' requiere argumento{Color.RESET}")
                else:
                    self._handle_command(cmd)
            return

        # Fallback sin interactive_menu
        print(f"\n{Color.CYAN}╔══ Comandos Nexus ══╗{Color.RESET}")
        for i, (cmd, desc) in enumerate(commands_list, 1):
            print(f"  {Color.YELLOW}{i:>2}{Color.RESET} {Color.GREEN}{cmd:<18}{Color.RESET} {Color.DIM}{desc}{Color.RESET}")
        print(f"{Color.CYAN}╚{'═'*22}╝{Color.RESET}")
        print(f"{Color.DIM}Escribe numero, comando (/help), o 'q'{Color.RESET}")

        # Numero → indice en commands_list
        arg_commands_idx = {i for i, (cmd, _) in enumerate(commands_list) if 'X' in cmd}

        while True:
            try:
                sel = input(f"{Color.rgb(0, 180, 255)}menu>{Color.RESET} ")
            except (EOFError, KeyboardInterrupt):
                print()
                return

            sel = sel.strip()
            if not sel or sel.lower() in ("q", "quit", "salir", "exit"):
                return

            # Si es un numero
            if sel.isdigit():
                idx = int(sel) - 1
                if 0 <= idx < len(commands_list):
                    cmd, _ = commands_list[idx]
                    if idx in arg_commands_idx:
                        base_cmd = cmd.replace(" X", "").strip()
                        arg = input(f"  {Color.DIM}Argumento para {base_cmd}:{Color.RESET} ").strip()
                        if arg:
                            cmd = f"{base_cmd} {arg}"
                        else:
                            cmd = base_cmd
                    print(f"  {Color.GREEN}-> Ejecutando: {cmd}{Color.RESET}")
                    self._handle_command(cmd)
                    return

            # Si empieza con / es un comando directo
            if sel.startswith("/"):
                base = sel.split()[0]
                needs_arg = base in ("/buscar", "/aprende", "/aprende-web",
                                     "/recuerda", "/analiza", "/olvida", "/model")
                if needs_arg and len(sel.split()) == 1:
                    arg = input(f"  {Color.DIM}Argumento para {sel}:{Color.RESET} ").strip()
                    if arg:
                        sel = f"{sel} {arg}"
                print(f"  {Color.GREEN}-> Ejecutando: {sel}{Color.RESET}")
                self._handle_command(sel)
                return

            # Si no es ni numero ni comando, tratarlo como query
            print(f"  {Color.GREEN}-> Procesando como query:{Color.RESET} {sel}")
            response, metadata = self.core.process(sel)
            self._show_response(response, metadata)
            return

    def _show_response(self, response: str, metadata: dict):
        """Muestra la respuesta formateada con metadatos técnicos en una sola línea elegante."""
        phase = self.core.state.get("nexus", "phase", default="Proto")
        
        # Indicador de fase con color distintivo
        phase_indicator = {
            "Proto": f"{Color.GRAY}[φ]{Color.RESET}",
            "Básico": f"{Color.BLUE}[◈]{Color.RESET}",
            "Intermedio": f"{Color.GREEN}[◆]{Color.RESET}",
            "Avanzado": f"{Color.MAGENTA}[◇]{Color.RESET}",
            "Pro": f"{Color.ORANGE}[✦]{Color.RESET}",
        }.get(phase, f"{Color.GRAY}[?]{Color.RESET}")

        print(f"\n{phase_indicator} ", end="")
        
        # Imprimir respuesta con word wrap simple
        words = response.split()
        line = ""
        for word in words:
            if len(line + word) > 78:
                print(f"  {line}")
                line = word
            else:
                line = f"{line} {word}" if line else word
        if line:
            print(f"  {line}")
        print()
        
        # Unificar metadatos en una sola línea fina y elegante
        backend = metadata.get("backend", "symbolic")
        model = metadata.get("model", "")
        elapsed = metadata.get("duration_ms", 0) or metadata.get("total_duration_ms", 0)
        tokens_gen = metadata.get("tokens_generated", 0)
        tool = metadata.get("tool_called", "")
        ver = metadata.get("version", "")
        skills_n = metadata.get("skills_count", 0)
        interactions = metadata.get("interactions", 0)
        mode = metadata.get("mode", "")
        git = self._git_info
        
        # Etiqueta de backend
        if backend == "slm":
            engine_lbl = f"{Color.ORANGE}SLM{Color.RESET}"
        else:
            engine_lbl = f"{Color.GRAY}φ{Color.RESET}"

        parts = [f"{engine_lbl} {elapsed:.0f}ms"]
        if tool:
            parts.append(f"🔧 {tool}")
        if model:
            parts.append(model)
        if tokens_gen:
            parts.append(f"{tokens_gen} tok")
        if ver:
            parts.append(f"v{ver}")
        if git:
            parts.append(f"#{git}")
        if mode:
            parts.append(mode)
        if skills_n:
            parts.append(f"{skills_n} tools")
        if interactions:
            parts.append(f"{interactions} int")
            
        conf = self.core.state.get("nexus", "confidence_level", default=0)
        bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
        parts.append(f"[{bar}] {conf:.0%}")
        
        # Imprimir metadatos en una sola línea con separadores de puntos flotantes
        print(f"  {Color.DIM}─── {' · '.join(parts)}{Color.RESET}\n")

    def _handle_command(self, cmd: str):
        """Maneja comandos internos de la CLI."""
        cmd = cmd.strip().lower()

        commands = {
            "/help": self._cmd_help,
            "/exit": self._cmd_exit,
            "/quit": self._cmd_exit,
            "/status": self._cmd_status,
            "/stats": self._cmd_stats,
            "/reset": self._cmd_reset,
            "/clear": self._cmd_clear,
            "/fase": self._cmd_phase,
            "/memoria": self._cmd_memory,
            "/hechos": self._cmd_facts,
            "/olvida": self._cmd_forget,
            "/skills": self._cmd_skills,
            "/skill": self._cmd_skills,
            "/hora": self._cmd_time,
            "/tiempo": self._cmd_time,
            "/personalidad": self._cmd_personality,
            "/backend": self._cmd_backend,
            "/model": self._cmd_model,
            "/agent": self._cmd_agent,
            "/export": self._cmd_export,
            "/version": self._cmd_version,
            "/update": self._cmd_update,
            "/verbose": self._cmd_verbose,
            # Comandos de aprendizaje directo (sin SLM)
            "/buscar": self._cmd_search,
            "/aprende": self._cmd_learn,
            "/aprende-web": self._cmd_learn_web,
            "/recuerda": self._cmd_remember,
            "/analiza": self._cmd_analyze,
            "/limpiar-web": self._cmd_clean_web,
            "/agent": self._cmd_agent,
            # Comandos de Notebook Guide
            "/documento": self._cmd_ingest,
            "/ingiere": self._cmd_ingest,
            "/guia": self._cmd_guide,
            "/faq": self._cmd_faq,
            # Herramientas externas
            "/renombrar": self._cmd_renombrar,
            "/renombrar-pdf": self._cmd_renombrar,
        }

        handler = commands.get(cmd.split()[0])
        if handler:
            handler(cmd)
        else:
            print(f"{Color.RED}Comando desconocido: {cmd}{Color.RESET}")
            print(f"  Usa {Color.GREEN}/help{Color.RESET} para ver comandos disponibles.")

    def _cmd_help(self, cmd: str = ""):
        print(f"""
{Color.CYAN}╔══ Comandos de Nexus ══╗{Color.RESET}
{Color.GREEN}/help{Color.RESET}         Muestra esta ayuda
{Color.GREEN}/status{Color.RESET}       Estado completo del sistema
{Color.GREEN}/stats{Color.RESET}        Estadísticas de memoria
{Color.GREEN}/fase{Color.RESET}         Progreso de evolución
{Color.GREEN}/hora{Color.RESET}         Fecha y hora actual
{Color.GREEN}/memoria{Color.RESET}      Últimos recuerdos
{Color.GREEN}/hechos{Color.RESET}       Hechos aprendidos
{Color.GREEN}/olvida{Color.RESET}       Borrar un hecho de la memoria
{Color.GREEN}/skills{Color.RESET}       Skills cargadas
{Color.GREEN}/personalidad{Color.RESET} Ver/ajustar personalidad
{Color.GREEN}/backend{Color.RESET}      Cambiar backend (symbolic/slm)
{Color.GREEN}/export{Color.RESET}       Exportar estado como JSON
{Color.GREEN}/version{Color.RESET}      Versión, commit y build info
{Color.GREEN}/model{Color.RESET}        Cambiar backend/modelo (opencode, ollama, llamacpp)
{Color.GREEN}/update{Color.RESET}       git pull desde GitHub
{Color.GREEN}/clear{Color.RESET}        Limpiar pantalla
{Color.GREEN}/reset{Color.RESET}        Resetear Nexus
{Color.GREEN}/exit{Color.RESET}         Salir
{Color.GREEN}/renombrar{Color.RESET}    Renombrar PDFs según proveedor+fecha
{Color.DIM}─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─{Color.RESET}
{Color.CYAN}Comandos de aprendizaje (sin SLM):{Color.RESET}
{Color.GREEN}/buscar{Color.RESET} <q>    Web search + auto-aprende
{Color.GREEN}/aprende{Color.RESET} <h>   Guardar hecho directo
{Color.GREEN}/aprende-web{Color.RESET} <tema>   Buscar y aprender sobre tema
{Color.GREEN}/recuerda{Color.RESET} <h>  Alias de /aprende
{Color.GREEN}/analiza{Color.RESET} <txt> Extraer hechos de un texto
{Color.GREEN}/olvida{Color.RESET} <txt>  Borrar hecho de la memoria
{Color.GREEN}/limpiar-web{Color.RESET}    Borrar hechos de web/GitHub contaminados
{Color.GREEN}/agent{Color.RESET} <tarea> Encadenar tools (investigar, explicar, etc)

{Color.DIM}Tip: Para enseñar algo a Nexus, escribe:{Color.RESET}
  "aprende que [hecho]"
  "Nexus, recuerda que [información]"
        """)

    def _cmd_status(self, cmd: str = ""):
        s = self.core.state.get_snapshot()
        n = s['nexus']
        p = s['personality']
        c = s['capabilities']
        perf = s['performance']

        print(f"""
{Color.CYAN}╔══ Estado de Nexus ══╗{Color.RESET}
  {Color.YELLOW}Fase:{Color.RESET} {n['phase']}  v{n['version']}
  {Color.YELLOW}Backend:{Color.RESET} {c['backend']}  SLM: {c['slm_loaded']}
  {Color.YELLOW}Interacciones:{Color.RESET} {n['total_interactions']}
  {Color.YELLOW}Confianza:{Color.RESET} {n['confidence_level']:.1%}
  {Color.YELLOW}Activo:{Color.RESET} {n['awake_time']//3600:.0f}h {(n['awake_time']%3600)//60:.0f}m

  {Color.YELLOW}Personalidad:{Color.RESET} {p['tone']} | formalidad: {p['formality']:.0%}
  {Color.YELLOW}Rendimiento:{Color.RESET} Ø {perf['avg_response_time_ms']:.0f}ms
  {Color.YELLOW}Aciertos:{Color.RESET} {perf['successful_responses']}/{perf['responses_given'] or 1}

  {Color.YELLOW}Skills:{Color.RESET} {n['total_skills']} | Hechos: {n['total_learned_facts']}
        """)

    def _cmd_stats(self, cmd: str = ""):
        mem_stats = self.core.memory.stats()
        print(f"""
{Color.CYAN}╔══ Estadísticas de Memoria ══╗{Color.RESET}
  {Color.YELLOW}Recuerdos episódicos:{Color.RESET} {mem_stats.get('episodic', 0)}
  {Color.YELLOW}Hechos semánticos:{Color.RESET}   {mem_stats.get('semantic', 0)}
  {Color.YELLOW}Patrones procedurales:{Color.RESET}{mem_stats.get('procedural', 0)}
  {Color.YELLOW}Total:{Color.RESET}               {mem_stats.get('total', 0)}
        """)

    def _cmd_phase(self, cmd: str = ""):
        s = self.core.state.get_snapshot()
        phase = s['nexus']['phase']
        interactions = s['nexus']['total_interactions']
        phase_order = ["Proto", "Básico", "Intermedio", "Avanzado", "Pro"]
        next_phase = "Máximo"
        remaining = 0
        try:
            idx = phase_order.index(phase)
            if idx < len(phase_order) - 1:
                next_phase = phase_order[idx + 1]
                thresholds = {"Proto": 10, "Básico": 50, "Intermedio": 200, "Avanzado": 500}
                remaining = thresholds.get(phase, 0) - interactions
        except ValueError:
            pass
        bar_len = 25
        if phase == "Pro":
            filled = bar_len
        else:
            filled = min(bar_len, max(0, int(interactions / max(thresholds.get(phase, 50), 1) * bar_len)))
        bar = "█" * filled + "░" * (bar_len - filled)

        print(f"""
{Color.CYAN}╔══ Evolución ══╗{Color.RESET}
  {Color.YELLOW}Fase actual:{Color.RESET} {Color.rgb(0, 255, 200)}{phase}{Color.RESET}
  {Color.YELLOW}Interacciones:{Color.RESET} {interactions}
  {Color.YELLOW}Progreso:{Color.RESET} [{Color.GREEN}{bar}{Color.RESET}]
  {Color.YELLOW}Siguiente:{Color.RESET} {next_phase}{f' ({max(0, remaining)} interacciones restantes)' if remaining > 0 else ''}
        """)

    def _cmd_time(self, cmd: str = ""):
        import time as tm
        now = tm.localtime()
        fecha = f"{now.tm_mday}/{now.tm_mon}/{now.tm_year}"
        hora = f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
        print(f"\n{Color.CYAN}╔══ Hora actual ══╗{Color.RESET}")
        print(f"  {Color.YELLOW}{hora}{Color.RESET} del {Color.GREEN}{fecha}{Color.RESET}")
        print()

    def _cmd_memory(self, cmd: str = ""):
        recent = self.core.memory.get_recent(limit=10)
        if not recent:
            print(f"{Color.DIM}Aún no hay recuerdos. Háblame para empezar a recordar.{Color.RESET}")
            return
        print(f"\n{Color.CYAN}╔══ Últimos recuerdos ══╗{Color.RESET}")
        for r in recent:
            role_icon = "🧑" if r['role'] == 'user' else "🤖"
            content = r['content'][:70]
            print(f"  {role_icon} {content}")
        print()

    def _cmd_agent(self, cmd: str = ""):
        """Comando /agent que encadena tools automaticamente.

        Similar a Hermes Agent: el agente orquesta web_search +
        browse_url + read_file en secuencia para tareas complejas.

        Uso:
          /agent investiga sobre la fotosintesis
          /agent explica como funciona X
          /agent documenta el API REST
          /agent busca en codigo la funcion X

        Tipos de tareas (detectadas automaticamente):
          - investigar: web_search + learn
          - explicar: web_search + browse_url + learn
          - documentar: web_search + search_files
          - buscar en codigo: search_files + read_file
        """
        task = cmd.replace("/agent", "", 1).strip()
        if not task:
            print(f"{Color.YELLOW}Uso: /agent <tarea>{Color.RESET}")
            print(f"  Ejemplos:")
            print(f"    /agent investiga sobre la fotosintesis")
            print(f"    /agent explica como funciona el aprendizaje automatico")
            print(f"    /agent documenta la arquitectura de Nexus")
            print(f"    /agent busca en codigo la funcion query_knowledge")
            return

        print(f"{Color.CYAN}Ejecutando agente: '{task}'{Color.RESET}")
        print()

        try:
            from cognition.agent import NexusAgent
            agent = NexusAgent(self.core)
            result = agent.run(task)

            if not result.success:
                print(f"{Color.RED}Error: {result.error}{Color.RESET}")
                return

            # Mostrar pasos ejecutados
            for i, step in enumerate(result.steps, 1):
                status = f"{Color.GREEN}OK{Color.RESET}" if step.success else f"{Color.RED}FAIL{Color.RESET}"
                print(f"  {Color.DIM}[{i}]{Color.RESET} {step.tool} → {status} ({step.duration_ms}ms)")

            # Mostrar resumen
            print()
            print(f"{Color.GREEN}Resumen:{Color.RESET}")
            if result.facts_learned > 0:
                print(f"  📚 Aprendi {result.facts_learned} hechos nuevos")
            print(f"  Pasos ejecutados: {len(result.steps)}")

            # ─── RESPUESTA FINAL destacada ───
            # Buscar el paso de sintesis (siempre al final si existe)
            synth_step = None
            for s in reversed(result.steps):
                if s.tool == "synthesize" and s.success:
                    synth_step = s
                    break

            if synth_step:
                print()
                print(f"{Color.CYAN}{'═' * 60}{Color.RESET}")
                print(f"{Color.CYAN}{Color.BOLD}📝 RESPUESTA:{Color.RESET}")
                print(f"{Color.CYAN}{'═' * 60}{Color.RESET}")
                # Mostrar la respuesta en bloques
                response = synth_step.output.strip()
                for line in response.split("\n"):
                    if line.startswith("# "):
                        print(f"\n{Color.BOLD}{line[2:]}{Color.RESET}")
                    elif line.startswith("Fuentes:"):
                        print(f"\n{Color.DIM}{line}{Color.RESET}")
                    elif line.startswith("  - ") and "http" in line:
                        print(f"{Color.DIM}{line}{Color.RESET}")
                    elif line.startswith("- "):
                        print(f"  {line}")
                    else:
                        print(line)
                print()
            else:
                print()

            # Mostrar preview de cada paso (excepto synthesize que ya se mostro)
            steps_to_show = [s for s in result.steps if s.tool != "synthesize"]
            if steps_to_show:
                print(f"{Color.DIM}--- Pasos ejecutados ---{Color.RESET}")
            for i, step in enumerate(steps_to_show, 1):
                status_icon = "✓" if step.success else "✗"
                print(f"{Color.DIM}[{i}]{Color.RESET} {step.tool} → {status_icon} ({step.duration_ms}ms)")

                # Limpiar output: quitar dicts raw, mostrar solo texto
                output = step.output
                if not output or len(output) < 20:
                    print(f"  {Color.DIM}(sin contenido){Color.RESET}")
                else:
                    # Detectar formato dict {'resultados': [...]}
                    import re as _re
                    if "'resultados':" in output or '"resultados":' in output:
                        # Extraer items • del dict
                        items = _re.findall(r"['\"](•[^'\"]{15,})['\"]", output)
                        if items:
                            for item in items[:3]:
                                # Limpiar el item
                                clean = item.lstrip('•').strip()
                                if len(clean) > 200:
                                    clean = clean[:200] + "..."
                                print(f"  {Color.CYAN}•{Color.RESET} {clean[:200]}")
                            if len(items) > 3:
                                print(f"  {Color.DIM}... y {len(items) - 3} mas{Color.RESET}")
                        else:
                            print(f"  {Color.DIM}{output[:300]}{Color.RESET}")
                    else:
                        # Output de read_file, browse_website, etc
                        preview = output[:400]
                        if len(output) > 400:
                            preview += f" {Color.DIM}...{Color.RESET}"
                        print(f"  {Color.DIM}{preview}{Color.RESET}")
                print()

        except Exception as e:
            print(f"{Color.RED}Error ejecutando agente: {e}{Color.RESET}")

    def _cmd_clean_web(self, cmd: str = ""):
        """Borra los hechos aprendidos de la web que son nombres de repos/URLs.

        A veces las busquedas web (especialmente GitHub) devuelven resultados
        que NO son definiciones. Este comando limpia la memoria de esos
        falsos positivos para evitar que contaminen futuras respuestas.
        """
        # Acceder directamente a la BD para tener acceso a todos los hechos
        cur = self.core.memory.semantic.conn.cursor()
        cur.execute(
            "SELECT id, fact, category, confidence, source FROM semantic"
        )
        rows = cur.fetchall()

        deleted = 0
        for row in rows:
            fact_id = row[0]
            text = row[1] or ""
            category = row[2] or ""
            source = row[4] or ""
            # Criterios para borrar
            is_repo_format = " ⭐" in text and " — " in text
            is_url_only = text.startswith("http")
            is_github = "github.com" in text.lower() and len(text) < 200
            is_auto_web_github = source == "auto_web" and ("github.com" in text.lower() or " ⭐" in text)
            is_short_asiento = len(text) < 40 and "asiento" in text.lower()
            # Hechos inutiles que el SLM alucina como "que son X"
            is_query_echo = text.lower().startswith("que son ") or text.lower().startswith("qué son ")
            # Tambien borrar si el texto es solo un "que" + pregunta corta
            is_question_echo = text.endswith("?") and len(text) < 60
            # Hechos auto_web que NO parecen definiciones (sin verbos clave)
            has_definition_verb = any(v in text.lower() for v in [
                " es ", " son ", " fue ", " es un ", " es una ",
                " significa ", " consiste ", " permite ", " realiza ",
                " proceso ", " forma ", " tipo ", " clase ", " metodo ",
            ])
            # Hechos auto_web que NO parecen definiciones (sin verbos clave)
            has_definition_verb = any(v in text.lower() for v in [
                " es ", " son ", " fue ", " es un ", " es una ",
                " significa ", " consiste ", " permite ", " realiza ",
                " proceso ", " forma ", " tipo ", " clase ", " metodo ",
            ])
            # Hechos auto_web sin verbos de definicion Y cortos = ruido
            is_auto_web_noise = (
                source == "auto_web"
                and len(text) < 100
                and not has_definition_verb
            )
            if (is_repo_format or is_url_only or is_github or
                is_auto_web_github or is_short_asiento or
                is_query_echo or is_question_echo or
                is_auto_web_noise):
                self.core.memory.semantic.conn.execute(
                    "DELETE FROM semantic WHERE id = ?", (fact_id,)
                )
                self.core.memory.semantic.conn.commit()
                deleted += 1
                print(f"  {Color.DIM}Borrado: {text[:80]}{Color.RESET}")
        if deleted:
            print(f"\n{Color.GREEN}✓ {deleted} hechos borrados (contaminados de web/GitHub){Color.RESET}")
        else:
            print(f"{Color.YELLOW}No se encontraron hechos para limpiar{Color.RESET}")

    def _cmd_facts(self, cmd: str = ""):
        # Extraer categoría del comando si se especifica
        parts = cmd.split()
        category = parts[1] if len(parts) > 1 else None
        if category:
            facts = self.core.memory.get_facts_by_category(category)
        else:
            # Todos los hechos - usar query vacío para obtener todos
            facts = self.core.memory.semantic.query_knowledge("", top_k=50)
        
        if not facts:
            print(f"{Color.DIM}Aún no hay hechos aprendidos.{Color.RESET}")
            return
        
        print(f"\n{Color.CYAN}╔══ Hechos aprendidos ({len(facts)}) ══╗{Color.RESET}")
        for i, f in enumerate(facts, 1):
            if isinstance(f, dict):
                text = f.get('fact', f.get('text', ''))
                conf = f.get('confidence', f.get('metadata', {}).get('confidence', 0))
                cat = f.get('category', f.get('metadata', {}).get('category', '?'))
                print(f"  {i:2d}. {Color.GREEN}[{cat}]{Color.RESET} {text[:80]} "
                      f"{Color.DIM}({conf:.0%}){Color.RESET}")
        print()

    def _cmd_skills(self, cmd: str = ""):
        skills = self.core.skills.list(active_only=True)
        if not skills:
            print(f"{Color.DIM}No hay skills cargadas.{Color.RESET}")
            return
        print(f"\n{Color.CYAN}╔══ Skills Cargadas ══╗{Color.RESET}")
        for skill in skills:
            info = skill.get_specs()
            print(f"  {Color.GREEN}{info['name']}{Color.RESET} v{info['version']}")
            print(f"    {Color.DIM}{info['description']}{Color.RESET}")
            for action in info.get('actions', []):
                # Buscar la acción para obtener descripción
                act = skill.actions.get(action)
                desc = f" — {act.description}" if act else ""
                print(f"    {Color.YELLOW}→{Color.RESET} {action}{Color.DIM}{desc[:50]}{Color.RESET}")
            print()
        print()

    def _cmd_personality(self, cmd: str = ""):
        p = self.core.state.get("personality", default={})
        
        # Detectar cambios inline
        parts = cmd.split()
        changes = {}
        for i, part in enumerate(parts):
            if part in ["tono", "tone"] and i + 1 < len(parts):
                changes["tone"] = parts[i + 1]
            elif part in ["formalidad", "formality"] and i + 1 < len(parts):
                try:
                    changes["formality"] = float(parts[i + 1])
                except:
                    pass
            elif part in ["curiosidad", "curiosity"] and i + 1 < len(parts):
                try:
                    changes["curiosity"] = float(parts[i + 1])
                except:
                    pass
            elif part in ["creatividad", "creativity"] and i + 1 < len(parts):
                try:
                    changes["creativity"] = float(parts[i + 1])
                except:
                    pass
        
        if changes:
            for key, value in changes.items():
                self.core.state.set("personality", key, value=value)
            p = self.core.state.get("personality", default={})

        print(f"""
{Color.CYAN}╔══ Personalidad ══╗{Color.RESET}
  {Color.YELLOW}Tono:{Color.RESET}        {p.get('tone', 'analytical')}
  {Color.YELLOW}Formalidad:{Color.RESET}  {p.get('formality', 0.5):.0%}
  {Color.YELLOW}Curiosidad:{Color.RESET}  {p.get('curiosity', 0.7):.0%}
  {Color.YELLOW}Creatividad:{Color.RESET} {p.get('creativity', 0.4):.0%}
{Color.DIM}
  Para cambiar: /personalidad tono friendly
  Valores: tono (analytical|friendly|playful|professional)
           formalidad (0.0-1.0) curiosidad (0.0-1.0) creatividad (0.0-1.0)
{Color.RESET}""")

    def _cmd_backend(self, cmd: str = ""):
        parts = cmd.split()
        if len(parts) > 1:
            new_backend = parts[1]
            if new_backend in ["symbolic", "slm", "hybrid"]:
                self.core.state.set("capabilities", "backend", value=new_backend)
                print(f"{Color.GREEN}Backend cambiado a: {new_backend}{Color.RESET}")
                if new_backend == "slm" and not self.core.slm.loaded:
                    print(f"{Color.YELLOW}⚠ SLM no está cargado. Usa /slm load para cargarlo.{Color.RESET}")
            else:
                print(f"{Color.RED}Backend inválido. Opciones: symbolic, slm, hybrid{Color.RESET}")
            return

        current = self.core.state.get("capabilities", "backend", default="symbolic")
        print(f"""
{Color.CYAN}╔══ Backend ══╗{Color.RESET}
  Actual: {Color.GREEN}{current}{Color.RESET}
  Opciones: {Color.YELLOW}symbolic{Color.RESET} (sin modelo),
           {Color.YELLOW}slm{Color.RESET} (modelo local),
           {Color.YELLOW}hybrid{Color.RESET} (combinado)""")
        if self.core.slm:
            slm_info = self.core.slm.get_info()
            print(f"  SLM: {'🟢 cargado' if slm_info['loaded'] else '🔴 no cargado'}")
            print(f"  Modo: {slm_info['mode']} | Modelo: {slm_info['model']}")
        print(f"\n{Color.DIM}Usa /model para cambiar backend + modelo.{Color.RESET}\n")

    def _cmd_model(self, cmd: str = ""):
        """Comando /model para cambiar backend + modelo sin tocar config.

        Uso:
          /model                          # muestra config actual
          /model list                     # muestra backends disponibles
          /model use opencode             # cambia a OpenCode Go
          /model use ollama qwen2.5:1.5b  # cambia a Ollama con modelo
          /model test [pregunta]          # compara todos los backends
        """
        parts = cmd.split()
        subcommand = parts[1] if len(parts) > 1 else "show"

        if subcommand in ("help", "?"):
            self._print_model_help()
            return

        if subcommand == "list":
            self._print_model_list()
            return

        if subcommand == "test":
            test_query = " ".join(parts[2:]) if len(parts) > 2 else "explicame brevemente que es la fotosintesis"
            self._run_model_comparison(test_query)
            return

        if subcommand == "use":
            if len(parts) < 3:
                # Sin argumentos: menu interactivo
                self._model_interactive_menu()
                return
            backend = parts[2].lower()
            model_name = parts[3] if len(parts) > 3 else None
            self._switch_model(backend, model_name)
            return

        if subcommand == "show":
            if HAS_INTERACTIVE_MENU:
                opts = [
                    "Ver modelo actual",
                    "Lista modelos instalados",
                    "Cambiar modelo (interactivo)",
                    "Cambio rapido directo",
                    "Comparar backends",
                ]
                choice = interactive_menu("Gestion de Modelos", opts)
                if choice == 0:
                    self._show_current_model()
                elif choice == 1:
                    self._print_model_list()
                elif choice == 2:
                    self._model_interactive_menu()
                elif choice == 3:
                    print(f"{Color.YELLOW}Uso: /model use <backend> [modelo]{Color.RESET}")
                    print(f"  Ej: /model use ollama hermes3:3b")
                elif choice == 4:
                    query = input(f"  {Color.DIM}Pregunta de prueba (Enter = default):{Color.RESET} ").strip()
                    if not query:
                        query = "explicame brevemente que es la fotosintesis"
                    self._run_model_comparison(query)
                return
            else:
                # Fallback sin interactive_menu
                self._show_current_model()
                print(f"{Color.DIM}/model list | /model use | /model test{Color.RESET}")
            return

        print(f"{Color.RED}Subcomando desconocido: {subcommand}{Color.RESET}")
        self._print_model_help()

    def _print_model_help(self):
        print(f"""
{Color.CYAN}╔══ /model — Gestión de Modelos ══╗{Color.RESET}

  {Color.YELLOW}/model{Color.RESET}                          Muestra modelo actual
  {Color.YELLOW}/model list{Color.RESET}                     Lista modelos instalados (dinamico)
  {Color.YELLOW}/model use{Color.RESET}                      Menu interactivo para elegir modelo
  {Color.YELLOW}/model use <backend> [modelo]{Color.RESET}   Cambiar directo
  {Color.YELLOW}/model test [pregunta]{Color.RESET}          Compara todos los backends

{Color.DIM}Persiste en data/state/nexus_state.json (sobrevive entre sesiones).{Color.RESET}
        """)

    def _print_model_list(self):
        print(f"""
{Color.CYAN}╔══ Backends disponibles ══╗{Color.RESET}

  {Color.YELLOW}opencode{Color.RESET}    OpenCode Go (Nous Research)
           Endpoint: https://opencode.ai/zen/go/v1
           API key: $OPENCODE_GO_API_KEY
           Modelo: deepseek-v4-flash (default)
           Rapido, cloud, gratis con API key

  {Color.YELLOW}ollama{Color.RESET}      Ollama local (offline, privado, ilimitado)
           Endpoint: http://localhost:11434/v1
           Modelos instalados:""")
        # Mostrar modelos reales de Ollama
        installed = self._get_installed_ollama_models()
        if installed:
            for name, size_bytes, params in installed:
                size_gb = size_bytes / (1024**3)
                param_str = f"{params}" if params and params != "?" else ""
                print(f"           • {Color.GREEN}{name}{Color.RESET} ({size_gb:.1f} GB{f', {param_str}' if param_str else ''})")
        else:
            print(f"           {Color.GRAY}(Ollama no detectado o sin modelos){Color.RESET}")
        print(f"""
  {Color.YELLOW}llamacpp{Color.RESET}    llama.cpp server (avanzado)
           Endpoint: http://localhost:8713/v1
           Requiere: model_path en config.py

  {Color.YELLOW}symbolic{Color.RESET}    Solo motor simbolico (sin SLM)
           No usa modelo, solo reglas + memoria
        """)

    def _show_current_model(self):
        s = self.core.state.get_snapshot()
        cap = s.get("capabilities", {})
        backend_mode = cap.get("backend", "symbolic")
        slm = self.core.slm

        print(f"""
{Color.CYAN}╔══ Modelo Actual ══╗{Color.RESET}

  {Color.YELLOW}Modo de operacion:{Color.RESET}   {backend_mode}
  {Color.YELLOW}SLM cargado:{Color.RESET}        {'🟢 Si' if slm and slm.loaded else '🔴 No'}""")
        if slm and slm.loaded:
            info = slm.get_info()
            print(f"  {Color.YELLOW}Backend SLM:{Color.RESET}       {info['mode']}")
            print(f"  {Color.YELLOW}Modelo:{Color.RESET}            {info['model']}")
            print(f"  {Color.YELLOW}Temperatura:{Color.RESET}       {info['temperature']}")
            print(f"  {Color.YELLOW}Max tokens:{Color.RESET}        {info['max_tokens']}")

        # Persistido
        model_state = s.get("model_state", {})
        if model_state:
            print(f"\n  {Color.DIM}Persistente (sobrevive entre sesiones):{Color.RESET}")
            print(f"    Backend: {model_state.get('backend', '?')}")
            print(f"    Modelo:  {model_state.get('model_name', '?')}")
        print()

    def _model_interactive_menu(self):
        """Menu interactivo con teclado para seleccionar modelo."""
        installed = self._get_installed_ollama_models()
        chat_models = [(n, s, p) for n, s, p in installed if "embed" not in n.lower()]
        
        opts = ["OpenCode Go (cloud) — deepseek-v4-flash"]
        for name, size_bytes, params in chat_models:
            size_gb = size_bytes / (1024**3)
            param_str = f"{params}" if params and params != "?" else "?"
            opts.append(f"{name} ({size_gb:.1f}GB, {param_str})")
        opts.append("Solo motor simbolico (sin modelo)")
        
        if HAS_INTERACTIVE_MENU:
            choice = interactive_menu("Seleccion de Modelo", opts)
            if choice is None:
                return
            if choice == 0:
                self._switch_model("opencode", "deepseek-v4-flash")
            elif choice == len(opts) - 1:
                self._switch_model("symbolic")
            elif 1 <= choice < len(opts) - 1:
                model_name = chat_models[choice - 1][0]
                self._switch_model("ollama", model_name)
        else:
            # Fallback: menu numerado simple
            print(f"""
{Color.CYAN}╔══ Seleccion de Modelo ══╗{Color.RESET}
  1) OpenCode Go (cloud) — deepseek-v4-flash""")
            for i, (name, size_bytes, params) in enumerate(chat_models, 2):
                size_gb = size_bytes / (1024**3)
                print(f"  {i}) {Color.GREEN}{name}{Color.RESET} ({size_gb:.1f}GB)")
            print(f"  {len(chat_models)+2}) Solo motor simbolico")
            try:
                c = input(f"  {Color.YELLOW}Elige →{Color.RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if c.isdigit():
                idx = int(c)
                if idx == 1: self._switch_model("opencode", "deepseek-v4-flash")
                elif idx == len(chat_models)+2: self._switch_model("symbolic")
                elif 2 <= idx <= len(chat_models)+1: self._switch_model("ollama", chat_models[idx-2][0])

    def _switch_model(self, backend: str, model_name: str | None):
        """Cambia el backend SLM y persiste en el estado."""
        import config as _cfg
        import importlib

        # Mapear aliases a backend real
        backend_aliases = {
            "opencode": "openai",  # OpenCode Go usa API compatible OpenAI
            "ollama": "ollama",
            "llamacpp": "llamacpp",
            "llama.cpp": "llamacpp",
            "symbolic": None,  # sin SLM
        }
        real_backend = backend_aliases.get(backend)
        if real_backend is None and backend != "symbolic":
            print(f"{Color.RED}Backend desconocido: {backend}{Color.RESET}")
            print(f"  Disponibles: opencode, ollama, llamacpp, symbolic")
            return

        # Configurar segun backend
        if backend == "symbolic":
            _cfg.ENGINE["llm"]["backend"] = None
            _cfg.ENGINE["llm"]["model_name"] = "ninguno"
            self.core.state.set("capabilities", "slm_loaded", value=False)
            self.core.state.set("capabilities", "backend", value="symbolic")
            self.core.state.set("model_state", "backend", value="symbolic")
            self.core.state.set("model_state", "model_name", value="ninguno")
            print(f"{Color.GREEN}✓ Modo cambiado a: symbolic (sin SLM){Color.RESET}")
            return

        # OpenCode
        if backend == "opencode":
            _cfg.ENGINE["llm"]["backend"] = "openai"
            _cfg.ENGINE["llm"]["api_base"] = "https://opencode.ai/zen/go/v1"
            if not model_name:
                model_name = "deepseek-v4-flash"
            _cfg.ENGINE["llm"]["model_name"] = model_name
            _cfg.ENGINE["llm"]["api_key"] = None  # leer de env var

        # Ollama
        elif backend == "ollama":
            _cfg.ENGINE["llm"]["backend"] = "ollama"
            _cfg.ENGINE["llm"]["api_base"] = "http://localhost:11434/v1"
            if not model_name:
                model_name = "qwen2.5:0.5b"
            _cfg.ENGINE["llm"]["model_name"] = model_name
            _cfg.ENGINE["llm"]["api_key"] = "not-needed"

        # llama.cpp
        elif backend == "llamacpp":
            _cfg.ENGINE["llm"]["backend"] = "llamacpp"
            _cfg.ENGINE["llm"]["api_base"] = "http://localhost:8713/v1"
            if model_name:
                _cfg.ENGINE["llm"]["model_name"] = model_name

        # Recargar SLMBackend con la nueva config
        try:
            from cognition.slm import SLMBackend
            # Cerrar el actual
            if self.core.slm:
                try:
                    self.core.slm.unload()
                except Exception:
                    pass
            # Crear nuevo
            new_slm = SLMBackend(_cfg.ENGINE["llm"])
            new_slm.load()
            if new_slm.loaded:
                self.core.slm = new_slm
                self.core.state.set("capabilities", "slm_loaded", value=True)
                self.core.state.set("model_state", "backend", value=backend)
                self.core.state.set("model_state", "model_name", value=_cfg.ENGINE["llm"]["model_name"])
                self.core.state.set("capabilities", "backend", value="hybrid")
                print(f"{Color.GREEN}✓ Backend cambiado a: {backend} ({model_name}){Color.RESET}")
                print(f"{Color.DIM}  Persistido en estado. Sobrevive entre sesiones.{Color.RESET}")
            else:
                print(f"{Color.RED}✗ Backend {backend} no se pudo cargar{Color.RESET}")
                # Mostrar modelos disponibles si es ollama
                if backend == "ollama" and hasattr(new_slm, "_ollama_available_models"):
                    available = new_slm._ollama_available_models
                    if available:
                        print(f"  {Color.YELLOW}Modelos Ollama disponibles:{Color.RESET}")
                        for m in available[:5]:
                            print(f"    - {m}")
                        print(f"\n  {Color.DIM}Prueba: /model use ollama {available[0]}{Color.RESET}")
                    else:
                        print(f"  Verifica que el servicio este corriendo:")
                        print(f"    ollama serve (puerto 11434)")
                elif backend == "llamacpp":
                    print(f"  Verifica que el servicio este corriendo:")
                    print(f"    llama-server -m modelo.gguf (puerto 8713)")
                elif backend == "opencode":
                    print(f"  Verifica:")
                    print(f"    set OPENCODE_GO_API_KEY=tu_key")
        except Exception as e:
            print(f"{Color.RED}Error cambiando backend: {e}{Color.RESET}")

    def _run_model_comparison(self, query: str):
        """Compara el mismo query contra todos los backends disponibles."""
        import time as _t
        import urllib.request
        import urllib.error

        print(f"{Color.CYAN}Comparando backends con query:{Color.RESET} \"{query}\"\n")

        # Detectar que backends estan disponibles
        backends = []

        # 1. OpenCode: usar la misma API key que el SLM principal
        api_key = os.environ.get("OPENCODE_GO_API_KEY", "")
        oc_url = "https://opencode.ai/zen/go/v1"
        if api_key:
            backends.append((
                "opencode", oc_url, "deepseek-v4-flash", api_key
            ))

        # 2. Ollama: detectar modelos instalados via /api/tags
        ollama_url = "http://localhost:11434/v1"
        ollama_api = "http://localhost:11434/api/tags"
        installed_models = []
        try:
            req = urllib.request.Request(ollama_api, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                installed_models = [m["name"] for m in data.get("models", [])]
        except Exception:
            pass

        if installed_models:
            # Preferir modelos de chat (no embeddings)
            chat_models = [m for m in installed_models
                           if "embed" not in m.lower() and "nomic-embed" not in m.lower()]
            for m in chat_models[:3]:  # hasta 3 modelos para no demorar
                backends.append(("ollama", ollama_url, m, "not-needed"))
        else:
            print(f"  {Color.GRAY}Ollama no detectado en localhost:11434{Color.RESET}")

        if not backends:
            print(f"  {Color.RED}No hay backends disponibles{Color.RESET}")
            return

        results = []
        for backend, url, model_name, api_key_for_call in backends:
            print(f"  {Color.YELLOW}Probando {backend}/{model_name}...{Color.RESET}", end=" ", flush=True)
            start = _t.time()
            try:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 200,
                    "temperature": 0.7,
                }
                req = urllib.request.Request(
                    f"{url}/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key_for_call}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                elapsed = _t.time() - start
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("completion_tokens", 0)
                print(f"🟢 {elapsed:.2f}s, {tokens} tok")
                results.append((backend, model_name, "ok", content, elapsed))
            except urllib.error.HTTPError as e:
                elapsed = _t.time() - start
                body = e.read().decode("utf-8", errors="replace")[:80]
                print(f"🔴 HTTP {e.code}: {body}")
                results.append((backend, model_name, f"HTTP {e.code}", None, elapsed))
            except Exception as e:
                elapsed = _t.time() - start if "_t" in dir() else 0
                print(f"🔴 {type(e).__name__}: {str(e)[:60]}")
                results.append((backend, model_name, f"{type(e).__name__}", None, elapsed))

        # Resumen
        print(f"\n{Color.CYAN}╔══ Resumen ══╗{Color.RESET}")
        ok_results = [r for r in results if r[2] == "ok"]
        for backend, model, status, content, elapsed in results:
            if status == "ok":
                preview = content[:120].replace("\n", " ") if content else ""
                tps = (ok_results and len([r for r in ok_results if r[0] == backend])
                       and "") or ""
                print(f"\n  {Color.GREEN}✓ {backend}{Color.RESET} / {Color.YELLOW}{model}{Color.RESET} — {elapsed:.2f}s, {content and len(content.split())} palabras")
                print(f"    {Color.DIM}\"{preview}{'...' if content and len(content) > 120 else ''}\"{Color.RESET}")
            else:
                print(f"\n  {Color.GRAY}✗ {backend}{Color.RESET} / {model} — {status}")

        if len(ok_results) > 1:
            fastest = min(ok_results, key=lambda r: r[4])
            print(f"\n  {Color.YELLOW}→ Mas rapido: {fastest[0]}/{fastest[1]} ({fastest[4]:.2f}s){Color.RESET}")
        elif len(ok_results) == 1:
            r = ok_results[0]
            print(f"\n  {Color.YELLOW}→ Unico backend funcionando: {r[0]}/{r[1]} ({r[4]:.2f}s){Color.RESET}")
        print()

    def _cmd_export(self, cmd: str = ""):
        output = self.core.state.export_json()
        print(f"\n{Color.CYAN}╔══ Exportar Estado ══╗{Color.RESET}")
        print(output)
        print()

    def _cmd_version(self, cmd: str = ""):
        s = self.core.state.get_snapshot()
        n = s['nexus']
        ver = n.get('version', '?')
        commit = n.get('commit', '?')
        interactions = n.get('total_interactions', 0)
        phase = n.get('phase', '?')
        skills = n.get('total_skills', 0)
        print(f"""
{Color.CYAN}╔══ Versión ══╗{Color.RESET}
  {Color.YELLOW}Versión:{Color.RESET}  {ver}
  {Color.YELLOW}Commit:{Color.RESET}   #{commit}
  {Color.YELLOW}Fase:{Color.RESET}     {phase}
  {Color.YELLOW}Build:{Color.RESET}    {interactions} interacciones · {skills} skills
  {Color.YELLOW}Repo:{Color.RESET}    github.com/kudawasama/NucleoNexus
        """)

    # ─────────────────────────────────────────────────────────
    # Comando: /renombrar
    # ─────────────────────────────────────────────────────────
    def _cmd_renombrar(self, cmd: str = ""):
        """Renombra PDFs según proveedor y fecha. Uso: /renombrar <ruta>"""
        if not HAS_PDF_RENAMER:
            print(f"{Color.RED}Herramienta no disponible.{Color.RESET}")
            print(f"  Ejecuta: python tools/pdf_renamer.py \"ruta\"")
            return

        args = cmd.strip().split(maxsplit=1)
        if len(args) < 2:
            print(f"{Color.YELLOW}Uso: /renombrar <ruta>{Color.RESET}")
            print(f"  Ruta puede ser carpeta con PDFs o archivo .zip")
            print(f"  Agrega --dry-run para simular")
            print(f"  {Color.DIM}Ej: /renombrar C:/Users/joce/Downloads/Facturas.zip{Color.RESET}")
            print(f"  {Color.DIM}Ej: /renombrar C:/ruta/carpeta --dry-run{Color.RESET}")
            return

        ruta = args[1]
        dry_run = " --dry-run" in cmd or "--dry-run" in ruta
        ruta_clean = ruta.replace(" --dry-run", "").strip()

        print(f"{Color.CYAN}📄 Renombrando PDFs en: {ruta_clean}{Color.RESET}")
        time.sleep(0.3)
        pdf_renombrar(ruta_clean, dry_run=dry_run)

    # ─────────────────────────────────────────────────────────
    # Comandos de aprendizaje (capa rápida, sin SLM)
    # ─────────────────────────────────────────────────────────

    def _cmd_search(self, cmd: str = ""):
        """Busca en la web sin pasar por el SLM. Uso: /buscar <query>"""
        query = cmd.replace("/buscar", "", 1).strip()
        if not query:
            print(f"{Color.YELLOW}Uso: /buscar <query>{Color.RESET}")
            print(f"  Ejemplo: /buscar capital de francia")
            return

        print(f"{Color.CYAN}Buscando: '{query}'{Color.RESET}")
        result = self.core.actions.execute("web_search", query=query)
        if result.get("success"):
            data = result["result"]
            if isinstance(data, dict) and "resultados" in data:
                items = data["resultados"]
                fuente = data.get("fuente", "web")
                print(f"\n{Color.GREEN}Resultados ({fuente}):{Color.RESET}")
                for i, item in enumerate(items[:5], 1):
                    print(f"  {i}. {str(item)[:200]}")
                # Aprender de los resultados (auto-aprendizaje)
                learned = self.core._learn_from_web_search(query, items)
                if learned:
                    print(f"\n{Color.CYAN}📚 Aprendí {learned} hechos nuevos{Color.RESET}")
            elif isinstance(data, dict) and "mensaje" in data:
                print(f"{Color.YELLOW}{data['mensaje']}{Color.RESET}")
            else:
                print(f"{Color.GRAY}Sin resultados{Color.RESET}")
        else:
            err = result.get("error", "Error desconocido")
            print(f"{Color.RED}Error: {err}{Color.RESET}")

    def _cmd_learn(self, cmd: str = ""):
        """Aprende un hecho directo. Uso: /aprende <hecho>"""
        fact = cmd.replace("/aprende", "", 1).strip()
        if not fact:
            print(f"{Color.YELLOW}Uso: /aprende <hecho>{Color.RESET}")
            print(f"  Ejemplo: /aprende Python es un lenguaje de programacion")
            return

        # Si empieza con 'sobre', sugerir /aprende-web
        if re.match(r'^(?:sobre|acerca de|respecto a|de)\s+\w+', fact, re.IGNORECASE):
            print(f"{Color.YELLOW}Parece que quieres aprender sobre un tema.{Color.RESET}")
            print(f"  Usa: /aprende-web {fact}")
            return

        # Guardar el hecho
        self.core.memory.learn_fact(
            fact, category="aprendizaje",
            confidence=0.5, source="usuario"
        )
        print(f"{Color.GREEN}✓ Aprendido: {fact}{Color.RESET}")
        print(f"  {Color.DIM}Categoría: aprendizaje | Confianza: 0.5{Color.RESET}")

    def _cmd_learn_web(self, cmd: str = ""):
        """Busca en la web y aprende los resultados. Uso: /aprende-web <tema>"""
        topic = cmd.replace("/aprende-web", "", 1).strip()
        if not topic:
            print(f"{Color.YELLOW}Uso: /aprende-web <tema>{Color.RESET}")
            print(f"  Ejemplo: /aprende-web la revolucion francesa")
            return

        print(f"{Color.CYAN}Investigando '{topic}' en la web...{Color.RESET}")
        result = self.core.actions.execute("web_search", query=topic)
        if result.get("success"):
            data = result["result"]
            if isinstance(data, dict) and "resultados" in data:
                items = data["resultados"]
                if not items:
                    print(f"{Color.YELLOW}No encontré información sobre '{topic}'{Color.RESET}")
                    return

                # Detectar si los resultados son de GitHub
                is_github = any(
                    "github.com" in str(r).lower() or
                    (isinstance(r, str) and " ⭐" in r and " — " in r)
                    for r in items[:3]
                )

                # Extraer terminos de la query (normalizar acentos)
                stop_words = {'que', 'qué', 'es', 'son', 'las', 'los', 'una', 'uno',
                              'por', 'para', 'con', 'del', 'los', 'las', 'este', 'esta',
                              'como', 'cómo', 'sobre', 'cual', 'cuál', 'cuando', 'donde'}
                def _norm_text_cli(t):
                    out = t.lower()
                    for src, dst in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ü','u')]:
                        out = out.replace(src, dst)
                    return out
                query_terms = set()
                for word in re.findall(r'\b[a-záéíóúñü]{4,}\b', topic.lower()):
                    if word not in stop_words:
                        query_terms.add(_norm_text_cli(word))

                # Guardar los 3 mejores (filtrando GitHub)
                learned = 0
                for item in items[:3]:
                    if isinstance(item, dict):
                        text = item.get("snippet", "") or item.get("extract", "")
                        title = item.get("title", "")
                    else:
                        text = str(item)
                        title = ""
                    text = re.sub(r'<[^>]+>', '', text).strip()[:200]
                    if not text and title:
                        text = title
                    # Filtro GitHub: no guardar nombres de repos
                    is_repo = " ⭐" in text and " — " in text and "http" in text
                    if is_github or is_repo:
                        continue
                    # Filtro de relevancia: debe contener al menos un termino de la query
                    text_norm = _norm_text_cli(text)
                    if (text
                        and len(text) > 30
                        and "http" not in text[:50]
                        and (not query_terms or any(term in text_norm for term in query_terms))):
                        # ─── Procesar con el extractor ANTES de guardar ───
                        # Separa listas ("X son A, B, C") en items
                        from learning.extractor import extract_facts_from_text
                        extracted = extract_facts_from_text(text)
                        if extracted:
                            for ex_fact in extracted[:3]:
                                if len(ex_fact) > 15:
                                    self.core.memory.learn_fact(
                                        ex_fact, category=f"aprendido_{topic[:15]}",
                                        confidence=0.5, source="auto_web"
                                    )
                                    learned += 1
                        else:
                            # Fallback: guardar el snippet tal cual
                            self.core.memory.learn_fact(
                                text, category=f"aprendido_{topic[:15]}",
                                confidence=0.5, source="auto_web"
                            )
                            learned += 1
                if is_github:
                    print(f"\n{Color.YELLOW}Nota: Los resultados son de GitHub, no se guardaron{Color.RESET}")
                print(f"\n{Color.GREEN}✓ Aprendí {learned} hechos sobre '{topic}':{Color.RESET}")
                for i, item in enumerate(items[:3], 1):
                    print(f"  {i}. {str(item)[:200]}")
                print(f"\n{Color.CYAN}Próxima vez que preguntes sobre esto, "
                      f"responderé desde mi memoria.{Color.RESET}")
            else:
                print(f"{Color.GRAY}Sin resultados{Color.RESET}")
        else:
            err = result.get("error", "Error desconocido")
            print(f"{Color.RED}Error: {err}{Color.RESET}")

    def _cmd_remember(self, cmd: str = ""):
        """Alias de /aprende. Uso: /recuerda <hecho>"""
        self._cmd_learn(cmd.replace("/recuerda", "/aprende", 1))

    def _cmd_analyze(self, cmd: str = ""):
        """Analiza un texto y extrae hechos. Uso: /analiza <texto>"""
        text = cmd.replace("/analiza", "", 1).strip()
        if not text:
            print(f"{Color.YELLOW}Uso: /analiza <texto>{Color.RESET}")
            print(f"  Ejemplo: /analiza el riñon filtra la sangre")
            return

        from learning.extractor import extract_facts_from_text
        facts = extract_facts_from_text(text)
        if not facts:
            print(f"{Color.YELLOW}No extraje hechos del texto.{Color.RESET}")
            return

        print(f"{Color.CYAN}Hechos extraídos ({len(facts)}):{Color.RESET}")
        for i, f in enumerate(facts, 1):
            print(f"  {i}. {f}")
        # Guardarlos
        for f in facts:
            self.core.memory.learn_fact(
                f, category="extraccion",
                confidence=0.4, source="auto_analisis"
            )
        print(f"\n{Color.GREEN}✓ {len(facts)} hechos guardados{Color.RESET}")

    def _cmd_forget(self, cmd: str = ""):
        """Borra un hecho de la memoria. Uso: /olvida <texto>"""
        text = cmd.replace("/olvida", "", 1).strip()
        if not text:
            print(f"{Color.YELLOW}Uso: /olvida <texto_a_borrar>{Color.RESET}")
            print(f"  Borrara los hechos que coincidan con el texto")
            return

        # Buscar hechos similares
        facts = self.core.memory.semantic.query_knowledge(text, top_k=10)
        if not facts:
            print(f"{Color.YELLOW}No encontré hechos sobre '{text}'{Color.RESET}")
            return

        # Borrar los que coincidan bien
        deleted = 0
        for fact in facts:
            fact_text = fact.get("text", "") or fact.get("fact", "")
            fact_id = fact.get("id")
            if not fact_id:
                continue
            if text.lower() in fact_text.lower() or fact_text.lower() in text.lower():
                # Borrar de la BD directamente
                self.core.memory.semantic.conn.execute(
                    "DELETE FROM semantic WHERE id = ?", (fact_id,)
                )
                self.core.memory.semantic.conn.commit()
                deleted += 1
                print(f"  {Color.DIM}Borrado: {fact_text[:80]}{Color.RESET}")
        if deleted:
            print(f"\n{Color.GREEN}✓ {deleted} hechos borrados{Color.RESET}")
        else:
            print(f"{Color.YELLOW}No borré nada (los hechos no coinciden){Color.RESET}")

    def _cmd_verbose(self, cmd: str = ""):
        """Alterna el modo verbose (mostrar logs de INFO en pantalla).

        Por defecto, los logs solo van al archivo. Con /verbose, tambien
        aparecen en la terminal (stderr). Util para debug.
        """
        import logging as _log
        # Leer estado actual del root logger
        root = _log.getLogger()
        has_stream_handler = any(
            isinstance(h, _log.StreamHandler) and not isinstance(h, _log.NullHandler)
            for h in root.handlers
        )

        if has_stream_handler:
            # Apagar: poner NullHandler en lugar de StreamHandler
            for h in list(root.handlers):
                if isinstance(h, _log.StreamHandler):
                    root.removeHandler(h)
            root.addHandler(_log.NullHandler())
            print(f"{Color.GREEN}✓ Modo verbose: OFF{Color.RESET}")
            print(f"  {Color.DIM}Los logs solo van al archivo.{Color.RESET}")
        else:
            # Encender: agregar StreamHandler a stderr
            for h in list(root.handlers):
                if isinstance(h, _log.NullHandler):
                    root.removeHandler(h)
            sh = _log.StreamHandler()
            sh.setFormatter(_log.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            root.addHandler(sh)
            print(f"{Color.GREEN}✓ Modo verbose: ON{Color.RESET}")
            print(f"  {Color.DIM}Los logs ahora se ven en la terminal (stderr).{Color.RESET}")

    def _cmd_update(self, cmd: str = ""):
        """Actualiza Nexus via git pull."""
        import subprocess as _sp
        print(f"{Color.YELLOW}Actualizando Nexus desde GitHub...{Color.RESET}")
        try:
            # Capturar SHA antes del pull
            sha_before = ""
            try:
                with open(Path(__file__).parent.parent / ".git" / "refs" / "heads" / "master", "r") as _f:
                    sha_before = _f.read().strip()[:7]
            except Exception:
                pass

            result = _sp.run(
                ["git", "pull", "origin", "master"],
                capture_output=True, text=True, timeout=30,
                cwd=Path(__file__).parent.parent,
            )
            if result.returncode != 0:
                print(f"{Color.RED}Error al actualizar:{Color.RESET}")
                print(f"  {result.stderr.strip()}")
                return

            output = result.stdout.strip()
            # Detectar tipo de cambio en el output de git pull
            if "Already up to date" in output or "ya está actualizado" in output:
                print(f"{Color.GREEN}✓ No hay cambios. Nexus ya esta en la ultima version (#{sha_before}).{Color.RESET}")
                return

            # Capturar SHA despues del pull
            sha_after = sha_before
            try:
                with open(Path(__file__).parent.parent / ".git" / "refs" / "heads" / "master", "r") as _f:
                    sha_after = _f.read().strip()[:7]
            except Exception:
                pass

            # Parsear commits descargados
            changes = []
            for line in output.splitlines():
                # Formato: " Fast-forward  | 1 file changed, 2 insertions(+), 1 deletion(-)"
                # Formato: "abc1234 Mensaje del commit"
                if "|" in line and "changed" not in line and "insertion" not in line and "deletion" not in line:
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2 and len(parts[0]) >= 7:
                        changes.append((parts[0][:7], parts[1]))

            if changes:
                print(f"{Color.GREEN}✓ Actualizado #{sha_before} -> #{sha_after}{Color.RESET}")
                print(f"  {Color.CYAN}Cambios:{Color.RESET}")
                for sha, msg in changes[:5]:
                    print(f"    {Color.DIM}{sha}{Color.RESET} {msg[:80]}")
                if len(changes) > 5:
                    print(f"    {Color.DIM}... y {len(changes) - 5} mas{Color.RESET}")
            else:
                # Pull exitoso pero sin listado de commits (ej: merge)
                print(f"{Color.GREEN}✓ Actualizado a #{sha_after}{Color.RESET}")
                for line in output.splitlines()[-5:]:
                    if line.strip():
                        print(f"  {Color.DIM}{line}{Color.RESET}")

            print(f"\n{Color.YELLOW}Reinicia Nexus para aplicar los cambios.{Color.RESET}")
            # Refrescar version info para que el proximo /version muestre la nueva
            try:
                import version as _v
                _v.refresh_version()
                # Actualizar el banner para el siguiente ciclo
                self._git_info = self._load_git_info()
            except Exception:
                pass
        except _sp.TimeoutExpired:
            print(f"{Color.RED}Timeout. git pull tardó más de 30s.{Color.RESET}")
        except FileNotFoundError:
            print(f"{Color.RED}git no está instalado o no está en el PATH.{Color.RESET}")
        except Exception as e:
            print(f"{Color.RED}Error: {e}{Color.RESET}")

    def _cmd_reset(self, cmd: str = ""):
        # Confirmación simple
        print(f"{Color.RED}¿Estás seguro? Esto borrará todo el progreso de Nexus.{Color.RESET}")
        confirm = input(f"{Color.YELLOW}Escribe 'si' para confirmar: {Color.RESET}")
        if confirm.lower() in ["si", "sí", "yes", "y"]:
            self.core.reset()
            print(f"{Color.GREEN}✓ Nexus ha sido reiniciado.{Color.RESET}")
        else:
            print(f"{Color.DIM}Cancelado.{Color.RESET}")

    def _cmd_clear(self, cmd: str = ""):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.show_banner()

    def _cmd_exit(self, cmd: str = ""):
        self.running = False
        print(f"\n{Color.rgb(0, 180, 255)}╔══════════════════════════════════╗")
        print(f"║   Nexus se despide. Sigamos     ║")
        print(f"║   aprendiendo en la próxima      ║")
        print(f"║   sesión. 👋                     ║")
        print(f"╚══════════════════════════════════╝{Color.RESET}")
        print()

    # ─── Comandos Notebook Guide ─────────────────────────────

    def _cmd_ingest(self, cmd: str = ""):
        """Ingiere un documento en memoria. Uso: /documento <ruta> o texto directo"""
        arg = cmd.split(" ", 1)[1] if " " in cmd else ""
        if not arg:
            print(f"{Color.YELLOW}Uso:{Color.RESET} /documento <ruta_archivo>")
            print(f"  O pega el texto directamente después del comando.")
            print(f"  Ej: /documento C:/ruta/documento.txt")
            print(f"  Ej: /documento El texto completo del documento...")
            return

        # Verificar si es una ruta de archivo
        from knowledge.ingester import ingest_text, chunk_text
        import os as _os

        if _os.path.exists(arg):
            try:
                with open(arg, "r", encoding="utf-8") as f:
                    text = f.read()
                titulo = _os.path.basename(arg)
                print(f"{Color.DIM}  Leyendo archivo: {arg} ({len(text)} chars){Color.RESET}")
            except Exception as e:
                print(f"{Color.RED}Error leyendo archivo: {e}{Color.RESET}")
                return
        else:
            # Es texto directo
            text = arg
            titulo = f"Texto_{len(text)}chars"

        # Chunkear y mostrar preview
        chunks = chunk_text(text)
        print(f"{Color.GREEN}✓ Documento dividido en {len(chunks)} secciones{Color.RESET}")

        # Confirmar ingesta
        print(f"{Color.DIM}  Ingenierdo '{titulo}' en memoria...{Color.RESET}")
        count = ingest_text(text, self.core.memory, titulo=titulo)
        print(f"{Color.GREEN}✓ {count} fragmentos almacenados en memoria{Color.RESET}")
        print(f"\n{Color.CYAN}Ahora puedes generar una guía con:{Color.RESET}")
        print(f"  {Color.GREEN}/guia {titulo}{Color.RESET}")
        print(f"  {Color.GREEN}/faq {titulo}{Color.RESET}")

    def _cmd_guide(self, cmd: str = ""):
        """Genera una guía (briefing + FAQ + conceptos) de un documento. Uso: /guia <titulo>"""
        arg = cmd.split(" ", 1)[1] if " " in cmd else ""
        if not arg:
            print(f"{Color.YELLOW}Uso: /guia <titulo_del_documento>{Color.RESET}")
            print(f"  El documento debe haber sido ingerido antes con /documento")
            return

        from knowledge.guide import generate_guide

        print(f"{Color.DIM}  Generando guía para '{arg}'... (puede tomar unos segundos){Color.RESET}")
        
        guide = generate_guide(self.core.slm, self.core.memory, titulo=arg)
        if not guide:
            print(f"{Color.RED}No se pudo generar la guía. ¿El documento está ingerido?{Color.RESET}")
            return

        # Mostrar resultados
        titulo = guide.get("titulo", arg)
        print(f"\n{Color.CYAN}╔══ Guía: {titulo} ══╗{Color.RESET}")

        # Briefing
        briefing = guide.get("briefing", "")
        if briefing:
            print(f"\n{Color.YELLOW}📋 BRIEFING (Resumen Ejecutivo){Color.RESET}")
            print(f"  {briefing[:600]}")

        # FAQ
        faq = guide.get("faq", [])
        if faq:
            print(f"\n{Color.YELLOW}❓ FAQ ({len(faq)} preguntas){Color.RESET}")
            for i, item in enumerate(faq, 1):
                if isinstance(item, dict):
                    q = item.get("pregunta", item.get("question", ""))
                    a = item.get("respuesta", item.get("answer", ""))
                    print(f"\n  {Color.GREEN}{i}. {q}{Color.RESET}")
                    print(f"     {a[:200]}")

        # Conceptos clave
        conceptos = guide.get("conceptos", guide.get("key_concepts", []))
        if conceptos:
            print(f"\n{Color.YELLOW}📌 CONCEPTOS CLAVE ({len(conceptos)}){Color.RESET}")
            for item in conceptos:
                if isinstance(item, dict):
                    term = item.get("termino", item.get("term", item.get("concept", "")))
                    defn = item.get("definicion", item.get("definition", ""))
                    print(f"  {Color.GREEN}• {term}:{Color.RESET} {defn[:150]}")

        # Timeline
        timeline = guide.get("timeline", [])
        if timeline:
            print(f"\n{Color.YELLOW}📅 TIMELINE{Color.RESET}")
            for item in timeline:
                if isinstance(item, dict):
                    fecha = item.get("fecha", item.get("date", ""))
                    evento = item.get("evento", item.get("event", ""))
                    print(f"  {Color.GREEN}{fecha}{Color.RESET} → {evento[:150]}")

        print(f"\n{Color.CYAN}╚══ Fin de la guía ══╝{Color.RESET}")

    def _cmd_faq(self, cmd: str = ""):
        """Genera FAQ sobre un tema. Uso: /faq <tema>"""
        arg = cmd.split(" ", 1)[1] if " " in cmd else ""
        if not arg:
            print(f"{Color.YELLOW}Uso: /faq <tema>{Color.RESET}")
            print(f"  Ej: /faq fotosintesis")
            return

        from knowledge.guide import generate_faq

        print(f"{Color.DIM}  Generando FAQ sobre '{arg}'...{Color.RESET}")
        faq = generate_faq(self.core.slm, arg, self.core.memory)
        if not faq:
            print(f"{Color.YELLOW}No hay suficiente información en memoria sobre '{arg}'.{Color.RESET}")
            print(f"  Prueba primero con /documento o /aprende para añadir información.")
            return

        print(f"\n{Color.CYAN}╔══ FAQ: {arg} ══╗{Color.RESET}")
        for i, item in enumerate(faq, 1):
            if isinstance(item, dict):
                q = item.get("pregunta", item.get("question", ""))
                a = item.get("respuesta", item.get("answer", ""))
                print(f"\n{Color.GREEN}{i}. {q}{Color.RESET}")
                print(f"     {a[:300]}")
        print(f"\n{Color.CYAN}╚══ Fin FAQ ══╝{Color.RESET}")
