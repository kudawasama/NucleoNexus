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
# Los logs a archivo siempre, a stream solo en modo verbose
# (para no spamear la salida del usuario en el CLI)
_VERBOSE = os.environ.get("NEXUS_VERBOSE", "0") == "1"
_LOG_LEVEL = getattr(logging, LOG_LEVEL, logging.INFO)

if not _VERBOSE:
    # Reducir logs a stream: solo WARNING+ por defecto
    _stream_level = logging.WARNING
else:
    _stream_level = _LOG_LEVEL

logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stderr) if _VERBOSE
        else logging.NullHandler(),  # silencio en stream por defecto
    ] if LOG_FILE else [
        logging.StreamHandler(sys.stderr) if _VERBOSE
        else logging.NullHandler(),
    ],
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

        # 2c. Restaurar modelo persistido (si /model use se uso antes)
        self._restore_persisted_model()

        # 3. Registro de Skills
        self.skills = SkillRegistry()
        self._load_skills()
        logger.info("OK Skills")

        # 4. Registro de Acciones (nucleo + skills)
        self.actions = ActionRegistry()
        self._register_core_actions()
        self._register_skill_actions()
        logger.info("OK Acciones")

        # 5. Backend SLM
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

    def _restore_persisted_model(self):
        """Restaura el modelo elegido via /model use en una sesion previa.

        Si el usuario hizo /model use ollama qwen2.5:1.5b en sesion
        anterior, la eleccion se guardo en state['model_state'].
        Al iniciar, leemos eso y actualizamos config.py en memoria
        ANTES de que SLMBackend se cree.
        """
        saved = self.state.get("model_state", default={})
        saved_backend = saved.get("backend", "")
        if not saved_backend or saved_backend == "symbolic":
            return  # usar config por defecto

        import config as _cfg
        cur_backend = _cfg.ENGINE["llm"].get("backend")

        if saved_backend == "opencode":
            if cur_backend != "openai":
                _cfg.ENGINE["llm"]["backend"] = "openai"
                _cfg.ENGINE["llm"]["api_base"] = "https://opencode.ai/zen/go/v1"
                _cfg.ENGINE["llm"]["api_key"] = None
            new_model = saved.get("model_name", "deepseek-v4-flash")
            if _cfg.ENGINE["llm"].get("model_name") != new_model:
                _cfg.ENGINE["llm"]["model_name"] = new_model
                logger.info(f"Modelo restaurado: opencode / {new_model}")

        elif saved_backend == "ollama":
            _cfg.ENGINE["llm"]["backend"] = "ollama"
            _cfg.ENGINE["llm"]["api_base"] = "http://localhost:11434/v1"
            _cfg.ENGINE["llm"]["api_key"] = "not-needed"
            new_model = saved.get("model_name", "qwen2.5:0.5b")
            if _cfg.ENGINE["llm"].get("model_name") != new_model:
                _cfg.ENGINE["llm"]["model_name"] = new_model
                logger.info(f"Modelo restaurado: ollama / {new_model}")

        elif saved_backend == "llamacpp":
            _cfg.ENGINE["llm"]["backend"] = "llamacpp"
            new_model = saved.get("model_name", "")
            if new_model:
                _cfg.ENGINE["llm"]["model_name"] = new_model
            logger.info(f"Modelo restaurado: llamacpp / {new_model}")

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

        # Enriquece metadata con info del sistema
        metadata["version"] = self.state.get("nexus", "version", default="?")
        metadata["skills_count"] = self.state.get("nexus", "total_skills", default=0)
        metadata["phase"] = self.state.get("nexus", "phase", default="Proto")
        metadata["interactions"] = self.state.get("nexus", "total_interactions", default=0)
        metadata["mode"] = self.state.get("capabilities", "backend", default="symbolic")

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

        # ─────────────────────────────────────────────────────────
        # TOOL INTENTS: deteccion directa (sin pasar por detect_intent
        # que tiene conflictos: "calcula" activa calcular antes que web_search)
        # ─────────────────────────────────────────────────────────
        input_lower = user_input.lower().strip()
        
        # Mapa de tool intents con su regex de deteccion
        tool_patterns = [
            ("web_search", r'(?:busca|buscar|bsuca|vusca|buca|investiga|investigar|encuentra|encontrar|consulta|consultar)\s+(?:en la web|en internet|en google|online|en linea|en línea)'),
            ("browse_url", r'(?:abre|abrir|navega|navegar|visita|visitar|browse|entra|entrar)\s+(?:a\s+|en\s+)?(?:la\s+)?(?:url|pagina|página|sitio|web|dominio)\s+(.+)'),
            ("browse_url", r'\b(?:visita|visitar|abre|abrir|navega|navegar|browse)\s+(?:https?://)?[\w.-]+\.\w{2,}\b'),
            ("read_file", r'(?:lee|leer|abre|abrir|muestra|mostrar)\s+(?:el\s+)?(?:archivo|fichero|file)'),
            ("search_files", r'(?:busca|buscar|encuentra|encontrar)\s+(?:en|dentro\s+de)\s+(?:los\s+)?(?:archivos|ficheros|codigo|código)'),
            ("run_command", r'\b(ejecuta|ejecutar|corre|correr|run|terminal|comando)\s+'),
        ]
        
        tool_intent = None
        for name, pattern in tool_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                tool_intent = name
                break
        
        if tool_intent:
            result = self._handle_tool_intent(tool_intent, user_input, metadata)
            if result:
                metadata["backend"] = "symbolic"
                metadata["tool_called"] = tool_intent
                return result, metadata

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
            # Pero preguntas de definicion ("que es X") siempre van al SLM
            import re as _qr
            if not _qr.search(r'(?:que\s+es|qué\s+es|que\s+significa|qué\s+significa|defineme|define|explicame)', user_input.lower().strip()):
                facts = self.memory.query_knowledge(user_input, top_k=2)
                if facts and any(f.get("score", 0) >= 0.15 for f in facts):
                    response = self.symbolic.process(user_input, actions_registry=self.actions,
                                                skip_bookkeeping=True)
                    metadata["backend"] = "symbolic"
                    return response, metadata

            # ── META DEL PROYECTO: mejorar Qwen 0.5B ─────────
            # docs/01-VISION: "Inteligencia por arquitectura, no por tamaño"
            # NO evadimos al SLM. En su lugar, lo rodeamos de:
            #   - Contexto rico (memoria, skills, estado)
            #   - Structured generation (JSON forzado)
            #   - Tools via intent (regex directa)
            #   - Self-consistency (multi-shot)
            #   - Memoria vectorial (embeddings)
            # Si todo falla, el SLM responde lo mejor que puede.
            # NO redirigimos a web_search automaticamente para no
            # ocultar el problema real: el modelo necesita entrenamiento.
            # Para preguntas factuales, el sistema mejora inyectando
            # contexto: en lugar de "que es Charizard?", mejor
            # "segun tu base de conocimiento, que es Charizard?".

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
                        accion = parsed.get("accion", "responder")

                        # Ejecutar acción según el tipo
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
                        elif accion == "usar_herramienta":
                            herramienta = parsed.get("herramienta", "")
                            parametros = parsed.get("parametros", {})
                            if herramienta:
                                metadata["tool_called"] = herramienta
                                # Ejecutar la herramienta via ActionRegistry
                                tool_result = self.actions.execute(herramienta, **parametros)
                                if tool_result.get("success"):
                                    result_data = tool_result.get("result", {})
                                    if isinstance(result_data, dict):
                                        # Si la herramienta ya dio formato, usarla
                                        if "respuesta" in result_data:
                                            respuesta = result_data["respuesta"]
                                        elif "resultados" in result_data:
                                            items = result_data["resultados"]
                                            respuesta = (
                                                f"Resultados de {herramienta}:\n"
                                                + "\n".join(str(i) for i in items[:5])
                                            )
                                        elif "salida" in result_data:
                                            respuesta = result_data["salida"][:500]
                                        else:
                                            respuesta = str(result_data)[:500]
                                    else:
                                        respuesta = str(result_data)[:500]
                                else:
                                    # Tool fallo: usar el mensaje de error como respuesta
                                    err = tool_result.get("error", "Error desconocido")
                                    respuesta = f"No pude ejecutar {herramienta}: {err}"

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

    # ─── Tool Intents: ejecucion directa sin SLM ─────────────

    def _handle_tool_intent(self, intent: str, user_input: str, metadata: dict = None) -> str | None:
        """Ejecuta una herramienta directamente desde el intent detectado.
        
        Extrae parámetros del texto del usuario con regex y llama
        a la acción correspondiente via ActionRegistry.
        """
        import re as _re

        if intent == "web_search":
            # Extraer query: "busca en la web [query]" — limpiar comandos extra
            m = _re.search(
                r'(?:busca|buscar|bsuca|vusca|buca|investiga|investigar|encuentra|encontrar|consulta|consultar)'
                r'\s+(?:en la web|en internet|en google|online|en linea|en línea)\s+(.+)',
                user_input, _re.IGNORECASE
            )
            if m:
                query = m.group(1).strip().rstrip('.?!,')
                # Limpiar: quitar "y [acción]" del final (ej: "y crea un informe")
                query = _re.split(r'\s+(?:y\s+(?:crea|crear|haz|hacer|genera|generar|prepara|preparar|elabora|elaborar|escribe|escribir)\s+)', query, maxsplit=1)[0]
                query = _re.split(r'\s+y\s+su\s+contenido', query, maxsplit=1)[0]
                
                # Si el query es un dominio (.com, .org, .io, .net, .dev, .app)
                # navegarlo directamente en vez de buscar
                domain_match = _re.match(
                    r'^(?:el\s+)?(?:dominio\s+|sitio\s+|web\s+)?'
                    r'([\w-]+\.\w{2,})(?:[/\s].*)?$',
                    query, _re.IGNORECASE
                )
                if domain_match:
                    domain = domain_match.group(1)
                    if not domain.startswith(('http://', 'https://')):
                        domain = 'https://' + domain
                    result = self.actions.execute("browse_website", url=domain)
                    if result.get("success"):
                        data = result["result"]
                        if isinstance(data, dict) and "error" not in data:
                            title = data.get("titulo", domain)
                            content = data.get("contenido", "")
                            lines = content.splitlines() if isinstance(content, str) else content
                            resp = f"🌐 {title}\n"
                            for line in lines[:15]:
                                resp += f"  {line[:150]}\n"
                            if len(lines) > 15:
                                resp += f"  ... ({len(lines) - 15} líneas más)"
                            metadata["tool_called"] = "browse_website"
                            return resp.strip()
                        elif "error" in data:
                            # Fallback: buscar normal si no se pudo navegar
                            pass
                
                result = self.actions.execute("web_search", query=query)
                if result.get("success"):
                    data = result["result"]
                    if isinstance(data, dict):
                        if "resultados" in data:
                            items = data["resultados"]
                            if items:
                                fuente = data.get("fuente", "web")
                                lines = [f"🔍 Resultados ({fuente}):"]
                                for i, item in enumerate(items[:5], 1):
                                    lines.append(f"  {i}. {str(item)[:150]}")
                                return "\n".join(lines)
                            elif "mensaje" in data:
                                return f"🔍 {data['mensaje']}"
                            else:
                                return "🔍 No se encontraron resultados."
                        elif "error" in data:
                            return f"No pude buscar: {data['error']}"
                return "No encontré resultados. ¿Quieres intentar con otra consulta?"
            return "No entendí qué buscar. Ej: 'busca en la web Python tutorial'"

        elif intent == "browse_url":
            # Extraer URL/dominio
            m = _re.search(
                r'(?:abre|abrir|navega|navegar|visita|visitar|browse|entra|entrar)'
                r'\s+(?:a\s+|en\s+)?(?:la\s+)?(?:url|pagina|página|sitio|web|dominio)\s+(.+)',
                user_input, _re.IGNORECASE
            )
            if not m:
                # Forma simple: "visita kudawa.com"
                m = _re.search(
                    r'\b(?:visita|visitar|abre|abrir|navega|navegar|browse)\s+((?:https?://)?[\w.-]+\.\w{2,})',
                    user_input, _re.IGNORECASE
                )
            if m:
                url_text = m.group(1).strip().rstrip('.?!,')
                url_text = _re.split(r'\s+(?:y\s+(?:crea|crear|haz|hacer|genera|generar|prepara|preparar|elabora|elaborar|escribe|escribir)\s+)', url_text, maxsplit=1)[0]
                url_text = _re.split(r'\s+y\s+su\s+contenido', url_text, maxsplit=1)[0]
                if not url_text.startswith(('http://', 'https://')):
                    url_text = 'https://' + url_text
                result = self.actions.execute("browse_website", url=url_text)
                if result.get("success"):
                    data = result["result"]
                    if isinstance(data, dict):
                        if "error" in data:
                            return f"Error: {data['error']}"
                        title = data.get("titulo", "")
                        content = data.get("contenido", data.get("texto", ""))
                        lines = content.splitlines() if isinstance(content, str) else content
                        resp = f"🌐 {title}\n"
                        for line in lines[:20]:
                            resp += f"  {line[:150]}\n"
                        if len(lines) > 20:
                            resp += f"  ... ({len(lines) - 20} líneas más)\n"
                        return resp.strip()
                return "No pude acceder a esa URL."
            return "Especifica qué sitio visitar. Ej: 'visita kudawa.com'"

        elif intent == "read_file":
            # Extraer path: "lee el archivo [path]" o "muestra [path]"
            m = _re.search(
                r'(?:lee|leer|abre|abrir|muestra|mostrar)\s+(?:el\s+)?(?:archivo|fichero|file)\s+(.+)',
                user_input, _re.IGNORECASE
            )
            if not m:
                m = _re.search(
                    r'(?:muestra|mostrar|enseña|enseñar)\s+(.+)',
                    user_input, _re.IGNORECASE
                )
            if m:
                path = m.group(1).strip().rstrip('.?!,').split()[0]
                result = self.actions.execute("read_file", path=path, max_lines=30)
                if result.get("success"):
                    data = result["result"]
                    if isinstance(data, dict):
                        if "error" in data:
                            return f"Error: {data['error']}"
                        lines = data.get("lineas", [])
                        archivo = data.get("archivo", path)
                        total = data.get("total_lineas", 0)
                        resp = f"📄 {archivo} ({total} líneas):\n"
                        resp += "\n".join(f"  {i+1}| {l}" for i, l in enumerate(lines))
                        if data.get("truncado"):
                            resp += f"\n  ... ({total - len(lines)} líneas más)"
                        return resp
                return "No pude leer ese archivo."
            return "Especifica qué archivo leer. Ej: 'lee el archivo config.py'"

        elif intent == "search_files":
            # Extraer patrón: "busca en archivos [patrón]"
            m = _re.search(
                r'(?:busca|buscar|encuentra|encontrar)'
                r'\s+(?:en|dentro\s+de)\s+(?:los\s+)?(?:archivos|ficheros|codigo|código)\s+(.+)',
                user_input, _re.IGNORECASE
            )
            if m:
                pattern = m.group(1).strip().rstrip('.?!,')
                result = self.actions.execute("search_files", pattern=pattern)
                if result.get("success"):
                    data = result["result"]
                    if isinstance(data, dict):
                        if "error" in data:
                            return f"Error: {data['error']}"
                        matches = data.get("resultados", [])
                        total = data.get("total_encontrados", 0)
                        if not matches:
                            return f"No encontré '{pattern}' en ningún archivo."
                        lines = [f"🔍 '{pattern}' encontrado {total} vez/veces:"]
                        for m in matches[:8]:
                            lines.append(f"  {m['archivo']}:{m['linea']}  {m['texto'][:80]}")
                        return "\n".join(lines)
                return "No pude buscar en archivos."
            return "Especifica qué buscar. Ej: 'busca en archivos def main'"

        elif intent == "run_command":
            # Extraer comando: "ejecuta [comando]" o "corre [comando]"
            m = _re.search(
                r'(?:ejecuta|ejecutar|corre|correr|run)\s+(.+)',
                user_input, _re.IGNORECASE
            )
            if m:
                cmd = m.group(1).strip().rstrip('.?!,')
                result = self.actions.execute("run_command", command=cmd)
                if result.get("success"):
                    data = result["result"]
                    if isinstance(data, dict):
                        if "error" in data:
                            return f"Error: {data['error']}"
                        salida = data.get("salida", "")
                        codigo = data.get("codigo_retorno", 0)
                        status = "✅" if codigo == 0 else "⚠️"
                        resp = f"  {status} Exit code: {codigo}\n"
                        if salida:
                            resp += salida[:500]
                        return resp
                return "No pude ejecutar ese comando."
            return "Especifica qué comando ejecutar. Ej: 'ejecuta ls -la'"

        return None

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
