"""
Núcleo Nexus — Cargador de Conocimiento Inicial
================================================
Puebla la memoria semántica con hechos desde archivos JSON.
Cada archivo en data/knowledge/*.json se carga al iniciar.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("nexus.knowledge.loader")

def load_knowledge_to_memory(memory, knowledge_dir: str) -> int:
    """Carga todos los archivos .json de knowledge_dir a la memoria semántica.
    
    Args:
        memory: Instancia de NexusMemory
        knowledge_dir: Ruta al directorio con archivos .json
        
    Returns:
        Cantidad de hechos cargados
    """
    kb_dir = Path(knowledge_dir)
    if not kb_dir.exists():
        logger.warning(f"Directorio de conocimiento no encontrado: {knowledge_dir}")
        return 0

    loaded = 0
    for json_file in sorted(kb_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                facts = json.load(f)
            for item in facts:
                fact = item.get("fact", "").strip()
                if not fact:
                    continue
                category = item.get("category", "general")
                source = item.get("source", "knowledge_base")
                # with_embedding=False: la carga inicial es masiva, no
                # queremos 50+ llamadas a Ollama en cada inicio de Nexus.
                # Los hechos se pueden embeber despues bajo demanda.
                memory.learn_fact(
                    fact, category=category, confidence=0.5, source=source,
                    with_embedding=False, force=True
                )
                loaded += 1
            logger.info(f"Cargados {len(facts)} hechos desde {json_file.name}")
        except Exception as e:
            logger.error(f"Error cargando {json_file}: {e}")

    logger.info(f"Total: {loaded} hechos cargados en memoria semántica")
    return loaded
