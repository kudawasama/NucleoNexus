"""
Núcleo Nexus — Embeddings (Búsqueda Semántica Real)
=====================================================
Usa nomic-embed-text (via Ollama) para convertir texto en vectores
y buscar por SIGNIFICADO, no solo por palabras exactas.

Diferencia con TF-IDF:
- TF-IDF: "auto" NO encuentra "coche" (palabras distintas)
- Embeddings: "auto" SI encuentra "coche" (significado similar)

Vision: 'Inteligencia por arquitectura, no por tamaño'
- Sin embeddings: busqueda por keywords
- Con embeddings: busqueda semantica real (como un LLM grande)
"""

import os
import json
import math
import hashlib
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("nexus.memory.embeddings")

# ─── Configuracion ─────────────────────────────────────────
# Endpoint de Ollama para embeddings
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("NEXUS_EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT = 10  # segundos

# Cache de embeddings en memoria (evita recomputar)
_EMBED_CACHE = {}
_CACHE_MAX = 1000


def get_embedding(text: str, model: str = EMBED_MODEL) -> Optional[list]:
    """Obtiene el embedding de un texto via Ollama.

    Args:
        text: Texto a embedir
        model: Modelo de Ollama (default: nomic-embed-text)

    Returns:
        Lista de floats (vector), o None si falla
    """
    if not text or not text.strip():
        return None

    # Cache: si ya calculamos este embedding, devolverlo
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in _EMBED_CACHE:
        return _EMBED_CACHE[cache_key]

    # Si cache esta lleno, limpiar
    if len(_EMBED_CACHE) > _CACHE_MAX:
        _EMBED_CACHE.clear()

    try:
        # Ollama embeddings API
        data = json.dumps({
            "model": model,
            "prompt": text[:2000],  # nomic-embed-text tiene limite
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        embedding = result.get("embedding")
        if embedding and isinstance(embedding, list):
            _EMBED_CACHE[cache_key] = embedding
            return embedding
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.warning(f"Ollama embeddings no disponible: {e}")
    except Exception as e:
        logger.warning(f"Error generando embedding: {e}")

    return None


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Calcula la similitud coseno entre dos vectores.

    Returns:
        Valor entre -1 y 1 (1 = identicos, 0 = sin relacion, -1 = opuestos)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    # Producto punto
    dot = sum(a * b for a, b in zip(vec1, vec2))

    # Normas
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot / (norm1 * norm2)


def is_available() -> bool:
    """Verifica si Ollama + modelo de embeddings esta disponible."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(EMBED_MODEL in m for m in models)
    except Exception:
        return False


def clear_cache():
    """Limpia el cache de embeddings (util para tests)."""
    _EMBED_CACHE.clear()


# ─── Tests ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("Test: get_embedding")
    if is_available():
        e1 = get_embedding("auto")
        e2 = get_embedding("coche")
        e3 = get_embedding("python programming")
        if e1 and e2 and e3:
            sim1 = cosine_similarity(e1, e2)  # auto vs coche
            sim2 = cosine_similarity(e1, e3)  # auto vs python
            print(f"  'auto' vs 'coche' (relacionados):  {sim1:.4f}")
            print(f"  'auto' vs 'python' (no relacionados): {sim2:.4f}")
            assert sim1 > sim2, "auto deberia ser mas similar a coche que a python"
            print("  [OK] embeddings funcionan")
        else:
            print("  [FAIL] no se pudieron generar embeddings")
    else:
        print(f"  [SKIP] Ollama o {EMBED_MODEL} no disponible")
