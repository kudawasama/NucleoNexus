#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recargador de Conocimiento → BD de Nexus
=========================================
Carga todos los archivos JSON de data/knowledge/ directamente
en la base de datos SQLite de Nexus, sin necesidad de reiniciar.

Útil después de ejecutar los scripts de carga masiva
(cargar_wikipedia.py, cargar_conceptnet.py).

Uso:
    python scripts/recargar_conocimiento.py
"""

import sys
import json
import logging
from pathlib import Path

# ─── Setup ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from config import MEMORY_DB_PATH, KNOWLEDGE_DIR, STATE_DIR
from memory.store import NexusMemory
from engine.state import StateEngine
from knowledge.loader import load_knowledge_to_memory

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("recarga")


def main():
    print("=" * 60)
    print("  RECARGADOR — JSON → BD de Nexus")
    print("=" * 60)
    print(f"  DB: {MEMORY_DB_PATH}")
    print(f"  JSON: {KNOWLEDGE_DIR}")
    print()

    # 1. Cargar BD
    memory = NexusMemory(MEMORY_DB_PATH)
    antes = memory.semantic.count()
    print(f"  Hechos en BD antes: {antes}")

    # 2. Cargar todos los JSON
    facts_loaded = load_knowledge_to_memory(memory, str(KNOWLEDGE_DIR))
    despues = memory.semantic.count()
    nuevos = despues - antes

    print(f"  Hechos procesados: {facts_loaded}")
    print(f"  Hechos NUEVOS en BD: {nuevos}")
    print(f"  Hechos en BD después: {despues}")

    # 3. Actualizar estado
    state = StateEngine(str(STATE_DIR))
    real_stats = memory.stats()
    state.set("knowledge_stats", "semantic_facts", value=real_stats["semantic"])
    state.set("knowledge_stats", "episodic_memories", value=real_stats["episodic"])
    state.set("knowledge_stats", "initial_facts", value=real_stats["semantic"])
    state.set("nexus", "total_learned_facts", value=real_stats["semantic"])

    # 4. Mostrar distribución por categoría
    print()
    print("  Distribución por categoría:")
    print("  " + "-" * 40)
    import sqlite3
    conn = sqlite3.connect(MEMORY_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT category, COUNT(*) as cnt FROM semantic "
        "GROUP BY category ORDER BY cnt DESC"
    )
    for row in cur.fetchall():
        print(f"    {row[0]:<30s} {row[1]:>5d}")
    conn.close()

    print()
    print(f"  ✅ Estado actualizado: {real_stats['semantic']} hechos semánticos")
    print(f"  📁 Archivos JSON en: {KNOWLEDGE_DIR}")
    for jf in sorted(Path(KNOWLEDGE_DIR).glob("*.json")):
        try:
            with open(jf, encoding="utf-8") as f:
                count = len(json.load(f))
            print(f"     {jf.name:<35s} {count:>4d} hechos")
        except Exception:
            print(f"     {jf.name:<35s} ERROR")
    print("=" * 60)


if __name__ == "__main__":
    main()
