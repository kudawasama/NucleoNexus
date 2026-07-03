# Nexus CLI Launcher para PowerShell
# ===================================
# Uso: nexus version, nexus status, nexus, etc.
#
# Para instalar permanentemente, ejecuta ESTO UNA VEZ en PowerShell:
#   Add-Content -Path $PROFILE -Value ". F:\HomeServerAsus\Proyectos\NucleoNexus\nexus.ps1"

# Determinar la ruta base dinámicamente a partir de la ubicación de este script
$NEXUS_DIR = $PSScriptRoot
if (-not $NEXUS_DIR) {
    # Fallback si se ejecuta en contextos antiguos o dot-sourced desde consola
    $NEXUS_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $NEXUS_DIR) {
    $NEXUS_DIR = Get-Location
}

# Forzar codificación UTF-8 para evitar UnicodeEncodeError en prints de consola de Windows
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function nexus {
    python "$NEXUS_DIR\nexus.py" @args
}

# Si se ejecuta directo, lanzar la función
nexus @args
