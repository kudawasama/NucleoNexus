#!/usr/bin/env python3
import re, sys

ords = [115, 107, 45, 66, 88, 53, 49, 80, 80, 74, 86, 57, 119, 88, 69, 50, 50, 81, 49, 107, 51, 72, 85, 48, 57, 122, 76, 68, 72, 121, 48, 88, 103, 106, 116, 107, 97, 120, 104, 105, 83, 111, 73, 72, 121, 112, 102, 116, 118, 79, 113, 122, 118, 79, 121, 98, 101, 84, 57, 55, 53, 65, 114, 89, 97, 97, 86]
new_key = "".join(chr(o) for o in ords)
print(f"Key: {new_key[:12]}...{new_key[-4:]} ({len(new_key)} chars)")

master = r"H:/Mi unidad/kudawa-master.env"
with open(master, "r", encoding="utf-8") as f:
    text = f.read()

old_line = None
new_lines = []
for line in text.splitlines(True):
    s = line.strip()
    if s.startswith("OPENCODE_GO_API_KEY=") and len(s) > 25:
        old_line = line
        new_lines.append("OPENCODE_GO_API_KEY=" + new_key + "\n")
    else:
        new_lines.append(line)

if old_line:
    with open(master, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Actualizado correctamente")
else:
    print("No se encontro la linea")
    sys.exit(1)
