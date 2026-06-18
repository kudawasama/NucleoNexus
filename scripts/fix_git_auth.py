#!/usr/bin/env python3
"""Configura git para recordar credenciales de GitHub."""
import subprocess, os, sys

# Configurar credential helper
subprocess.run(['git', 'config', '--global', 'credential.helper', 'manager-core'],
               capture_output=True)
print("✅ credential.helper = manager-core")

# Verificar remote actual
result = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True)
current_url = result.stdout.strip()
print(f"Remote actual: {current_url}")

# Si tiene token embebido, limpiarlo
if 'ghp_' in current_url or 'github_pat_' in current_url:
    # Reemplazar con URL limpia
    clean_url = 'https://github.com/kudawasama/NucleoNexus.git'
    subprocess.run(['git', 'remote', 'set-url', 'origin', clean_url])
    print(f"URL limpiada: {clean_url}")

# Probar push (debería pedir credenciales UNA vez y recordarlas)
print("\nProbando conexión...")
result = subprocess.run(['git', 'fetch', '--dry-run'], capture_output=True, text=True)
if result.returncode == 0:
    print("✅ Conexión OK")
else:
    print("⚠️  Se necesita autenticación una vez más. En la ventana que aparece, selecciona 'kudawasama' e ingresa tu contraseña de GitHub o token.")
    print("   Después de eso, Windows recordará las credenciales.")
