"""
Skill — Recordatorios
======================
Crea recordatorios con tiempo. Al iniciar, revisa si hay
recordatorios vencidos y los notifica.
"""

import sqlite3
import time
import os
import threading
from skills.registry import Skill

DB_PATH = None

def _get_db():
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reminders.db")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS recordatorios (id INTEGER PRIMARY KEY AUTOINCREMENT, mensaje TEXT, creado REAL, recordar_en REAL, activo INTEGER DEFAULT 1)")
    return conn

def register() -> Skill:
    skill = Skill(name="recordatorios", description="Crea recordatorios con tiempo", version="1.0.0")

    def _crear_recordatorio(mensaje: str = "", minutos: int = 5):
        conn = _get_db()
        ahora = time.time()
        recordar_en = ahora + (minutos * 60)
        conn.execute("INSERT INTO recordatorios (mensaje, creado, recordar_en) VALUES (?, ?, ?)",
                     (mensaje, ahora, recordar_en))
        conn.commit()
        conn.close()
        return {"respuesta": f"Recordatorio creado: te avisare en {minutos} minuto(s): '{mensaje}'"}

    skill.register_action("crear_recordatorio", "Crea un recordatorio con tiempo", _crear_recordatorio,
        parameters={
            "mensaje": {"type": "string", "description": "Que recordar"},
            "minutos": {"type": "integer", "description": "En cuantos minutos"},
        })

    def _listar_recordatorios():
        conn = _get_db()
        rows = conn.execute("SELECT id, mensaje, creado, recordar_en FROM recordatorios WHERE activo=1 ORDER BY recordar_en LIMIT 10").fetchall()
        conn.close()
        if not rows:
            return {"respuesta": "No tienes recordatorios activos."}
        lines = []
        ahora = time.time()
        for r in rows:
            restante = int((r[3] - ahora) / 60)
            if restante > 0:
                lines.append(f"  {r[0]}. {r[1]} (en {restante} min)")
            else:
                lines.append(f"  {r[0]}. {r[1]} (AHORA!)")
        return {"respuesta": "Recordatorios:\n" + "\n".join(lines)}

    skill.register_action("listar_recordatorios", "Muestra los recordatorios pendientes", _listar_recordatorios)

    def _revisar_recordatorios():
        """Revisa si hay recordatorios vencidos (se llama al inicio)."""
        conn = _get_db()
        ahora = time.time()
        rows = conn.execute("SELECT id, mensaje FROM recordatorios WHERE activo=1 AND recordar_en <= ?", (ahora,)).fetchall()
        for r in rows:
            conn.execute("UPDATE recordatorios SET activo=0 WHERE id=?", (r[0],))
        conn.commit()
        conn.close()
        if rows:
            return {"respuesta": "⏰ Recordatorios vencidos:\n" + "\n".join(f"  • {r[1]}" for r in rows)}
        return None

    skill.register_action("revisar_recordatorios", "Revisa recordatorios vencidos", _revisar_recordatorios)

    return skill
