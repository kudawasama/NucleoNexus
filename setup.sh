#!/bin/bash
# ─── Nexus CLI Setup ────────────────────────────────────────────
# Agrega nexus a tu PATH para usarlo desde cualquier carpeta.
#
# Uso:
#   source setup.sh          # temporal (solo esta sesion)
#   bash setup.sh --install  # permanente (agrega a ~/.bashrc)
#
# Despues de instalar, usa:
#   nexus                    # inicia chat
#   nexus status             # estado del sistema
#   nexus model list         # modelos disponibles
#   nexus update             # git pull
#   nexus help               # todos los comandos

NEXUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Agregar al PATH
export PATH="$NEXUS_DIR:$PATH"

# Hacer el script ejecutable
chmod +x "$NEXUS_DIR/nexus" 2>/dev/null

echo "✅ Nexus CLI configurado"
echo "   Directorio: $NEXUS_DIR"
echo "   Prueba con: nexus version"
echo ""

if [ "$1" = "--install" ]; then
    BASHRC="$HOME/.bashrc"
    LINE="export PATH=\"$NEXUS_DIR:\$PATH\"  # Nexus CLI"

    if ! grep -q "Nexus CLI" "$BASHRC" 2>/dev/null; then
        echo "$LINE" >> "$BASHRC"
        echo "✅ Agregado a ~/.bashrc (permanente)"
    else
        echo "⚠️  Ya estaba en ~/.bashrc"
    fi
    echo ""
    echo "Para aplicar AHORA: source ~/.bashrc"
fi
