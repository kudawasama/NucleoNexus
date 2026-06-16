#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nucleo Nexus -- Punto de Entrada
=================================
Inicializa todos los componentes y lanza la interfaz.

Arquitectura:
+---------------------------------------------------------------+
|                     INTERFAZ                                   |
|             (CLI / API / Web)                                 |
+---------------------------------------------------------------+
|                   CAPA COGNITIVA                               |
|  +----------+  +----------+  +-----------------------------+  |
|  | Simbolico |  |   SLM    |  | Inyector de               |  |
|  | (default) |  | (Qwen,   |  | Contexto                   |  |
|  |           |  |  Phi...) |  | Dinamico                   |  |
|  +----------+  +----------+  +-----------------------------+  |
+---------------------------------------------------------------+
|                  SKILLS / ACCIONES                             |
|      (Function Calling . Registry . Builtins)                 |
+---------------------------------------------------------------+
|                MOTOR DE ESTADO                                 |
|   (JSON persistente . Metricas . Fases)                      |
+---------------------------------------------------------------+
|                MEMORIA PERSISTENTE                             |
|  +----------+  +----------+  +-----------------------------+  |
|  |Epi-sodica|  |Semantica |  |Procedimental               |  |
|  | (Que     |  | (Hechos) |  | (Como hacer)               |  |
|  |  paso)   |  |          |  |                             |  |
|  +----------+  +----------+  +-----------------------------+  |
|              SQLite + TF-IDF                                   |
+---------------------------------------------------------------+
|              SISTEMA (archivos, DB)                            |
+---------------------------------------------------------------+
"""

import sys
import os
import logging
from pathlib import Path

# Asegurar que el directorio raiz esta en el path
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import ENGINE, MEMORY, LEARNING, INTERFACE, SYSTEM, LOG_LEVEL, LOG_FILE, MEMORY_DB_PATH, DATA_DIR, SKILLS_DIR
from engine.state import StateEngine
from engine.actions import ActionRegistry
from memory.store import NexusMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.procedural import ProceduralMemory
from cognition.symbolic import SymbolicEngine
from cognition.slm import SLMBackend
from cognition.context import ContextBuilder
from skills.registry import SkillRegistry
from interface.cli import NexusCLI


# --- Logging ---------------------------------------------------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ] if LOG_FILE else [logging.StreamHandler()],
)
logger = logging.getLogger("nexus")


class NexusCore:
    """Nucleo central de Nexus. Coordina todos los subsistemas."""

    def __init__(self):
        logger.info(f"{SYSTEM['name']} v{SYSTEM['version']} inicializando...")

        # 1. Motor de Estado
        self.state = StateEngine(str(DATA_DIR / "state"))
        logger.info("OK Motor de Estado")

        # 2. Memoria Persistente
        self.memory = NexusMemory(MEMORY_DB_PATH)
        logger.info("OK Memoria Persistente")

        # 3. Registro de Skills
        self.skills = SkillRegistry()
        self._load_skills()
        logger.info("OK Skills")

        # 4. Registro de Acciones
        self.actions = ActionRegistry()
        self._register_core_actions()
        logger.info("OK Acciones")

        # 5. Backend SLM (opcional)
        self.slm = SLMBackend(ENGINE.get("llm", {}))
        logger.info("OK Backend SLM (standby)")

        # 6. Motor Simbolico (default)
        self.symbolic = SymbolicEngine(self.state, self.memory)
        logger.info("OK Motor Simbolico")

        # 7. Inyector de Contexto
        self.context = ContextBuilder(self.state, self.skills, self.memory)
        logger.info("OK Inyector de Contexto")

        # Actualizar estado inicial
        self.state.set("nexus", "total_skills", value=len(self.skills.list()))
        self.state.set("knowledge_stats", "skills_learned", value=len(self.skills.list()))

        logger.info(f"{SYSTEM['name']} listo. Fase: {self.state.get('nexus', 'phase')}")

    def _load_skills(self):
        """Carga las skills nativas y las registra."""
        self.skills.load_builtins(str(SKILLS_DIR / "builtins"))

    def _register_core_actions(self):
        """Registra acciones del nucleo (accesibles desde cualquier skill)."""

        # Accion: aprender un hecho
        def _learn_fact(fact: str, category: str = "general"):
            success = self.memory.learn_fact(fact, category, source="usuario")
            if success:
                self.state.increment("nexus", "total_learned_facts")
            return {"learned": success, "fact": fact[:60]}

        self.actions.register_fn(
            name="learn_fact",
            description="Aprende un nuevo hecho o concepto",
            handler=_learn_fact,
            parameters={
                "fact": {"type": "string", "description": "El hecho a aprender"},
                "category": {"type": "string", "description": "Categoria del hecho"},
            },
        )

        # Accion: recordar algo
        def _recall(query: str):
            results = self.memory.recall(query, top_k=3)
            return {"memories": results}

        self.actions.register_fn(
            name="recall",
            description="Busca recuerdos relacionados con un tema",
            handler=_recall,
            parameters={
                "query": {"type": "string", "description": "Tema a buscar en la memoria"},
            },
        )

        # Accion: obtener estado
        def _get_status():
            return self.state.get_snapshot()

        self.actions.register_fn(
            name="get_nexus_status",
            description="Obtiene el estado completo de Nexus",
            handler=_get_status,
        )

    def process(self, user_input: str) -> str:
        """Procesa la entrada del usuario y genera respuesta.

        Flujo:
        1. Construye contexto inyectable (estado + memoria + skills)
        2. Decide backend segun configuracion (symbolic | slm | hybrid)
        3. Ejecuta acciones si es necesario
        4. Aprende de la interaccion
        5. Devuelve respuesta
        """
        backend_mode = self.state.get("capabilities", "backend", default="symbolic")

        if backend_mode == "slm" and self.slm and self.slm.loaded:
            # Construir contexto para el SLM
            system_prompt = self.context.build(user_input)
            # Generar con SLM
            response = self.slm.generate(user_input, system_prompt=system_prompt)
            if response:
                self.memory.remember("user", user_input, context={"backend": "slm"})
                self.memory.remember("nexus", response, context={"backend": "slm"})
                self.state.record_interaction(success=True)
                self.state.evolve_phase()
                return response
            else:
                # Fallback a simbolico si SLM falla
                logger.warning("SLM fallo, usando modo simbolico como fallback")

        # Modo simbolico (default o fallback)
        return self.symbolic.process(user_input, actions_registry=self.actions)

    def reset(self):
        """Reinicia Nexus a su estado inicial."""
        self.state.reset()
        logger.info("Nexus reiniciado (estado, no memoria)")

    def shutdown(self):
        """Apaga Nexus limpiamente."""
        logger.info("Apagando Nexus...")
        if self.slm:
            self.slm.unload()
        self.memory.close()
        logger.info("Nexus apagado.")


def main():
    """Punto de entrada principal."""
    try:
        nexus = NexusCore()
        cli = NexusCLI(nexus)
        cli.run()
    except KeyboardInterrupt:
        print("\n\nApagando Nexus...")
    except Exception as e:
        logger.critical(f"Error fatal: {e}", exc_info=True)
        print(f"\nError fatal: {e}")
        return 1
    finally:
        if 'nexus' in locals():
            nexus.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
