"""
Núcleo Nexus — Módulo de Embeddings Vectoriales
================================================
Genera embeddings usando nomic-embed-text (Ollama) y
realiza búsqueda semántica por similitud de coseno.

Reemplaza la búsqueda TF-IDF con búsqueda por significado.
"""
import json
import sqlite3
import logging
import time
import math
from typing import List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger("nexus.memory.embeddings")

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768  # nomic-embed-text output dimension


def get_embedding(text: str) -> Optional[List[float]]:
    """Genera embedding para un texto usando nomic-embed-text.
    
    Args:
        text: Texto a vectorizar
        
    Returns:
        Lista de floats (768 dimensiones) o None si falla
    """
    if not text or not text.strip():
        return None
    
    payload = json.dumps({
        "model": EMBED_MODEL,
        "input": text[:2048],  # Limitar a 2048 chars
    }).encode()
    
    try:
        req = Request(OLLAMA_URL, data=payload,
                     headers={"Content-Type": "application/json"})
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data["embeddings"][0]
    except Exception as e:
        logger.warning(f"Error generando embedding: {e}")
        return None


def is_available() -> bool:
    """Verifica si el modelo de embeddings esta disponible en Ollama."""
    try:
        payload = json.dumps({"model": EMBED_MODEL, "input": "test"}).encode()
        req = Request(OLLAMA_URL, data=payload,
                     headers={"Content-Type": "application/json"})
        resp = urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calcula similitud coseno entre dos vectores."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_to_blob(embedding: List[float]) -> bytes:
    """Convierte embedding a BLOB para SQLite."""
    return json.dumps(embedding).encode()


def blob_to_embed(blob: bytes) -> List[float]:
    """Convierte BLOB de SQLite a embedding."""
    return json.loads(blob.decode())


class EmbeddingIndex:
    """Índice de embeddings en memoria para búsqueda rápida.
    
    Mantiene todos los embeddings cargados para calcular
    similitud coseno sin consultas SQL complejas.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._vectors: List[tuple] = []  # [(id, embedding, text)]
        self._loaded = False
    
    def load(self):
        """Carga todos los embeddings desde la DB."""
        if self._loaded:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, fact, embedding FROM semantic WHERE embedding IS NOT NULL")
            count = 0
            for row in cur.fetchall():
                doc_id, text, blob = row
                if blob:
                    emb = blob_to_embed(blob)
                    self._vectors.append((doc_id, emb, text))
                    count += 1
            conn.close()
            self._loaded = True
            logger.info(f"Cargados {count} embeddings en índice")
        except Exception as e:
            logger.warning(f"Error cargando embeddings: {e}")
    
    def add(self, doc_id: int, embedding: List[float], text: str):
        """Agrega un embedding al índice en memoria."""
        self._vectors.append((doc_id, embedding, text))
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[dict]:
        """Busca los top_k vectores más similares por coseno."""
        if not self._vectors:
            return []
        
        scores = []
        for doc_id, vec, text in self._vectors:
            sim = cosine_similarity(query_embedding, vec)
            scores.append((sim, doc_id, text))
        
        scores.sort(reverse=True)
        results = []
        for sim, doc_id, text in scores[:top_k]:
            results.append({
                "doc_id": doc_id,
                "text": text[:200],
                "score": round(sim, 4),
            })
        return results
    
    def count(self) -> int:
        return len(self._vectors)
