"""
Skill — Notas Persistentes
===========================
Guarda y recupera notas personales usando SQLite.
Las notas persisten entre sesiones automaticamente.
"""

import sqlite3
import time
import os
from skills.registry import Skill

DB_PATH = None

def _get_db():
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "notes.db")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS notas (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, contenido TEXT, created REAL)")
    return conn

def register() -> Skill:
    skill = Skill(name="notas", description="Guarda y recupera notas personales", version="1.0.0")

    def _guardar_nota(titulo: str = "", contenido: str = ""):
        conn = _get_db()
        conn.execute("INSERT INTO notas (titulo, contenido, created) VALUES (?, ?, ?)",
                     (titulo or "Sin titulo", contenido or "", time.time()))
        conn.commit()
        conn.close()
        return {"respuesta": f"Nota guardada: {titulo or 'Sin titulo'}"}

    skill.register_action("guardar_nota", "Guarda una nota con titulo y contenido", _guardar_nota,
        parameters={"titulo": {"type": "string"}, "contenido": {"type": "string"}})

    def _listar_notas(limite: int = 5):
        conn = _get_db()
        rows = conn.execute("SELECT id, titulo, created FROM notas ORDER BY created DESC LIMIT ?", (limite,)).fetchall()
        conn.close()
        if not rows:
            return {"respuesta": "No tienes notas guardadas."}
        lines = [f"  {r[0]}. {r[1]} ({time.strftime('%d/%m', time.localtime(r[2]))})" for r in rows]
        return {"respuesta": "Tus notas:\n" + "\n".join(lines)}

    skill.register_action("listar_notas", "Lista las ultimas notas guardadas", _listar_notas,
        parameters={"limite": {"type": "integer", "description": "Cuantas notas mostrar"}})

    def _buscar_nota(query: str = ""):
        conn = _get_db()
        rows = conn.execute("SELECT id, titulo, contenido FROM notas WHERE titulo LIKE ? OR contenido LIKE ? ORDER BY created DESC LIMIT 5",
                           (f"%{query}%", f"%{query}%")).fetchall()
        conn.close()
        if not rows:
            return {"respuesta": f"No encontre notas con: {query}"}
        lines = [f"  {r[0]}. {r[1]}: {r[2][:80]}" for r in rows]
        return {"respuesta": "Notas encontradas:\n" + "\n".join(lines)}

    skill.register_action("buscar_nota", "Busca notas por texto", _buscar_nota,
        parameters={"query": {"type": "string", "description": "Texto a buscar"}})

    return skill
