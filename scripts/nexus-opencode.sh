#!/bin/bash
# Arranca Nexus con OpenCode Go
# Extrae la API key del master env y lanza la app

MASTER_ENV="H:/Mi unidad/kudawa-master.env"
if [ -f "$MASTER_ENV" ]; then
    # Extraer OPENCODE_GO_API_KEY del archivo master
    export OPENCODE_GO_API_KEY=$(grep "^OPENCODE_GO_API_KEY=" "$MASTER_ENV" | cut -d= -f2- | tr -d '"'"'"')
fi

echo "Iniciando Nexus con OpenCode Go..."
cd "$(dirname "$0")/.."
python main.py
