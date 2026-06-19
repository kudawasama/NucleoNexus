"""
Menu Interactivo con Teclado
=============================
Navegacion con flechas ↑↓, seleccion con Enter/Espacio, cancelar con Esc/q.

Uso:
    from interface.menu import interactive_menu

    options = ["Ver modelo actual", "Lista modelos", "Menu interactivo", "Cambio rapido", "Test"]
    choice = interactive_menu("Gestion de Modelos", options)
    if choice == 0: ...
    if choice is None: ...  # cancelo
"""

import sys
import os

# ─── Detectar plataforma ──────────────────────────────────────
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import msvcrt

    def _get_key():
        """Lee una tecla en Windows/msvcrt."""
        ch = msvcrt.getch()
        if ch == b'\xe0':  # teclas especiales
            ch2 = msvcrt.getch()
            if ch2 == b'H': return 'UP'
            if ch2 == b'P': return 'DOWN'
            if ch2 == b'K': return 'LEFT'
            if ch2 == b'M': return 'RIGHT'
            return None
        if ch == b'\r': return 'ENTER'
        if ch == b' ': return 'SPACE'
        if ch == b'\x1b': return 'ESC'
        if ch == b'q' or ch == b'Q': return 'q'
        try:
            return ch.decode('utf-8').lower()
        except:
            return None
else:
    import tty
    import termios

    def _get_key():
        """Lee una tecla en Unix/Linux/macOS."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = os.read(fd, 1)
            if ch == b'\x1b':
                # Podria ser secuencia de escape
                extra = os.read(fd, 2)
                if extra == b'[A': return 'UP'
                if extra == b'[B': return 'DOWN'
                if extra == b'[C': return 'RIGHT'
                if extra == b'[D': return 'LEFT'
                return 'ESC'
            if ch == b'\r' or ch == b'\n': return 'ENTER'
            if ch == b' ': return 'SPACE'
            if ch == b'q' or ch == b'Q': return 'q'
            return ch.decode('utf-8').lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ─── Colores ANSI ─────────────────────────────────────────────
class C:
    R = '\033[0m'
    B = '\033[1m'
    D = '\033[2m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BLUE = '\033[94m'
    BG_BLUE = '\033[44m'
    BG_CYAN = '\033[46m'


def interactive_menu(title, options, default=0):
    """Menu interactivo con navegacion por teclado.

    Args:
        title: Titulo del menu
        options: Lista de strings (opciones)
        default: Indice por defecto

    Returns:
        int: indice seleccionado (0-based)
        None: si el usuario cancelo (Esc/q)
    """
    selected = default

    while True:
        # Dibujar menu
        _draw_menu(title, options, selected)

        key = _get_key()

        if key == 'UP':
            selected = (selected - 1) % len(options)
        elif key == 'DOWN':
            selected = (selected + 1) % len(options)
        elif key in ('ENTER', 'SPACE'):
            _clear_menu(len(options) + 3)
            return selected
        elif key in ('ESC', 'q'):
            _clear_menu(len(options) + 3)
            return None
        # numeros rapidos: 1-9
        elif key and key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(options):
                _clear_menu(len(options) + 3)
                return idx


def _draw_menu(title, options, selected):
    """Dibuja el menu en la terminal."""
    # Mover cursor arriba si no es primera vez
    if hasattr(_draw_menu, '_drawn'):
        sys.stdout.write(f'\033[{len(options) + 3}A')
    _draw_menu._drawn = True

    width = max(len(o) for o in options) + 8

    print(f'\r{C.CYAN}╔══ {title} ══{"═" * (width - len(title) - 6)}╗{C.R}')
    for i, opt in enumerate(options):
        if i == selected:
            print(f'\r{C.CYAN}║{C.R} {C.BG_CYAN}{C.B} ▶ {opt:<{width-2}}{C.R} {C.CYAN}║{C.R}')
        else:
            print(f'\r{C.CYAN}║{C.R} {C.D}  {opt:<{width-2}}{C.R} {C.CYAN}║{C.R}')
    print(f'\r{C.CYAN}╚{"═" * (width + 2)}╝{C.R}')
    print(f'\r{C.D}  ↑↓ navegar  Enter/Espacio seleccionar  Esc/q cancelar  1-9 rapido{C.R}')
    sys.stdout.flush()


def _clear_menu(lines):
    """Limpia las lineas del menu."""
    for _ in range(lines):
        sys.stdout.write('\033[F\033[K')
    sys.stdout.flush()
