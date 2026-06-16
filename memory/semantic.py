"""
Núcleo Nexus — Memoria Semántica
=================================
Almacenamiento de hechos, conceptos y relaciones.
Cada hecho tiene un nivel de confianza que aumenta con la repetición.
"""

import sqlite3
import json
import time
import logging

logger = logging.getLogger("nexus.memory.semantic")


class SemanticMemory:
    """Memoria semántica — hechos y conceptos con confianza."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def _init_table(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fact        TEXT UNIQUE NOT NULL,
                category    TEXT DEFAULT 'general',
                confidence  REAL DEFAULT 0.5,
                source      TEXT,
                created_at  REAL,
                updated_at  REAL,
                access_count INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def learn_fact(self, fact: str, category: str = "general",
                   confidence: float = 0.5, source: str = None) -> bool:
        cur = self.conn.cursor()
        now = time.time()
        try:
            cur.execute(
                "INSERT INTO semantic (fact, category, confidence, source, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (fact, category, confidence, source, now, now)
            )
            self.conn.commit()
            logger.info(f"Nuevo hecho aprendido [{category}]: {fact[:60]}...")
            return True
        except sqlite3.IntegrityError:
            # Reforzar confianza
            cur.execute(
                "UPDATE semantic SET confidence = MIN(1.0, confidence + 0.1), "
                "updated_at = ?, access_count = access_count + 1 "
                "WHERE fact = ?",
                (now, fact)
            )
            self.conn.commit()
            return True

    def query_knowledge(self, query: str, top_k: int = 3) -> list[dict]:
        """Busca hechos por coincidencia de términos.
        Si query está vacío, devuelve los hechos más recientes.
        """
        cur = self.conn.cursor()

        if not query or not query.strip():
            cur.execute(
                "SELECT id, fact, category, confidence, source, created_at "
                "FROM semantic ORDER BY confidence DESC, created_at DESC LIMIT ?",
                (top_k * 3,)
            )
            results = []
            for row in cur.fetchall():
                results.append({
                    "doc_id": f"sem_{row['id']}",
                    "text": row['fact'],
                    "metadata": {
                        "category": row['category'],
                        "type": "semantic",
                        "confidence": row['confidence'],
                        "source": row['source'],
                    },
                    "score": row['confidence'],
                })
            return results[:top_k]

        terms = query.lower().split()
        results = []
        for term in terms:
            if len(term) < 3:
                continue
            cur.execute(
                "SELECT id, fact, category, confidence, source, created_at "
                "FROM semantic WHERE LOWER(fact) LIKE ? ORDER BY confidence DESC "
                "LIMIT ?", (f"%{term}%", top_k)
            )
            for row in cur.fetchall():
                results.append(dict(row))

        # Deduplicar y ordenar por confianza
        seen = set()
        unique = []
        for r in results:
            if r['id'] not in seen:
                seen.add(r['id'])
                unique.append({
                    "doc_id": f"sem_{r['id']}",
                    "text": r['fact'],
                    "metadata": {
                        "category": r['category'],
                        "type": "semantic",
                        "confidence": r['confidence'],
                        "source": r['source'],
                    },
                    "score": r['confidence'],
                })
        unique.sort(key=lambda x: x['score'], reverse=True)
        return unique[:top_k]

    def get_facts_by_category(self, category: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT fact, confidence, source, created_at FROM semantic "
            "WHERE category = ? ORDER BY confidence DESC LIMIT 100",
            (category,)
        )
        return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM semantic")
        return cur.fetchone()[0]

    def close(self):
        pass
