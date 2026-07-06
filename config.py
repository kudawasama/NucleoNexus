"""
Nucleo Nexus -- Configuracion Central
======================================
Toda la configuracion del sistema en un solo lugar.
A medida que Nexus evoluciona, aqui se agregan nuevas opciones.
"""

import os
from pathlib import Path

# Versionado automatico desde git
from version import FULL_VERSION, COMMIT

# --- Rutas base -----------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = DATA_DIR / "memory"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
STATE_DIR = DATA_DIR / "state"
LOGS_DIR = DATA_DIR / "logs"
SKILLS_DIR = BASE_DIR / "skills"

# Asegurar que existan
for d in [DATA_DIR, MEMORY_DIR, KNOWLEDGE_DIR, STATE_DIR, LOGS_DIR, SKILLS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- Base de datos --------------------------------------------
MEMORY_DB_PATH = str(MEMORY_DIR / "nexus_memory.db")
KNOWLEDGE_DB_PATH = str(KNOWLEDGE_DIR / "nexus_knowledge.db")

# --- Motor de IA ----------------------------------------------
ENGINE = {
    "mode": "hybrid",            # "symbolic" | "hybrid" | "llm"
    "symbolic": {
        "max_patterns": 5000,    # Maximo de patrones aprendidos
        "min_confidence": 0.15,  # Confianza minima para responder
        "learning_rate": 0.1,    # Que tan rapido aprende (0-1)
    },
    "llm": {
        "backend": "ollama",     # "ollama" | "llamacpp" | "openai" | None
        "model_path": None,      # Ruta al modelo GGUF
        "model_name": "hermes3:3b",  # 🏆 Mejor modelo local (131K ctx, agent-optimized)
        "api_base": "http://localhost:11434/v1",  # Ollama local
        "api_key": "not-needed", # Ollama no requiere API key
        "max_tokens": 4096,
        "temperature": 0.7,
    }
}

# --- Memoria --------------------------------------------------
MEMORY = {
    "episodic_limit": 10000,
    "semantic_limit": 5000,
    "vector_dim": 256,
    "similarity_top_k": 5,
    "decay_rate": 0.99,
}

# --- Umbrales y Algoritmos (Thresholds) --------------------------
THRESHOLDS = {
    "semantic_deduplication": 0.88,  # Similitud coseno mínima para considerar un hecho duplicado
    "embedding_min_match": 0.50,     # Similitud coseno mínima para considerar un hecho relevante en vector query
    "reinforce_increment": 0.1,      # Incremento de confianza ante repetición / duplicados
    "reinforce_decrement": 0.1,      # Decremento de confianza ante penalizaciones
    "consolidation_min_conf": 0.8,   # Confianza mínima para consolidar hecho de runtime a JSON
}

# --- Aprendizaje ----------------------------------------------
LEARNING = {
    "pattern_extraction": True,
    "concept_mining": True,
    "reinforcement": True,
    "auto_skill_create": False,
    "feedback_tracking": True,
}

# --- Interfaz -------------------------------------------------
INTERFACE = {
    "type": "cli",
    "cli": {
        "prompt": "Nexus> ",
        "history_file": str(MEMORY_DIR / ".nexus_history"),
        "max_history": 1000,
        "colors": True,
    },
    "api": {
        "host": "127.0.0.1",
        "port": 8712,
        "workers": 1,
    }
}

# --- Logging --------------------------------------------------
LOG_LEVEL = "INFO"
LOG_FILE = str(LOGS_DIR / "nexus.log")

# --- Estado del sistema ---------------------------------------
SYSTEM = {
    "name": "Nucleo Nexus",
    "version": FULL_VERSION,
    "commit": COMMIT,
    "phase": "Proto",
    "author": "Jose Cespedes",
    "description": "Sistema de IA ultraligero con aprendizaje incremental",
    "repository": "https://github.com/kudawasama/NucleoNexus",
}
