"""
Skill — Todo List
==================
Lista de tareas pendientes persistente en SQLite.
CRUD completo: agregar, listar, completar, eliminar.
"""

import sqlite3
import time
import os
from skills.registry import Skill

DB_PATH = None


def _get_db():
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "todos.db")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, tarea TEXT, creado REAL, completado INTEGER DEFAULT 0)")
    return conn


def register() -> Skill:
    skill = Skill(name="todos", description="Lista de tareas pendientes", version="1.0.0")

    def _agregar_tarea(tarea: str = ""):
        if not tarea.strip():
            return {"respuesta": "Que tarea quieres agregar?"}
        conn = _get_db()
        conn.execute("INSERT INTO todos (tarea, creado) VALUES (?, ?)", (tarea, time.time()))
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM todos WHERE completado=0").fetchone()[0]
        conn.close()
        return {"respuesta": f"Tarea agregada: '{tarea}' (pendientes: {count})"}

    skill.register_action("agregar_tarea", "Agrega una tarea a la lista", _agregar_tarea,
        parameters={"tarea": {"type": "string", "description": "Descripcion de la tarea"}})

    def _listar_tareas():
        conn = _get_db()
        rows = conn.execute("SELECT id, tarea, creado FROM todos WHERE completado=0 ORDER BY creado DESC LIMIT 20").fetchall()
        conn.close()
        if not rows:
            return {"respuesta": "No tienes tareas pendientes. Buen trabajo! 🎉"}
        lines = []
        for r in rows:
            fecha = time.strftime("%d/%m", time.localtime(r[2]))
            lines.append(f"  {r[0]}. {r[1]} ({fecha})")
        return {"respuesta": f"Tareas pendientes ({len(rows)}):\n" + "\n".join(lines)}

    skill.register_action("listar_tareas", "Muestra las tareas pendientes", _listar_tareas)

    def _completar_tarea(id_tarea: int = 0):
        conn = _get_db()
        cur = conn.execute("UPDATE todos SET completado=1 WHERE id=? AND completado=0", (id_tarea,))
        conn.commit()
        affected = cur.rowcount
        conn.close()
        if affected:
            return {"respuesta": f"Tarea #{id_tarea} completada! ✅"}
        return {"respuesta": f"Tarea #{id_tarea} no encontrada o ya completada."}

    skill.register_action("completar_tarea", "Marca una tarea como completada", _completar_tarea,
        parameters={"id_tarea": {"type": "integer", "description": "Numero de la tarea"}})

    def _eliminar_tarea(id_tarea: int = 0):
        conn = _get_db()
        cur = conn.execute("DELETE FROM todos WHERE id=?", (id_tarea,))
        conn.commit()
        affected = cur.rowcount
        conn.close()
        if affected:
            return {"respuesta": f"Tarea #{id_tarea} eliminada."}
        return {"respuesta": f"Tarea #{id_tarea} no encontrada."}

    skill.register_action("eliminar_tarea", "Elimina una tarea de la lista", _eliminar_tarea,
        parameters={"id_tarea": {"type": "integer", "description": "Numero de la tarea"}})

    return skill
