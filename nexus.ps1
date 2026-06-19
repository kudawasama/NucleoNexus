# Nexus CLI Launcher para PowerShell
# ===================================
# Uso: nexus version, nexus status, nexus, etc.
#
# Para instalar permanentemente, ejecuta ESTO UNA VEZ en PowerShell:
#   Add-Content -Path $PROFILE -Value ". F:\HomeServerAsus\Proyectos\NucleoNexus\nexus.ps1"

$NEXUS_DIR = "F:\HomeServerAsus\Proyectos\NucleoNexus"

function nexus {
    python "$NEXUS_DIR\nexus.py" @args
}

# Si se ejecuta directo (no como dot-source), mostrar ayuda
if ($MyInvocation.InvocationName -eq '.\nexus.ps1') {
    nexus @args
}
