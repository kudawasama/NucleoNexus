"""
Skill — Lector CSV
===================
Lee archivos CSV y muestra resumen de datos.
Usa solo la stdlib (csv, statistics).
"""

import csv
import os
import statistics
from pathlib import Path
from skills.registry import Skill

BASE = Path(__file__).parent.parent.parent  # NucleoNexus/


def register() -> Skill:
    skill = Skill(name="csv", description="Lee archivos CSV y muestra resumen de datos", version="1.0.0")

    def _leer_csv(ruta: str = "", filas: int = 5):
        full = (BASE / ruta).resolve()
        if not str(full).startswith(str(BASE)):
            return {"respuesta": "Solo puedo leer archivos dentro del proyecto."}
        if not full.exists():
            return {"respuesta": f"Archivo no encontrado: {ruta}"}
        try:
            with open(full, newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
            if not reader:
                return {"respuesta": f"Archivo vacio o sin cabeceras: {ruta}"}
            cols = list(reader[0].keys())
            total = len(reader)
            # Detectar columnas numericas
            numericas = []
            for c in cols:
                try:
                    vals = [float(row[c]) for row in reader if row[c].strip()]
                    if vals:
                        numericas.append((c, min(vals), max(vals), statistics.mean(vals)))
                except:
                    pass
            out = [f"CSV: {ruta} | {total} filas x {len(cols)} columnas"]
            out.append(f"Columnas: {', '.join(cols)}")
            if numericas:
                out.append("\nResumen numerico:")
                for c, mn, mx, prom in numericas[:5]:
                    out.append(f"  {c}: min={mn:g}, max={mx:g}, prom={prom:.2f}")
            out.append(f"\nPrimeras {filas} filas:")
            for row in reader[:filas]:
                vals = [f"{k}={v}" for k, v in row.items()]
                out.append("  " + " | ".join(vals[:4]))
            return {"respuesta": "\n".join(out)}
        except Exception as e:
            return {"respuesta": f"Error leyendo CSV: {e}"}

    skill.register_action("leer_csv", "Lee y resume un archivo CSV", _leer_csv,
        parameters={
            "ruta": {"type": "string", "description": "Ruta al archivo CSV"},
            "filas": {"type": "integer", "description": "Cuantas filas mostrar"},
        })

    return skill
