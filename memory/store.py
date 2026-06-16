"""
Núcleo Nexus — Almacén de Memoria Persistente
===============================================
Sistema completo de memoria con SQLite + TF-IDF.
Implementa los tres tipos de memoria del modelo arquitectónico:
- Episódica: registro de interacciones
- Semántica: hechos y conceptos
- Procedimental: patrones y habilidades
"""

from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.procedural import ProceduralMemory


class NexusMemory:
    """Fachada unificada para los tres tipos de memoria."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.episodic = EpisodicMemory(db_path)
        self.semantic = SemanticMemory(db_path)
        self.procedural = ProceduralMemory(db_path)
        # Inicializar todas las tablas
        self.episodic._init_table()
        self.semantic._init_table()
        self.procedural._init_table()

    # ─── Delegación a memoria episódica ───────────────────────

    def remember(self, role: str, content: str, context: dict = None,
                 importance: float = 1.0) -> int:
        return self.episodic.remember(role, content, context, importance)

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        return self.episodic.recall(query, top_k)

    def get_recent(self, limit: int = 20) -> list[dict]:
        return self.episodic.get_recent(limit)

    def get_conversation_history(self, limit: int = 10) -> list[dict]:
        return self.episodic.get_conversation_history(limit)

    # ─── Delegación a memoria semántica ───────────────────────

    def learn_fact(self, fact: str, category: str = "general",
                   confidence: float = 0.5, source: str = None) -> bool:
        return self.semantic.learn_fact(fact, category, confidence, source)

    def query_knowledge(self, query: str, top_k: int = 3) -> list[dict]:
        return self.semantic.query_knowledge(query, top_k)

    def get_facts_by_category(self, category: str) -> list[dict]:
        return self.semantic.get_facts_by_category(category)

    # ─── Delegación a memoria procedural ──────────────────────

    def learn_pattern(self, name: str, pattern: str, response: str,
                      triggers: list[str] = None) -> bool:
        return self.procedural.learn_pattern(name, pattern, response, triggers)

    def find_pattern(self, input_text: str):
        return self.procedural.find_pattern(input_text)

    def reinforce_pattern(self, name: str, success: bool):
        return self.procedural.reinforce_pattern(name, success)

    # ─── Estadísticas ─────────────────────────────────────────

    def stats(self) -> dict:
        eps = self.episodic.count()
        sem = self.semantic.count()
        pro = self.procedural.count()
        return {
            "episodic": eps,
            "semantic": sem,
            "procedural": pro,
            "total": eps + sem + pro,
        }

    def close(self):
        self.episodic.close()
        self.semantic.close()
        self.procedural.close()
