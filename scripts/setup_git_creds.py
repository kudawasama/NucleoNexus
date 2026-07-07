#!/usr/bin/env python3
"""Configura git para usar token desde .env en lugar de hardcodeado.

Este script reemplaza la version anterior que tenia tokens embebidos
con codigos ASCII ofuscados. Ahora todo se lee desde .env.
"""
import subprocess, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
from utils.dotenv import get_env

token = get_env("GITHUB_TOKEN")
if not token:
    print("❌ No hay GITHUB_TOKEN en .env")
    print("   Copia .env.example a .env y agrega tu token")
    sys.exit(1)

# Almacenar credencial en el helper del sistema
cred_input = f"""protocol=https
host=github.com
username=kudawasama
password={token}
"""

proc = subprocess.run(['git', 'credential', 'approve'],
                     input=cred_input, text=True, capture_output=True)
if proc.returncode == 0:
    print("✅ Credenciales almacenadas en el helper de git")
else:
    print(f"⚠️  Error: {proc.stderr}")

# Verificar
result = subprocess.run(['git', 'fetch', '--dry-run'], capture_output=True, text=True)
if result.returncode == 0:
    print("✅ Conexion verificada - git funcional")
else:
    print(f"⚠️  Verificacion fallo: {result.stderr[:100]}")
