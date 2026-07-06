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
        row_id = self.episodic.remember(role, content, context, importance)
        
        # 1. Comprobar si se alcanza el 80% de la capacidad de la memoria episódica
        capacity = 10000  # Capacidad por defecto
        try:
            from config import MEMORY
            capacity = MEMORY.get("episodic_limit", 10000)
        except Exception:
            pass
            
        if self.episodic.count() >= 0.8 * capacity:
            self.compress_episodic_memory(capacity)
            
        return row_id

    def compress_episodic_memory(self, capacity: int):
        """Resume conversaciones antiguas en hechos semánticos y libera espacio en la memoria episódica."""
        # Comprimir el 20% más viejo de los mensajes
        to_remove_count = int(capacity * 0.2)
        if to_remove_count <= 0:
            return
            
        import logging
        logger = logging.getLogger("nexus.memory.store")
        logger.info(f"Comprimiendo memoria episódica: se purgarán y resumirán los {to_remove_count} recuerdos más antiguos.")
        
        # 1. Obtener los registros más antiguos
        cur = self.episodic.conn.cursor()
        cur.execute(
            "SELECT id, role, content FROM episodic ORDER BY timestamp ASC LIMIT ?",
            (to_remove_count,)
        )
        old_records = cur.fetchall()
        if not old_records:
            return
            
        # 2. Resumir / Extraer hechos de esos registros e insertarlos en la memoria semántica
        from learning.extractor import extract_facts
        extracted_facts = []
        for row in old_records:
            facts = extract_facts(row['content'])
            for fact in facts:
                try:
                    # Guardamos el hecho en la memoria semántica con fuente 'compresion_episodica'
                    # y una confianza moderada (0.4) ya que provienen de interacciones reales
                    self.semantic.learn_fact(fact, category="aprendizaje", confidence=0.4, source="compresion_episodica")
                    extracted_facts.append(fact)
                except Exception:
                    # Ignorar si es un hecho duplicado o contradictorio
                    pass
                    
        # 3. Eliminar los registros de la base de datos de memoria episódica
        record_ids = [row['id'] for row in old_records]
        placeholders = ",".join("?" for _ in record_ids)
        cur.execute(
            f"DELETE FROM episodic WHERE id IN ({placeholders})",
            record_ids
        )
        self.episodic.conn.commit()
        
        # 4. Reconstruir el índice TF-IDF para reflejar los cambios
        from memory.episodic import TFIDFIndex
        self.episodic._index = TFIDFIndex()  # Re-instanciar TFIDFIndex
        self.episodic._index_loaded = False
        self.episodic._load_index()
        
        logger.info(f"Compresión completada. Extrayendo {len(extracted_facts)} hechos e indexando de nuevo.")

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        return self.episodic.recall(query, top_k)

    def get_recent(self, limit: int = 20) -> list[dict]:
        return self.episodic.get_recent(limit)

    def get_conversation_history(self, limit: int = 10) -> list[dict]:
        return self.episodic.get_conversation_history(limit)

    # ─── Delegación a memoria semántica ───────────────────────

    def learn_fact(self, fact: str, category: str = "general",
                   confidence: float = 0.5, source: str = None,
                   **kwargs) -> bool:
        return self.semantic.learn_fact(fact, category, confidence, source, **kwargs)

    def query_knowledge(self, query: str, top_k: int = 3) -> list[dict]:
        return self.semantic.query_knowledge(query, top_k)

    def get_facts_by_category(self, category: str) -> list[dict]:
        return self.semantic.get_facts_by_category(category)

    def get_consolidable_facts(self, min_confidence: float = 0.8) -> list[dict]:
        return self.semantic.get_consolidable_facts(min_confidence)

    def mark_as_consolidated(self, fact_id: int):
        return self.semantic.mark_as_consolidated(fact_id)

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
        """Cierra la conexion SQLite compartida."""
        self.episodic.close()
        # Cerrar la conexion una sola vez (la creo EpisodicMemory)
        if self.episodic.conn is not None:
            try:
                self.episodic.conn.close()
            except Exception:
                pass
        self.semantic.close()
        self.procedural.close()
