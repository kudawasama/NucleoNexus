#!/usr/bin/env python3
"""Configura git para usar token desde .env en lugar de embeberlo en la URL."""
import subprocess, os, sys

# Asegurar que el remote NO tenga token embebido
result = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True)
current_url = result.stdout.strip()

if 'ghp_' in current_url or 'github_pat_' in current_url:
    clean_url = 'https://github.com/kudawasama/NucleoNexus.git'
    subprocess.run(['git', 'remote', 'set-url', 'origin', clean_url])
    print(f"✅ Token removido de remote. URL limpia: {clean_url}")
else:
    print("✅ Remote ya esta limpio")

# Verificar que el .env existe
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if not os.path.exists(env_path):
    print(f"⚠️  No existe .env. Crea uno desde .env.example")
    sys.exit(1)

# Probar conexion (git_auto.py usara el token del .env automaticamente)
print("\nProbando conexión (lectura desde .env)...")
from utils.dotenv import get_env
token = get_env("GITHUB_TOKEN")
if token:
    print(f"✅ Token cargado desde .env")
else:
    print("⚠️  No hay token en .env, git pedira autenticacion manual")

result = subprocess.run(['git', 'fetch', '--dry-run'], capture_output=True, text=True)
if result.returncode == 0:
    print("✅ Conexion OK")
else:
    print(f"⚠️  Verificacion fallo: {result.stderr[:100]}")
