#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════╗
# ║     Nexus CLI — Instalador Universal                       ║
# ║     Detecta OS y configura todo automaticamente            ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Uso:
#   bash install.sh          # Instalacion guiada
#   bash install.sh --force  # Sin preguntar
#   bash install.sh --help   # Ayuda

set -e

# ─── Colores ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

# ─── Deteccion del sistema ─────────────────────────────────────
detect_system() {
    NEXUS_DIR="$(cd "$(dirname "$0")" && pwd)"
    OS="unknown"
    SHELL_TYPE="unknown"
    INSTALL_METHOD=""

    case "$(uname -s)" in
        Linux)  OS="linux" ;;
        Darwin) OS="macos" ;;
        *_NT*)  OS="windows" ;;
        MINGW*|MSYS*) OS="windows-msys" ;;
    esac

    # Detectar shell activa
    if [ -n "$BASH_VERSION" ]; then
        SHELL_TYPE="bash"
    elif [ -n "$ZSH_VERSION" ]; then
        SHELL_TYPE="zsh"
    elif [ "$OS" = "windows" ]; then
        SHELL_TYPE="powershell"
    fi

    # Detectar WSL
    if [ "$OS" = "linux" ] && grep -qi microsoft /proc/version 2>/dev/null; then
        OS="wsl"
    fi

    echo -e "${CYAN}🔍 Sistema detectado:${NC} $OS / $SHELL_TYPE"
    echo -e "${DIM}   Directorio Nexus: $NEXUS_DIR${NC}"
}

# ─── Verificar requisitos ──────────────────────────────────────
check_requirements() {
    echo -e "\n${CYAN}📋 Verificando requisitos...${NC}"

    local missing=0

    # Python
    if command -v python3 &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} Python 3: $(python3 --version 2>&1)"
        PYTHON="python3"
    elif command -v python &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} Python: $(python --version 2>&1)"
        PYTHON="python"
    else
        echo -e "  ${RED}❌${NC} Python no encontrado. Instala Python 3.10+"
        missing=$((missing + 1))
    fi

    # Git
    if command -v git &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} Git: $(git --version 2>&1 | head -1)"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Git no encontrado (opcional, para nexus update)"
    fi

    # Ollama (opcional)
    if command -v ollama &>/dev/null || curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo -e "  ${GREEN}✅${NC} Ollama detectado"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Ollama no detectado (opcional, para modelos locales)"
    fi

    if [ $missing -gt 0 ]; then
        echo -e "\n${RED}❌ Faltan $missing requisito(s). Instalalos y volve a ejecutar.${NC}"
        exit 1
    fi
}

# ─── Instalar en bash / zsh / git-bash ─────────────────────────
install_bash() {
    local rc_file=""
    local shell_name=""

    case "$SHELL_TYPE" in
        bash)
            if [ "$OS" = "macos" ]; then
                rc_file="$HOME/.bash_profile"
            else
                rc_file="$HOME/.bashrc"
            fi
            shell_name="Bash"
            ;;
        zsh)
            rc_file="$HOME/.zshrc"
            shell_name="Zsh"
            ;;
    esac

    echo -e "\n${CYAN}🐚 Configurando $shell_name...${NC}"

    local nexus_line="export PATH=\"$NEXUS_DIR:\$PATH\"  # Nexus CLI"
    local alias_line="alias nexus='$NEXUS_DIR/nexus'  # Nexus CLI (fallback)"

    # Crear .bashrc si no existe
    touch "$rc_file" 2>/dev/null || true

    # Agregar PATH si no esta
    if ! grep -q "Nexus CLI" "$rc_file" 2>/dev/null; then
        echo "" >> "$rc_file"
        echo "# ─── Nexus CLI ───────────────────────────────────" >> "$rc_file"
        echo "$nexus_line" >> "$rc_file"
        echo "$alias_line" >> "$rc_file"
        echo -e "  ${GREEN}✅${NC} Agregado a $rc_file"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Ya estaba en $rc_file"
    fi

    # Hacer ejecutable el launcher
    chmod +x "$NEXUS_DIR/nexus" 2>/dev/null || true
    chmod +x "$NEXUS_DIR/nexus.py" 2>/dev/null || true

    echo -e "  ${GREEN}✅${NC} $shell_name configurado"
    echo -e "  ${DIM}Para activar: source $rc_file${NC}"
}

# ─── Instalar en PowerShell ────────────────────────────────────
install_powershell() {
    echo -e "\n${CYAN}🪟 Configurando PowerShell...${NC}"

    # Detectar ruta del perfil PowerShell
    local ps_profile=""
    if command -v powershell &>/dev/null; then
        ps_profile=$(powershell -Command 'Write-Host $PROFILE.CurrentUserCurrentHost' 2>/dev/null || echo "")
    fi

    if [ -z "$ps_profile" ]; then
        # Fallback a ruta estandar
        ps_profile="$HOME/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1"
    fi

    local ps_line=". $NEXUS_DIR\\nexus.ps1  # Nexus CLI"
    # Convertir forward slashes a backslashes para PowerShell
    ps_line=$(echo "$ps_line" | sed 's|/|\\\\|g')

    # Crear directorio del perfil si no existe
    local ps_dir
    ps_dir=$(dirname "$ps_profile")
    mkdir -p "$ps_dir" 2>/dev/null || true

    # Agregar al perfil
    if [ -f "$ps_profile" ]; then
        if ! grep -q "Nexus CLI" "$ps_profile" 2>/dev/null; then
            echo "" >> "$ps_profile"
            echo "# ─── Nexus CLI ───────────────────────────────────" >> "$ps_profile"
            echo ". $NEXUS_DIR\\nexus.ps1  # Nexus CLI" >> "$ps_profile"
            echo -e "  ${GREEN}✅${NC} Agregado a $ps_profile"
        else
            echo -e "  ${YELLOW}⚠️${NC}  Ya estaba en el perfil"
        fi
    else
        echo "# ─── Nexus CLI ───────────────────────────────────" > "$ps_profile"
        echo ". $NEXUS_DIR\\nexus.ps1  # Nexus CLI" >> "$ps_profile"
        echo -e "  ${GREEN}✅${NC} Perfil creado: $ps_profile"
    fi

    echo -e "  ${GREEN}✅${NC} PowerShell configurado"
    echo -e "  ${DIM}Abrí una terminal PowerShell nueva para usar 'nexus'${NC}"
}

# ─── Instalar en cmd.exe ──────────────────────────────────────
install_cmd() {
    echo -e "\n${CYAN}💻 Configurando cmd.exe...${NC}"

    # En Windows, agregar al PATH del usuario via registry
    if [ "$OS" = "windows" ] || [ "$OS" = "windows-msys" ]; then
        local win_path
        win_path=$(echo "$NEXUS_DIR" | sed 's|/|\\\\|g')

        # Usar PowerShell para modificar el PATH de usuario
        powershell -Command "
            \$oldPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
            if (\$oldPath -notlike '*$win_path*') {
                [Environment]::SetEnvironmentVariable('PATH', \"\$oldPath;$win_path\", 'User')
                Write-Host '  ✅ Agregado al PATH de usuario'
            } else {
                Write-Host '  ⚠️  Ya estaba en el PATH'
            }
        " 2>/dev/null && echo -e "  ${GREEN}✅${NC} cmd.exe configurado" || \
            echo -e "  ${YELLOW}⚠️${NC}  No se pudo modificar PATH (ejecuta como Admin?)"
    fi
}

# ─── Verificar instalacion ─────────────────────────────────────
verify_installation() {
    echo -e "\n${CYAN}🧪 Verificando instalacion...${NC}"

    # Probar el script Python directamente
    if "$PYTHON" "$NEXUS_DIR/nexus.py" version &>/dev/null; then
        echo -e "  ${GREEN}✅${NC} nexus.py funciona"
        "$PYTHON" "$NEXUS_DIR/nexus.py" version 2>/dev/null | head -6 | sed 's/^/  /'
    else
        echo -e "  ${RED}❌${NC} nexus.py fallo"
    fi

    # Verificar bash launcher
    if [ -f "$NEXUS_DIR/nexus" ] && [ -x "$NEXUS_DIR/nexus" ]; then
        echo -e "  ${GREEN}✅${NC} Launcher bash listo"
    fi

    # Verificar PowerShell
    if [ -f "$NEXUS_DIR/nexus.ps1" ]; then
        echo -e "  ${GREEN}✅${NC} Launcher PowerShell listo"
    fi

    # Verificar cmd
    if [ -f "$NEXUS_DIR/nexus.bat" ]; then
        echo -e "  ${GREEN}✅${NC} Launcher cmd.exe listo"
    fi
}

# ─── Banner ────────────────────────────────────────────────────
show_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║       ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗  ║"
    echo "║       ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝  ║"
    echo "║       ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗  ║"
    echo "║       ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║  ║"
    echo "║       ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║  ║"
    echo "║       ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝  ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  ${BOLD}Instalador Universal${NC} — v1.0"
    echo -e "  ${DIM}Detecta tu SO y configura todo automaticamente${NC}"
    echo ""
}

# ─── Resumen final ─────────────────────────────────────────────
show_summary() {
    echo -e "\n${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${BOLD}✅ Instalacion completada${NC}                          ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"

    echo -e "\n${BOLD}📦 Comandos disponibles:${NC}"
    echo -e "  ${YELLOW}nexus${NC}              Chat interactivo"
    echo -e "  ${YELLOW}nexus status${NC}       Estado del sistema"
    echo -e "  ${YELLOW}nexus model list${NC}   Modelos Ollama"
    echo -e "  ${YELLOW}nexus update${NC}       git pull"
    echo -e "  ${YELLOW}nexus help${NC}         Todos los comandos"

    echo -e "\n${BOLD}🚀 Para empezar:${NC}"

    case "$SHELL_TYPE" in
        bash|zsh)
            echo -e "  ${CYAN}source ~/.bashrc${NC}   (o abri una terminal nueva)"
            echo -e "  ${CYAN}nexus version${NC}"
            ;;
    esac

    if [ "$OS" = "windows" ] || [ "$OS" = "windows-msys" ]; then
        echo -e "  ${CYAN}Abrí PowerShell nuevo${NC} y escribí: ${YELLOW}nexus version${NC}"
    fi
}

# ─── Main ──────────────────────────────────────────────────────
main() {
    FORCE=false
    for arg in "$@"; do
        case "$arg" in
            --force|-f) FORCE=true ;;
            --help|-h)
                echo "Nexus CLI — Instalador Universal"
                echo "  bash install.sh           Instalacion guiada"
                echo "  bash install.sh --force   Sin preguntar"
                exit 0
                ;;
        esac
    done

    show_banner
    detect_system
    check_requirements

    # Confirmar
    if [ "$FORCE" != true ]; then
        echo -e "\n${YELLOW}¿Instalar Nexus CLI en este sistema?${NC}"
        echo -e "  Directorio: ${CYAN}$NEXUS_DIR${NC}"
        echo -e "  Sistema:    ${CYAN}$OS / $SHELL_TYPE${NC}"
        echo ""
        read -p "  Continuar? [S/n] " -r REPLY
        if [[ "$REPLY" =~ ^[Nn] ]]; then
            echo "Cancelado."
            exit 0
        fi
    fi

    # Instalar segun sistema
    case "$SHELL_TYPE" in
        bash|zsh) install_bash ;;
    esac

    # En Windows, instalar tambien PowerShell y cmd
    if [ "$OS" = "windows" ] || [ "$OS" = "windows-msys" ]; then
        install_powershell
        install_cmd
    fi

    verify_installation
    show_summary
}

main "$@"
