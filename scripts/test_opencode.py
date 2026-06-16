#!/usr/bin/env python3
"""Prueba conexion OpenCode Go - Lee API key desde archivo."""
import sys, json, urllib.request

# Leer key desde un archivo temporal
try:
    with open('/tmp/opencode_key.txt', 'r') as f:
        key = f.read().strip()
    if not key:
        raise ValueError("Archivo vacio")
except:
    print("ERROR: Crea el archivo /tmp/opencode_key.txt con tu API key")
    print("Ejecuta en Git Bash: echo 'TU_KEY_AQUI' > /tmp/opencode_key.txt")
    sys.exit(1)

print(f"Key: {key[:12]}...{key[-4:]} (len={len(key)})")

# Probar modelos
url = "https://opencode.ai/zen/go/v1/models"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {key}")

try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print("\n✅ Modelos disponibles en Go plan:")
    for m in data.get('data', []):
        print(f"  - {m.get('id', '?')}")
except urllib.error.HTTPError as e:
    print(f"\n❌ HTTP {e.code}: {e.reason}")
    print(f"Detalle: {e.read().decode()[:200]}")
    sys.exit(1)

# Probar chat
print("\nProbando chat completion...")
chat_url = "https://opencode.ai/zen/go/v1/chat/completions"
payload = json.dumps({
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "responde solo: ok funciono"}],
    "max_tokens": 10
}).encode()
req2 = urllib.request.Request(chat_url, data=payload)
req2.add_header("Authorization", f"Bearer {key}")
req2.add_header("Content-Type", "application/json")
try:
    resp2 = urllib.request.urlopen(req2, timeout=15)
    d = json.loads(resp2.read())
    print(f"✅ Chat OK")
    print(f"Modelo: {d.get('model', '?')}")
    print(f"Respuesta: {d['choices'][0]['message']['content']}")
except Exception as e:
    print(f"❌ Error: {e}")
