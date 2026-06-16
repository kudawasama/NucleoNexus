# Test de lectura de API key
import os
master_path = 'H:/Mi unidad/kudawa-master.env'
found = False
with open(master_path, 'r', encoding='utf-8') as f:
    for line in f:
        if line.startswith('OPENCODE_GO_API_KEY=') and '***' not in line:
            key = line.split('=', 1)[1].strip().strip('"').strip("'")
            if key and key != '***':
                print(f"Key encontrada: {key[:12]}...{key[-4:]} ({len(key)} chars)")
                found = True
                break
if not found:
    print("No se encontro la key en el archivo master")
