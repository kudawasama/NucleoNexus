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
        """Busca hechos por relevancia semántica de términos significativos.
        
        Filtra palabras vacías (stop words) para evitar matches por 'que', 'es', etc.
        Normaliza acentos para búsqueda robusta.
        El score refleja cuántos términos significativos de la query aparecen en el hecho.
        """
        cur = self.conn.cursor()
        import re as _re

        # Normalizar acentos para matching
        def _norm(t: str) -> str:
            return (t.replace('á','a').replace('é','e').replace('í','i')
                    .replace('ó','o').replace('ú','u').replace('ü','u')
                    .replace('¿','').replace('?','').replace('!','')
                    .replace('.','').replace(',',''))

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

        # Stop words: palabras tan comunes que no aportan significado
        stop_words = {
            'que', 'qué', 'es', 'son', 'las', 'los', 'una', 'uno', 'unas',
            'por', 'para', 'con', 'del', 'sus', 'le', 'como', 'cómo',
            'esta', 'este', 'entre', 'todo', 'tiene', 'cada', 'sin',
            'mas', 'más', 'pero', 'era', 'han', 'has', 'sea', 'fue',
            'ello', 'ante', 'tras', 'segun', 'durante', 'mediante',
            'dónde', 'donde', 'cuándo', 'cuando', 'cuál', 'cual',
        }

        # Extraer términos significativos (≥3 caracteres, sin stop words)
        all_terms = _re.findall(r'[a-záéíóúñü0-9]{3,}', query.lower())
        terms = []
        for t in all_terms:
            tn = _norm(t)
            if tn not in stop_words:
                terms.append(tn)

        # Si no quedan términos, usar todos (incluyendo stop words)
        if not terms:
            terms = [_norm(t) for t in all_terms]
        if not terms:
            return []

        # Buscar facts que contengan al menos uno de los términos
        results = []
        seen_ids = set()

        # Enfoque simple: cargar hechos una vez, filtrar en Python
        cur.execute(
            "SELECT id, fact, category, confidence, source, created_at "
            "FROM semantic ORDER BY confidence DESC"
        )
        all_rows = cur.fetchall()

        for row in all_rows:
            fact_lower = _norm(row['fact'].lower())
            # Contar cuántos términos significativos aparecen en el hecho
            matches = sum(1 for t in terms if t in fact_lower)
            if matches > 0:
                relevance = matches / len(terms)
                # Penalizar si solo matchean términos de 3 letras comunes
                if matches == 1 and len(terms) > 2:
                    # Un solo match entre muchos términos → muy probablemente irrelevante
                    relevance *= 0.3
                results.append({
                    "doc_id": f"sem_{row['id']}",
                    "text": row['fact'],
                    "metadata": {
                        "category": row['category'],
                        "type": "semantic",
                        "confidence": row['confidence'],
                        "source": row['source'],
                    },
                    "score": round(relevance, 4),
                })

        # Ordenar por relevancia, luego por confianza
        results.sort(key=lambda x: (x['score'], x['metadata']['confidence']), reverse=True)
        return results[:top_k]

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
        # conn compartida con NexusMemory — cerrar alli
        pass
