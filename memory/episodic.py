"""
Núcleo Nexus — Memoria Episódica
=================================
Registro cronológico de interacciones con el usuario.
Cada "recuerdo" es una interacción completa con timestamp.
"""

import sqlite3
import json
import time
import math
import re
import logging
from collections import Counter, defaultdict

logger = logging.getLogger("nexus.memory.episodic")


class TFIDFIndex:
    """Índice TF-IDF liviano para búsqueda semántica sin dependencias."""

    def __init__(self):
        self.doc_freqs = Counter()
        self.term_docs = defaultdict(set)
        self.doc_vectors = {}
        self.doc_texts = {}
        self.doc_metadata = {}
        self.total_docs = 0
        self._built = False
        self._max_docs = 10000

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        return re.findall(r'\b[a-záéíóúñü]{3,}\b|\b\d{2,}\b', text)

    def add_document(self, doc_id: str, text: str, metadata: dict = None):
        if self.total_docs >= self._max_docs:
            return
        tokens = self._tokenize(text)
        unique_terms = set(tokens)
        for term in unique_terms:
            self.doc_freqs[term] += 1
            self.term_docs[term].add(doc_id)
        self.doc_texts[doc_id] = text
        self.doc_metadata[doc_id] = metadata or {}
        self.total_docs += 1
        self._built = False

    def build(self):
        if self.total_docs == 0:
            return
        for doc_id, text in self.doc_texts.items():
            tokens = self._tokenize(text)
            term_counts = Counter(tokens)
            vector = {}
            for term, count in term_counts.items():
                tf = 1 + math.log10(count) if count > 0 else 0
                idf = math.log10(self.total_docs / (1 + self.doc_freqs.get(term, 0)))
                vector[term] = tf * idf
            self.doc_vectors[doc_id] = vector
        self._built = True

    def _cosine_similarity(self, vec_a: dict, vec_b: dict) -> float:
        terms = set(vec_a.keys()) & set(vec_b.keys())
        if not terms:
            return 0.0
        dot = sum(vec_a[t] * vec_b[t] for t in terms)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._built:
            self.build()
        if self.total_docs == 0:
            return []
        query_tokens = self._tokenize(query)
        query_counts = Counter(query_tokens)
        query_vec = {}
        for term, count in query_counts.items():
            tf = 1 + math.log10(count) if count > 0 else 0
            idf = math.log10(self.total_docs / (1 + self.doc_freqs.get(term, 0)))
            query_vec[term] = tf * idf
        scores = []
        for doc_id, doc_vec in self.doc_vectors.items():
            sim = self._cosine_similarity(query_vec, doc_vec)
            if sim > 0:
                scores.append((sim, doc_id))
        scores.sort(reverse=True)
        results = []
        for sim, doc_id in scores[:top_k]:
            results.append({
                "doc_id": doc_id,
                "text": self.doc_texts.get(doc_id, ""),
                "metadata": self.doc_metadata.get(doc_id, {}),
                "score": round(sim, 4),
            })
        return results


class EpisodicMemory:
    """Memoria episódica — recuerdos de interacciones en orden cronológico."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._index = TFIDFIndex()
        self._index_loaded = False

    def _init_table(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS episodic (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                context     TEXT,
                importance  REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0,
                last_access  REAL
            )
        """)
        self.conn.commit()
        self._load_index()

    def _load_index(self):
        if self._index_loaded:
            return
        cur = self.conn.cursor()
        cur.execute("SELECT id, content, role FROM episodic ORDER BY id DESC LIMIT 5000")
        for row in cur.fetchall():
            self._index.add_document(
                doc_id=f"ep_{row['id']}",
                text=row['content'],
                metadata={"role": row['role'], "type": "episodic"}
            )
        self._index.build()
        self._index_loaded = True

    def remember(self, role: str, content: str, context: dict = None,
                 importance: float = 1.0) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO episodic (timestamp, role, content, context, importance) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), role, content, json.dumps(context or {}), importance)
        )
        self.conn.commit()
        doc_id = f"ep_{cur.lastrowid}"
        self._index.add_document(doc_id, content, {"role": role, "type": "episodic"})
        return cur.lastrowid

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._index_loaded:
            self._load_index()
        results = self._index.search(query, top_k=top_k)
        return [r for r in results if r["metadata"].get("type") == "episodic"]

    def get_recent(self, limit: int = 20) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, timestamp, role, content, context, importance "
            "FROM episodic ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

    def get_conversation_history(self, limit: int = 10) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT role, content, timestamp FROM episodic "
            "ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        history = []
        for r in cur.fetchall():
            label = "Tú" if r['role'] == 'user' else "Nexus"
            history.append({
                "role": r['role'],
                "label": label,
                "content": r['content'],
                "timestamp": r['timestamp'],
            })
        history.reverse()
        return history

    def count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM episodic")
        return cur.fetchone()[0]

    def close(self):
        pass  # conn compartida
