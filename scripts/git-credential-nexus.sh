#!/bin/bash
# git-credential-nexus: provee credenciales de GitHub desde .env
# Uso: git config --global credential.helper /ruta/a/este/script
# Luego cualquier git fetch/push/pull usara el token del .env

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null)")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ ! -f "$ENV_FILE" ]; then
    exit 0
fi

case "$1" in
    get)
        read -r line
        TOKEN=$(grep -E "^GITHUB_TOKEN=" "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
        if [ -n "$TOKEN" ]; then
            echo "username=x-access-token"
            echo "password=$TOKEN"
        fi
        echo ""
        ;;
    store|erase)
        exit 0
        ;;
esac
