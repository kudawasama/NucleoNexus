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
import re
import logging
from pathlib import Path

# Asegurar que el directorio raiz esta en el path
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import ENGINE, MEMORY, LEARNING, INTERFACE, SYSTEM, LOG_LEVEL, LOG_FILE, MEMORY_DB_PATH, DATA_DIR, KNOWLEDGE_DIR, SKILLS_DIR
from engine.state import StateEngine
from engine.actions import ActionRegistry
from memory.store import NexusMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.procedural import ProceduralMemory
from cognition.symbolic import SymbolicEngine
from cognition.slm import SLMBackend
from cognition.context import ContextBuilder
from knowledge.loader import load_knowledge_to_memory
from learning.extractor import learn_from_user_input, learn_from_response, reinforce_from_feedback
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

        # 2b. Cargar conocimiento inicial en memoria semántica
        facts_loaded = load_knowledge_to_memory(self.memory, str(KNOWLEDGE_DIR))
        self.state.set("knowledge_stats", "initial_facts", value=facts_loaded)

        # 3. Registro de Skills
        self.skills = SkillRegistry()
        self._load_skills()
        logger.info("OK Skills")

        # 4. Registro de Acciones (nucleo + skills)
        self.actions = ActionRegistry()
        self._register_core_actions()
        self._register_skill_actions()
        logger.info("OK Acciones")

        # 5. Backend SLM (Ollama local)
        self.slm = SLMBackend(ENGINE.get("llm", {}))
        if self.slm.load():
            logger.info(f"OK SLM cargado ({self.slm.mode}: {self.slm.model_name})")
            # Modo hibrido: intents rapidas en simbolico, resto en SLM
            self.state.set("capabilities", "backend", value="hybrid")
            self.state.set("capabilities", "slm_loaded", value=True)
        else:
            logger.info("OK Backend SLM (standby - symbolic fallback)")

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

    def _register_skill_actions(self):
        """Registra las acciones de todas las skills en el registro central.
        
        Esto permite que el puente intent->skill action en el motor simbolico
        encuentre y ejecute acciones de cualquier skill cargada.
        """
        all_skill_actions = self.skills.get_all_actions()
        for action in all_skill_actions.list():
            self.actions.register(action)
            logger.debug(f"Accion de skill registrada: {action.name}")

    def process(self, user_input: str) -> tuple:
        """Procesa la entrada del usuario y genera respuesta.

        Modos de operacion:
        - symbolic:   solo motor simbolico (sin modelo, sin internet)
        - slm:        solo SLM local (modelo responde todo)
        - hybrid:     intents rapidas en simbolico, general en SLM

        Returns:
            Tuple (response_str, metadata_dict)
        """
        # 1. Generar respuesta según el backend activo
        response, metadata = self._get_response(user_input)

        # 2. Aprender de la interacción (solo desde input del usuario, no del SLM)
        learned_input = learn_from_user_input(user_input, self.memory)
        reinforced = reinforce_from_feedback(user_input, self.memory)

        # 3. Registrar en memoria episódica
        self.memory.remember("user", user_input, context={"backend": "main"})
        self.memory.remember("nexus", response, context={"backend": "main"})

        # 4. Actualizar estado
        self.state.record_interaction(success=True)
        self.state.evolve_phase()

        return response, metadata

    def _get_response(self, user_input: str) -> tuple:
        """Selecciona y ejecuta el backend adecuado según el modo actual.
        
        Returns:
            Tuple (response_str, metadata_dict)
        """
        # Metadata base
        metadata = {
            "backend": "symbolic",
            "model": None,
            "tokens_prompt": 0,
            "tokens_generated": 0,
            "duration_ms": 0,
            "total_duration_ms": 0,
        }
        backend_mode = self.state.get("capabilities", "backend", default="symbolic")

        # --- HYBRID: intent -> simbolico, resto -> SLM (ReAct) ---
        if backend_mode == "hybrid" and self.slm and self.slm.loaded:
            intent = self.symbolic.detect_intent(user_input.lower().strip())
            fast_intents = {"saludo", "despedida", "agradecimiento", "presentacion",
                            "hora", "calcular", "fase", "ayuda", "memoria",
                            "nombre", "reset", "personalidad", "confianza",
                            "estado", "clima"}
            if intent in fast_intents:
                # Excepción: "calcular" sin números → es conceptual (explicación), no operación
                if intent == "calcular" and not re.search(r'\d+\s*[+\-*/]\s*\d+', user_input):
                    pass  # Dejar que caiga al SLM o búsqueda en memoria
                else:
                    response = self.symbolic.process(user_input, actions_registry=self.actions,
                                                skip_bookkeeping=True)
                    metadata["backend"] = "symbolic"
                    return response, metadata

            # Pregunta sin intent rápido: ver si hay hechos en memoria
            facts = self.memory.query_knowledge(user_input, top_k=2)
            if facts and any(f.get("score", 0) >= 0.15 for f in facts):
                response = self.symbolic.process(user_input, actions_registry=self.actions,
                                            skip_bookkeeping=True)
                metadata["backend"] = "symbolic"
                return response, metadata

            # Sin hechos → SLM con contexto de memoria (structured output)
            try:
                mem_facts = self.memory.query_knowledge(user_input, top_k=3)
                mem_records = self.memory.recall(user_input, top_k=2)
                prompt = self.context.build_react(
                    user_input,
                    memory_facts=mem_facts,
                    memory_records=mem_records,
                )
                # Generar con JSON mode forzado
                slm_result = self.slm.generate(user_input, system_prompt=prompt,
                                            structured=True)
                if slm_result:
                    raw_json = slm_result["response"]
                    metadata["backend"] = "slm"
                    metadata["model"] = slm_result.get("model")
                    metadata["tokens_prompt"] = slm_result.get("tokens_prompt", 0)
                    metadata["tokens_generated"] = slm_result.get("tokens_generated", 0)
                    metadata["duration_ms"] = slm_result.get("duration_ms", 0)
                    metadata["total_duration_ms"] = slm_result.get("total_duration_ms", 0)

                    # Parsear JSON
                    import json as _json
                    try:
                        parsed = _json.loads(raw_json)
                        respuesta = parsed.get("respuesta", "")
                        accion = parsed.get("accion", "ninguna")

                        # Ejecutar acción si aplica
                        if accion == "buscar_memoria":
                            tema = parsed.get("tema", user_input)
                            res = self.memory.query_knowledge(tema, top_k=3)
                            if res:
                                for r in res:
                                    self.memory.learn_fact(
                                        r["text"], category="react",
                                        confidence=0.3, source="react_busqueda")
                        elif accion == "calcular":
                            expr = parsed.get("expresion", "")
                            if expr:
                                self.memory.remember("nexus",
                                    f"[calculo: {expr}]",
                                    context={"backend": "react"})

                        if respuesta:
                            return respuesta, metadata
                    except _json.JSONDecodeError:
                        # Fallback: usar raw si no es JSON válido
                        return raw_json, metadata
            except Exception as e:
                logger.warning(f"SLM fallo, usando simbolico: {e}")

        # --- SLM mode: todo via SLM ---
        if backend_mode == "slm" and self.slm and self.slm.loaded:
            try:
                system_prompt = self.context.build(user_input)
                slm_result = self.slm.generate(user_input, system_prompt=system_prompt)
                if slm_result:
                    metadata["backend"] = "slm"
                    metadata["model"] = slm_result.get("model")
                    metadata["tokens_prompt"] = slm_result.get("tokens_prompt", 0)
                    metadata["tokens_generated"] = slm_result.get("tokens_generated", 0)
                    metadata["duration_ms"] = slm_result.get("duration_ms", 0)
                    metadata["total_duration_ms"] = slm_result.get("total_duration_ms", 0)
                    return slm_result["response"], metadata
            except Exception as e:
                logger.warning(f"SLM fallo, usando simbolico: {e}")

        # --- Modo simbolico (default o fallback) ---
        response = self.symbolic.process(user_input, actions_registry=self.actions,
                                    skip_bookkeeping=True)
        return response, metadata

    # ─── ReAct: acciones embebidas en respuesta del SLM ─────────

    def _execute_react_actions(self, response: str, user_input: str):
        """Ejecuta acciones [[accion:...]] embebidas en la respuesta del SLM."""
        import re
        for match in re.finditer(r'\[\[accion:(\w+)\(([^)]*)\)\]\]', response):
            action_name = match.group(1)
            params_str = match.group(2)
            params = {}
            if params_str:
                for pair in params_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip().strip('"').strip("'")
            logger.info(f"ReAct: ejecutando accion {action_name}({params})")
            if action_name == "buscar_memoria":
                query = params.get("query", params_str.strip().strip('"').strip("'"))
                results = self.memory.query_knowledge(query, top_k=3)
                if results:
                    for r in results:
                        self.memory.learn_fact(
                            r["text"], category="react",
                            confidence=0.3, source="react_busqueda"
                        )
                        logger.info(f"ReAct: aprendido de busqueda: {r['text'][:60]}")
            elif action_name == "calcular":
                expr = params.get("expresion", params_str.strip().strip('"').strip("'"))
                self.memory.remember("nexus", f"[calculo: {expr}]",
                                   context={"backend": "react"})

    def _clean_react_response(self, response: str) -> str:
        """Limpia el formato ReAct para mostrar solo la respuesta al usuario."""
        import re
        # Extraer solo la parte después de "Respuesta:" o "RESPONDER:"
        for prefix in ["Respuesta:", "RESPONDER:", "RESPUESTA:", "respuesta:"]:
            if prefix in response:
                after = response.split(prefix, 1)[1].strip()
                # Quitar posibles marcadores de fin
                after = re.sub(r'\n===.*$', '', after)
                after = re.sub(r'\[\[accion:.*?\]\]', '', after)
                return after.strip()
        # Si no encuentra el formato, devolver la última línea sustancial
        lines = [l.strip() for l in response.split("\n") if l.strip()]
        meaningful = [l for l in lines if not l.startswith("Pienso") 
                     and not l.startswith("PENSAR") and not l.startswith("HACER")
                     and not l.startswith("🔧") and not l.startswith("🤔")
                     and not l.startswith("===")]
        if meaningful:
            return meaningful[-1]
        return response.strip()[:300]

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
