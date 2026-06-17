"""
Núcleo Nexus — Memoria Procedimental
=====================================
Patrones de respuesta aprendidos de interacciones.
Cada patrón tiene efectividad que sube o baja según su uso.
"""

import sqlite3
import json
import re
import time
import logging
from typing import Optional

logger = logging.getLogger("nexus.memory.procedural")


class ProceduralMemory:
    """Memoria procedural — patrones aprendidos y skills adquiridas."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def _init_table(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS procedural (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                pattern     TEXT NOT NULL,
                response    TEXT NOT NULL,
                triggers    TEXT,
                effectiveness REAL DEFAULT 0.5,
                created_at  REAL,
                updated_at  REAL,
                use_count   INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def learn_pattern(self, name: str, pattern: str, response: str,
                      triggers: list[str] = None) -> bool:
        cur = self.conn.cursor()
        now = time.time()
        try:
            cur.execute(
                "INSERT INTO procedural (name, pattern, response, triggers, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, pattern, response, json.dumps(triggers or []), now, now)
            )
            self.conn.commit()
            logger.info(f"Nuevo patrón aprendido: {name}")
            return True
        except sqlite3.IntegrityError:
            cur.execute(
                "UPDATE procedural SET pattern = ?, response = ?, "
                "triggers = ?, updated_at = ? WHERE name = ?",
                (pattern, response, json.dumps(triggers or []), now, name)
            )
            self.conn.commit()
            return True

    def find_pattern(self, input_text: str) -> Optional[dict]:
        """Busca un patrón que coincida con el texto de entrada."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT name, pattern, response, triggers, effectiveness, use_count "
            "FROM procedural ORDER BY effectiveness DESC"
        )
        for row in cur.fetchall():
            triggers = json.loads(row['triggers'] or '[]')
            for trigger in triggers:
                if trigger.lower() in input_text.lower():
                    return dict(row)
            # Regex
            try:
                if re.search(row['pattern'], input_text, re.IGNORECASE):
                    return dict(row)
            except re.error:
                pass
        return None

    def reinforce_pattern(self, name: str, success: bool):
        cur = self.conn.cursor()
        delta = 0.05 if success else -0.03
        cur.execute(
            "UPDATE procedural SET effectiveness = "
            "MAX(0.0, MIN(1.0, effectiveness + ?)), "
            "use_count = use_count + 1, updated_at = ? WHERE name = ?",
            (delta, time.time(), name)
        )
        self.conn.commit()

    def count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM procedural")
        return cur.fetchone()[0]

    def close(self):
        # conn compartida con NexusMemory — cerrar alli
        pass
