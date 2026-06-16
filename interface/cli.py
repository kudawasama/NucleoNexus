"""
Núcleo Nexus — Interfaz CLI Interactiva
=========================================
Terminal interactiva con colores, historial y comandos.
"""

import logging
import os
import sys
import time
from pathlib import Path

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
NEXUS_ASCII = f"""{Color.rgb(0, 180, 255)}╔══════════════════════════════════╗
║     {Color.rgb(255, 200, 50)}███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗{Color.rgb(0, 180, 255)}    ║
║     {Color.rgb(255, 200, 50)}████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝{Color.rgb(0, 180, 255)}    ║
║     {Color.rgb(255, 200, 50)}██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗{Color.rgb(0, 180, 255)}    ║
║     {Color.rgb(255, 200, 50)}██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║{Color.rgb(0, 180, 255)}    ║
║     {Color.rgb(255, 200, 50)}██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║{Color.rgb(0, 180, 255)}    ║
║     {Color.rgb(255, 200, 50)}╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝{Color.rgb(0, 180, 255)}    ║
╚══════════════════════════════════╝{Color.RESET}
{Color.DIM}  IA Ultra-Ligera · Aprendizaje Incremental · SLM-Ready{Color.RESET}
"""


class NexusCLI:
    """Terminal interactivo de Núcleo Nexus."""

    def __init__(self, nexus_core):
        self.core = nexus_core
        self.history = []
        self.running = True
        self._setup_history()

    def _setup_history(self):
        """Carga historial de comandos previos si existe."""
        hist_file = Path(self.core.state.state_dir) / ".nexus_history"
        if hist_file.exists():
            try:
                self.history = hist_file.read_text().splitlines()
            except:
                pass

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
        backend = self.core.state.get("capabilities", "backend", default="symbolic")
        print(f"{Color.CYAN}╔═══════════════════════════════════════════╗{Color.RESET}")
        print(f"{Color.CYAN}║{Color.RESET}  Fase: {Color.YELLOW}{phase}{Color.RESET}                 "
              f"v{version}      {Color.CYAN}║{Color.RESET}")
        print(f"{Color.CYAN}║{Color.RESET}  Backend: {Color.GREEN}{backend}{Color.RESET}"
              f"                           {Color.CYAN}║{Color.RESET}")
        print(f"{Color.CYAN}║{Color.RESET}  Escribe '{Color.GREEN}/help{Color.RESET}' para comandos  "
              f"'{Color.GREEN}/exit{Color.RESET}' para salir {Color.CYAN}║{Color.RESET}")
        print(f"{Color.CYAN}╚═══════════════════════════════════════════╝{Color.RESET}")
        print()

    def run(self):
        """Bucle principal de la CLI."""
        self.show_banner()
        
        while self.running:
            try:
                user_input = input(f"{Color.rgb(0, 180, 255)}Nexus{Color.RESET}"
                                   f"{Color.GRAY}@{Color.RESET}"
                                   f"{Color.rgb(255, 200, 50)}φ{Color.RESET} ")
            except (EOFError, KeyboardInterrupt):
                print()
                self._cmd_exit()
                break

            if not user_input.strip():
                continue

            self._save_history(user_input)

            # Comandos del sistema
            if user_input.startswith("/"):
                self._handle_command(user_input)
                continue

            # Procesar input con Nexus
            start = time.time()
            response = self.core.process(user_input)
            elapsed = (time.time() - start) * 1000

            # Mostrar respuesta con estilo
            self._show_response(response, elapsed)

    def _show_response(self, response: str, elapsed_ms: float):
        """Muestra la respuesta formateada."""
        phase = self.core.state.get("nexus", "phase", default="Proto")
        
        # Indicador de fase
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
        
        # Footer con tiempo
        conf = self.core.state.get("nexus", "confidence_level", default=0)
        bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
        
        print(f"{Color.DIM}  ─── {elapsed_ms:.0f}ms · [{bar}] {conf:.0%} confianza{Color.RESET}")
        print()

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
            "/skills": self._cmd_skills,
            "/skill": self._cmd_skills,
            "/personalidad": self._cmd_personality,
            "/backend": self._cmd_backend,
            "/export": self._cmd_export,
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
{Color.GREEN}/memoria{Color.RESET}      Últimos recuerdos
{Color.GREEN}/hechos{Color.RESET}       Hechos aprendidos
{Color.GREEN}/skills{Color.RESET}       Skills cargadas
{Color.GREEN}/personalidad{Color.RESET} Ver/ajustar personalidad
{Color.GREEN}/backend{Color.RESET}      Cambiar backend (symbolic/slm)
{Color.GREEN}/export{Color.RESET}       Exportar estado como JSON
{Color.GREEN}/clear{Color.RESET}        Limpiar pantalla
{Color.GREEN}/reset{Color.RESET}        Resetear Nexus
{Color.GREEN}/exit{Color.RESET}         Salir

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
        print(f"{Color.CYAN}╔══ Backend ══╗{Color.RESET}")
        print(f"  Actual: {Color.GREEN}{current}{Color.RESET}")
        print(f"  Opciones: {Color.YELLOW}symbolic{Color.RESET} (sin modelo), "
              f"{Color.YELLOW}slm{Color.RESET} (modelo local), "
              f"{Color.YELLOW}hybrid{Color.RESET} (combinado)")
        if self.core.slm:
            slm_info = self.core.slm.get_info()
            print(f"  SLM: {'🟢 cargado' if slm_info['loaded'] else '🔴 no cargado'}")
            print(f"  Modo: {slm_info['mode']} | Modelo: {slm_info['model']}")

    def _cmd_export(self, cmd: str = ""):
        output = self.core.state.export_json()
        print(f"\n{Color.CYAN}╔══ Exportar Estado ══╗{Color.RESET}")
        print(output)
        print()

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
