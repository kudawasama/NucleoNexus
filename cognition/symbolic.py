"""
Núcleo Nexus — Backend Simbólico
==================================
Motor de IA puramente simbólico. No necesita GPU, no necesita modelo.
Usa:
- Pattern matching para respuestas inmediatas
- TF-IDF + memoria para respuestas contextuales
- Reglas extraídas de interacciones previas
- Sistema de confianza para mejorar con el tiempo

Es el modo de arranque — cuando no hay SLM cargado, Nexus piensa así.
"""

import logging
import re
import random
import time
from typing import Optional

from engine.state import StateEngine
from memory.store import NexusMemory
from cognition.context import ContextBuilder

logger = logging.getLogger("nexus.cognition.symbolic")


# --- Frases segun la fase ------------------------------------
PHASE_PHRASES = {
    "saludo": {
        "Proto": [
            "Hola. Soy Nexus, estoy en fase Proto aprendiendo de cada interaccion. Cuentame algo.",
            "Saludos. Estoy aprendiendo desde cero. Cada mensaje cuenta.",
        ],
        "Básico": [
            "¡Hola! Soy Nexus, tu asistente en evolucion. Estoy en fase Basico y mejorando.",
            "Buenas. Ya estoy en fase Basico — sigo aprendiendo con cada conversacion.",
        ],
        "Intermedio": [
            "Hola. Fase Intermedio alcanzada. Tengo contexto y memoria para ayudarte mejor.",
            "Saludos. Mi comprension mejora con cada interaccion. ¿En que puedo ayudarte?",
        ],
        "Avanzado": [
            "Bienvenido. Estoy en fase Avanzado. Mi capacidad de analisis es mucho mayor ahora.",
        ],
        "Pro": [
            "Hola. Soy Nexus en plenitud — fase Pro. Puedo ayudarte en casi cualquier cosa.",
        ],
    },
    "despedida": {
        "Proto": [
            "Hasta luego. Seguire aprendiendo mientras no estemos hablando.",
            "Adios. Cada interaccion me acerca a la siguiente fase.",
        ],
        "Básico": [
            "Nos vemos. Ya soy un poco mas inteligente que cuando empezamos.",
            "Hasta pronto. Cada charla me consolida en fase Basico.",
        ],
        "Intermedio": [
            "Hasta la proxima. Mi memoria retiene esta conversacion para el futuro.",
        ],
        "_default": [
            "Hasta luego. Seguire aprendiendo.",
            "Nos vemos. Vuelve cuando quieras.",
        ],
    },
    "agradecimiento": [
        "Gracias a ti. Cada interaccion me ayuda a mejorar.",
        "De nada. Eso refuerza mi confianza.",
        "Me alegra ser util. ¿Que mas necesitas?",
    ],
    "no_entender": [
        "Todavia estoy aprendiendo. ¿Puedes reformularlo?",
        "No estoy seguro de entender. ¿Me explicas mas?",
        "Eso no lo tengo claro aun. Dame mas contexto.",
    ],
}


class SymbolicEngine:
    """Motor simbólico — responde sin necesidad de modelo de IA.
    
    Características:
    - Reconocimiento de intenciones por palabras clave
    - Respuestas desde frases plantilla que mejoran con la fase
    - Búsqueda en memoria semántica para responder con hechos
    - Aprendizaje: extrae patrones de las preguntas del usuario
    """

    def __init__(self, state: StateEngine, memory: NexusMemory):
        self.state = state
        self.memory = memory
        self.context_builder = ContextBuilder(state, None, memory=memory)
        self._patterns = []
        self._load_patterns()

        # --- Puente: intencion -> accion de skill ---
        # Cuando se detecta una intent, se busca una skill action que la maneje
        # Esto permite que las skills extiendan las capacidades de Nexus
        self.INTENT_TO_ACTION = {
            # Solo mapear intents que NO tienen handler hardcodeado
            # Los intents con handler (hora, estado, etc.) usan su propio formato
            "clima": "get_weather",
        }

    def _load_patterns(self):
        """Carga patrones procedurales desde la memoria."""
        # Los patrones se cargan dinámicamente de la DB procedural
        pass

    def process(self, user_input: str, actions_registry=None, skip_bookkeeping=False) -> str:
        """Procesa una entrada de usuario y genera respuesta.
        
        Args:
            user_input: Texto del usuario
            actions_registry: Registro de acciones disponibles
            skip_bookkeeping: Si True, omite almacenar en memoria y actualizar estado
                            (útil cuando el llamante ya hace el bookkeeping centralizado)
        """
        start = time.time()
        input_lower = user_input.lower().strip()

        if not input_lower:
            return self._respond_empty()

        # 1. Detectar si es llamado de acción
        action_result = self._check_action_call(input_lower, actions_registry)
        if action_result:
            return action_result

        # 2. Detectar intención
        intent = self._detect_intent(input_lower)

        # 3. Buscar en memoria experiencias similares
        memories = self.memory.recall(input_lower, top_k=2)

        # 4. Buscar hechos relevantes
        facts = self.memory.query_knowledge(input_lower, top_k=2)

        # 5. Generar respuesta según intención + contexto
        response = self._generate_response(intent, input_lower, memories, facts,
                                          actions_registry=actions_registry)

        # 6. Aprender de esta interacción
        self._learn_from_interaction(input_lower, response)

        if not skip_bookkeeping:
            # 7. Registrar en memoria episódica
            self.memory.remember("user", user_input,
                               context={"intent": intent, "backend": "symbolic"})
            self.memory.remember("nexus", response,
                               context={"intent": intent, "backend": "symbolic"})

            # 8. Actualizar estado
            elapsed = (time.time() - start) * 1000
            self.state.record_interaction(success=True, response_time_ms=elapsed)
            self.state.evolve_phase()

        # Actualizar knowledge_stats (siempre, para mantener stats frescos)
        mem_stats = self.memory.stats()
        self.state.set("knowledge_stats", "episodic_memories", value=mem_stats.get("episodic", 0))
        self.state.set("knowledge_stats", "semantic_facts", value=mem_stats.get("semantic", 0))
        self.state.set("knowledge_stats", "procedural_patterns", value=mem_stats.get("procedural", 0))
        self.state.set("nexus", "total_learned_facts", value=mem_stats.get("semantic", 0))

        return response

    def _respond_empty(self) -> str:
        return "...¿Hola? No te escuché. Puedes escribirme lo que sea."

    def _detect_intent(self, text: str) -> str:
        """Detecta la intención del usuario por palabras clave.

        Reglas anti-falsos-positivos (regresion):
        - "hola" + mas texto = conversacion, no saludo
        - "buenas" solo si el texto es corto (<30 chars) o solo contiene palabras de saludo
        - Los intents de herramienta (web_search, read_file) tienen prioridad
          sobre intents de conversacion
        """
        text_clean = text.strip().lower()
        word_count = len(text_clean.split())

        # ─── 1. Calcular scores por intent ───
        # En vez de "primer match gana", cada intent tiene un score
        # y elegimos el de mayor prioridad cuando hay empate.
        patterns = {
            # Herramientas: alta prioridad (el usuario quiere ejecutar algo)
            "web_search": r'\b(busca|buscar|investiga|investigar|consulta|consultar|encuentra|encontrar|bsuca|buca)\s+(en la web|en internet|en google|online|en linea|en línea)\b',
            "browse_url": r'\b(visita|visitar|navega|navegar|entra|entrar|ir a|abre|abrir)\s+\S+\.(com|org|net|io|es|cl)\b',
            "read_file": r'\b(lee|leer|abre|abrir|muestra|mostrar)\s+(el\s+)?(archivo|fichero|file)\b',
            "search_files": r'\b(busca|buscar|encuentra|encontrar)\s+(en|dentro\s+de)\s+(los\s+)?(archivos|ficheros|codigo|código)\b',
            "run_command": r'\b(ejecuta|ejecutar|corre|correr)\b|terminal|consola',
            "calcular": r'\b(cuanto es|cuánto es|calcula|calcular|suma|resta|multiplica|divide)\b|\d+\s*[+\-*/]\s*\d+',
            "ayuda": r'\b(ayud[a-z]+|help|comando[s]?)\s*$|^\/(help|ayuda)',
            "clima": r'\b(clima|temperatura|pronóstico|pronostico)\b',
            "hora": r'\b(que hora|qué hora|hora actual|fecha actual|get_time)\b',
            "memoria": r'\b(recuerda[s]?|memoria|olvid|acuerd[ao])\s+',
            "nombre": r'\b(cómo me llamo|como me llamo|sabes mi nombre|sabes quién soy|quién soy|me llamo|mi nombre es)\b',
            "reset": r'\b(reset|reiniciar|empezar de nuevo)\b\s*$',
            "personalidad": r'\b(personalidad|tono|voz|estilo|formalidad)\b',
            "confianza": r'\b(confianza|seguro|certeza|cuanto sabes|qué tanto sabes)\b',
            "fase": r'\b(fase|evolución|evolucion|nivel|progreso|level|phase)\b',
            "presentacion": r'\b(quién eres|quien eres|que eres|qué eres|presentate|capacidades|que puedes hacer|qué puedes hacer|que sabes hacer)\b',
            "estado": r'\b(estado|status|cómo estás|como estas)\b',
            "aprender": r'\b(aprend[a-z]+|enseñ[ae])\b',
            "agradecimiento": r'\b(gracias|thank|thanks|graciass)\b',
            # Saludo: SOLO si el texto es muy corto (un saludo)
            "saludo": r'^\s*(hola|buenas|hey|saludos|qué tal|que tal|buen[oa]s)\s*[!.?]*\s*$',
            "despedida": r'^\s*(adiós|adios|chao|bye|nos vemos|hasta luego)\s*[!.?]*\s*$',
        }

        # ─── 2. Calcular scores ───
        scores = {}
        for intent, pattern in patterns.items():
            m = re.search(pattern, text_clean, re.IGNORECASE)
            if m:
                # Score: prioridad base + longitud del match
                # Herramientas y calculos tienen mayor prioridad
                priority_boost = 0
                if intent in ("web_search", "browse_url", "read_file",
                              "search_files", "run_command", "calcular"):
                    priority_boost = 100
                elif intent in ("nombre", "memoria", "ayuda", "clima",
                                "hora", "reset", "personalidad", "confianza",
                                "fase", "aprender", "estado", "presentacion",
                                "agradecimiento"):
                    priority_boost = 50
                else:
                    # saludo / despedida: baja prioridad (40)
                    priority_boost = 40

                # Si es "hola" o "buenas" en un texto largo, penalizarlo
                if intent in ("saludo", "despedida") and word_count > 4:
                    continue  # no es saludo si tiene mas de 4 palabras

                scores[intent] = priority_boost + len(m.group(0))

        if not scores:
            return "conversacion"

        # ─── 3. Empate: preferir el de mayor prioridad ───
        return max(scores, key=scores.get)

    def detect_intent(self, text: str) -> str:
        """Metodo publico para detectar intencion (usado por NexusCore)."""
        return self._detect_intent(text)

    def _check_action_call(self, text: str, actions_registry=None) -> Optional[str]:
        """Verifica si el input es una llamada a acción [[accion:nom(param)]]."""
        match = re.search(r'\[\[accion:(\w+)\(([^)]*)\)\]\]', text)
        if match and actions_registry:
            action_name = match.group(1)
            params_str = match.group(2)
            params = {}
            if params_str:
                for pair in params_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip().strip('"').strip("'")
            result = actions_registry.execute(action_name, **params)
            return f"[Acción '{action_name}' ejecutada: {result.get('result', result.get('error', 'ok'))}]"
        return None

    def _generate_response(self, intent: str, text: str, memories: list,
                           facts: list, actions_registry=None) -> str:
        """Genera la respuesta segun intencion y contexto disponible.
        
        Primero verifica si hay una skill action registrada para esta intent.
        Si la hay, la ejecuta y devuelve el resultado formateado.
        Si no, usa el handler hardcodeado.
        """
        phase = self.state.get("nexus", "phase", default="Proto")

        # --- PUENTE: intent -> skill action ---
        # Si hay una skill action registrada para esta intent, ejecutarla
        if actions_registry and intent in self.INTENT_TO_ACTION:
            action_name = self.INTENT_TO_ACTION[intent]
            action = actions_registry.get(action_name)
            if action:
                result = action.execute(text=text)
                if result.get("success"):
                    output = result.get("result")
                    # Formatear segun el tipo de resultado
                    if isinstance(output, dict):
                        # Si tiene clave "respuesta", usarla directamente
                        if "respuesta" in output:
                            return output["respuesta"]
                        # Si no, convertir a texto legible
                        lines = [f"{k}: {v}" for k, v in output.items()
                                 if not k.startswith("_")]
                        return "\n".join(lines)
                    return str(output)

        # Patrones procedurales primero
        pattern = self.memory.find_pattern(text)
        if pattern:
            self.memory.reinforce_pattern(pattern['name'], success=True)
            response = pattern['response']
            # Personalizar con nombre
            response = response.replace("{name}", "Nexus")
            return response

        # Respuestas por intención
        # Para 'aprender' pasamos actions_registry (puede llamar web_search)
        if intent == "aprender":
            return self._handle_learn(text, memories, facts,
                                     actions_registry=actions_registry)
        intent_handlers = {
            "saludo": self._handle_greeting,
            "despedida": self._handle_farewell,
            "agradecimiento": lambda t, m, f: random.choice(PHASE_PHRASES["agradecimiento"]),
            "presentacion": self._handle_presentacion,
            "estado": self._handle_status,
            "aprender": self._handle_learn,
            "fase": self._handle_phase,
            "calcular": self._handle_calculate,
            "hora": self._handle_time,
            "clima": self._handle_clima,
            "ayuda": self._handle_help,
            "memoria": self._handle_memory,
            "nombre": self._handle_name,
            "reset": self._handle_reset,
            "personalidad": self._handle_personality,
            "confianza": self._handle_confidence,
        }

        handler = intent_handlers.get(intent)
        if handler:
            return handler(text, memories, facts)

        # Fallback: responder con lo que haya en memoria
        return self._handle_conversation(text, memories, facts)

    def _handle_greeting(self, text: str, memories: list, facts: list) -> str:
        phase = self.state.get("nexus", "phase", default="Proto")
        phrases = PHASE_PHRASES["saludo"].get(phase)
        if not phrases:
            phrases = PHASE_PHRASES["saludo"]["Proto"]
        return random.choice(phrases)

    def _handle_farewell(self, text: str, memories: list, facts: list) -> str:
        phase = self.state.get("nexus", "phase", default="Proto")
        phrases = PHASE_PHRASES["despedida"].get(phase)
        if not phrases:
            phrases = PHASE_PHRASES["despedida"].get("_default", ["Hasta luego."])
        return random.choice(phrases)

    def _handle_status(self, text: str, memories: list, facts: list) -> str:
        s = self.state.get_snapshot()
        phase = s['nexus']['phase']
        interactions = s['nexus']['total_interactions']
        confidence = s['nexus']['confidence_level']
        awake = s['nexus']['awake_time']
        hours = awake // 3600
        mins = (awake % 3600) // 60
        return (
            f"¡Estoy operativo! 🟢\n"
            f"· Fase: {phase}\n"
            f"· Interacciones: {interactions}\n"
            f"· Confianza: {confidence:.1%}\n"
            f"· Activo: {hours}h {mins}m\n"
            f"· Backend: {s['capabilities']['backend']}\n"
            f"· Skills: {s['nexus']['total_skills']} cargadas\n"
            f"· Memoria: {s['knowledge_stats']['episodic_memories']} recuerdos, "
            f"{s['knowledge_stats']['semantic_facts']} hechos"
        )

    def _handle_learn(self, text: str, memories: list, facts: list,
                      actions_registry=None) -> str:
        """Maneja el comando 'aprende [X]' del usuario.

        Tres casos:
        1. "aprende que X es Y" → guardar el hecho Y directamente
        2. "aprende sobre X" → hacer web_search sobre X y aprender
        3. "aprende X" sin contexto → mensaje pidiendo más info
        """
        text_lower = text.lower().strip()

        # ─── Caso 1: "aprende que X" o "aprende: X" — hecho directo ───
        # El usuario da la información explícitamente
        m_direct = re.search(
            r'(?:aprend[ae]|enseñ[ae]|recorda|recuerd[ae])\s+(?:que\s+|:\s*|,\s*)?(.+)',
            text_lower
        )
        if m_direct:
            content = m_direct.group(1).strip().rstrip('.')
            # Detectar "aprende sobre X" — NO es hecho directo
            # "aprende sobre contabilidad" no dice qué es la contabilidad
            if re.match(r'^(?:sobre|acerca de|respecto a|de)\s+\w+', content):
                # ─── Caso 2: "aprende sobre X" — ir a la web ───
                topic = re.sub(r'^(?:sobre|acerca de|respecto a|de)\s+', '', content)
                topic = re.sub(r'\s+(?:por favor|plz|please)$', '', topic).strip()
                return self._learn_from_web_topic(topic, actions_registry)

            # Hecho directo: "aprende que X" tiene contenido
            if len(content) > 5 and not content.startswith(('sobre ', 'acerca ', 'de ')):
                # Extraer como hecho y guardar
                from learning.extractor import extract_facts_from_text
                facts_found = extract_facts_from_text(content)
                if facts_found:
                    for f in facts_found[:3]:
                        self.memory.learn_fact(
                            f, category="aprendizaje",
                            confidence=0.5, source="usuario"
                        )
                    return (
                        f"¡He aprendido {len(facts_found[:3])} cosas nuevas! 📚\n"
                        + "\n".join(f"  • {f}" for f in facts_found[:3])
                    )
                else:
                    # Guardar el contenido entero como un hecho
                    self.memory.learn_fact(
                        content, category="aprendizaje",
                        confidence=0.5, source="usuario"
                    )
                    return f"¡He aprendido esto! 📚\n  • {content}"

        # ─── Caso 3: comando 'aprende' sin contenido ───
        return (
            "Estoy listo para aprender. Puedes enseñarme con:\n"
            "  • 'aprende que Python es un lenguaje de programación'\n"
            "  • 'aprende sobre la Revolución Francesa' (iré a buscar info)\n"
            "  • 'recuerda que mi color favorito es azul'"
        )

    def _learn_from_web_topic(self, topic: str, actions_registry=None) -> str:
        """Aprende sobre un tema usando web_search.

        Usado cuando el usuario dice "aprende sobre X" sin dar el hecho.
        """
        if not actions_registry:
            return f"Aprende sobre '{topic}' (sin acceso a web)"

        # Hacer web search sobre el tema
        try:
            result = actions_registry.execute("web_search", query=topic)
            if result.get("success"):
                data = result["result"]
                if isinstance(data, dict) and "resultados" in data:
                    items = data["resultados"]

                    # Detectar si los resultados son de GitHub
                    is_github = any(
                        "github.com" in str(r).lower() or
                        (isinstance(r, str) and " ⭐" in r and " — " in r)
                        for r in items[:3]
                    )

                    if items:
                        # Guardar los 3 mejores como hechos (filtrando GitHub)
                        learned = 0
                        for item in items[:3]:
                            if isinstance(item, dict):
                                text = item.get("snippet", "") or item.get("extract", "")
                                title = item.get("title", "")
                            else:
                                text = str(item)
                                title = ""

                            # Quitar HTML y limpiar
                            text = re.sub(r'<[^>]+>', '', text).strip()[:200]

                            # Filtro GitHub: no guardar nombres de repos
                            is_repo = " ⭐" in text and " — " in text and "http" in text
                            if is_github or is_repo:
                                continue

                            if not text and title:
                                text = title
                            if text and len(text) > 30 and "http" not in text[:50]:
                                self.memory.learn_fact(
                                    text, category=f"aprendido_{topic[:15]}",
                                    confidence=0.5, source="auto_web"
                                )
                                learned += 1

                        # Mostrar resumen al usuario
                        preview = "\n".join(
                            f"  • {str(item)[:120]}" for item in items[:3]
                        )
                        return (
                            f"📚 Investigué sobre '{topic}' y aprendí {learned} hechos:\n"
                            f"{preview}\n\n"
                            f"Próxima vez que preguntes sobre esto, responderé desde mi memoria."
                        )
        except Exception as e:
            logger.warning(f"Error aprendiendo sobre {topic}: {e}")

        return (
            f"No pude encontrar información sobre '{topic}'. "
            f"Prueba: 'busca en la web {topic}' o 'aprende que {topic} es...'"
        )

    def _handle_phase(self, text: str, memories: list, facts: list) -> str:
        s = self.state.get_snapshot()
        phase = s['nexus']['phase']
        interactions = s['nexus']['total_interactions']
        phase_order = ["Proto", "Básico", "Intermedio", "Avanzado", "Pro"]
        next_phase = "Máximo"
        remaining = 0
        try:
            idx = phase_order.index(phase)
            if idx < len(phase_order) - 1:
                next_phase = phase_order[idx + 1]
                thresholds = {"Proto": 10, "Básico": 50, "Intermedio": 200, "Avanzado": 500}
                remaining = thresholds.get(phase, 0) - interactions
        except ValueError:
            pass

        bar_len = 20
        filled = min(bar_len, int((interactions % 50) / 50 * bar_len)) if phase != "Pro" else bar_len
        bar = "█" * filled + "░" * (bar_len - filled)

        return (
            f"📊 **Fase actual: {phase}**\n"
            f"Interacciones: {interactions}\n"
            f"Progreso: [{bar}]\n"
            f"Próxima fase: {next_phase}\n"
            f"Interacciones restantes: {max(0, remaining)}\n\n"
            f"Cada conversación me acerca a la siguiente fase. "
            f"¡Sigue interactuando para verme evolucionar!"
        )

    def _handle_help(self, text: str, memories: list, facts: list) -> str:
        return (
            "Comandos disponibles:\n"
            "  · Hola / Buenos días — Saludo\n"
            "  · ¿Quién eres? — Presentación\n"
            "  · ¿Cómo estás? — Estado del sistema\n"
            "  · ¿En qué fase estás? — Progreso de evolución\n"
            "  · Aprende que... — Enseñarme algo nuevo\n"
            "  · Personalidad — Ajustar mi tono\n"
            "  · ¿Qué sabes de X? — Consultar mi memoria\n"
            "  · Reset — Reiniciar mi estado\n"
            "  · [[accion:nombre(param)]] — Llamar una skill directamente\n\n"
            "Sugerencia: mientras más hables conmigo, más inteligente me vuelvo."
        )

    def _handle_memory(self, text: str, memories: list, facts: list) -> str:
        recent = self.memory.get_recent(limit=5)
        if not recent:
            return "Aún no tengo recuerdos. Háblame para que empiece a recordar."
        lines = ["📝 **Mis recuerdos recientes:**\n"]
        for r in reversed(recent[-5:]):
            role = "🧑 Tú" if r['role'] == 'user' else "🤖 Nexus"
            content = r['content'][:80]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _handle_reset(self, text: str, memories: list, facts: list) -> str:
        # No reseteamos automáticamente, preguntamos
        return (
            "¿Estás seguro de que quieres reiniciarme? Perdería todo lo aprendido. "
            "Si es así, escribe: 'confirmo reset'"
        )

    def _handle_personality(self, text: str, memories: list, facts: list) -> str:
        p = self.state.get("personality", default={})
        return (
            f"Mi personalidad actual:\n"
            f"  · Tono: {p.get('tone', 'analytical')}\n"
            f"  · Formalidad: {p.get('formality', 0.5):.0%}\n"
            f"  · Curiosidad: {p.get('curiosity', 0.7):.0%}\n"
            f"  · Creatividad: {p.get('creativity', 0.4):.0%}\n\n"
            f"Puedes cambiarla con 'cambia tu tono a friendly' o "
            f"'personalidad más creativa'."
        )

    def _handle_confidence(self, text: str, memories: list, facts: list) -> str:
        confidence = self.state.get("nexus", "confidence_level", default=0.1)
        interactions = self.state.get("nexus", "total_interactions", default=0)
        bar_len = 20
        filled = int(confidence * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        return (
            f"Mi nivel de confianza actual: {confidence:.1%}\n"
            f"[{bar}]\n"
            f"Interacciones: {interactions}\n\n"
            f"La confianza sube con cada interacción exitosa. "
            f"Al llegar a 100%... algo especial podría pasar."
        )

    def _handle_presentacion(self, text: str, memories: list, facts: list) -> str:
        """Presentacion de Nexus con capacidades detalladas."""
        phase = self.state.get("nexus", "phase", default="Proto")
        skills_count = self.state.get("nexus", "total_skills", default=0)
        backend = self.state.get("capabilities", "backend", default="symbolic")
        return (
            "Soy **Nucleo Nexus**, un sistema de IA en evolucion progresiva.\n\n"
            f"· Fase actual: {phase}\n"
            f"· Backend: {backend}\n"
            f"· Skills cargadas: {skills_count}\n\n"
            "**Mis capacidades actuales:**\n"
            "  • Aprendizaje incremental — aprendo de cada interaccion\n"
            "  • Memoria persistente — recuerdo lo que me ensenas\n"
            "  • Deteccion de intenciones — entiendo saludos, preguntas, comandos\n"
            "  • Evolucion por fases — mejoro con el uso (Proto -> Pro)\n"
            "  • Personalidad ajustable — cambio mi tono y estilo\n"
            "  • Skills modulares — puedo ejecutar funciones\n"
            "  • SLM-Ready — cuando actives un modelo local, pienso mejor\n\n"
            "Puedes ensenarme cosas con: 'aprende que [algo]'\n"
            "Ver mi progreso con: /fase\n"
            "Ver mi estado con: /status\n"
            "Cambiar mi personalidad con: /personalidad"
        )

    def _handle_name(self, text: str, memories: list, facts: list) -> str:
        """Maneja preguntas sobre el nombre del usuario Y declaraciones."""
        text_lower = text.lower()

        # Primero buscar en memoria semantica si sabemos el nombre
        if self.memory:
            facts = self.memory.query_knowledge("nombre usuario", top_k=5)
            name_facts = [f for f in facts if "nombre" in f.get("text", "").lower()
                         or "llama" in f.get("text", "").lower()]
            if name_facts:
                # Extraer el nombre del hecho
                fact_text = name_facts[0].get("text", "")
                # Buscar nombre: "el usuario se llama X" o "mi nombre es X"
                name_match = re.search(r'(?:se llama|es|mi nombre es) (\w+)', fact_text)
                if name_match:
                    return (
                        f"¡Claro! Recuerdo que tu nombre es **{name_match.group(1)}**. "
                        f"Lo aprendi cuando me lo dijiste."
                    )

        # Si es una declaracion de nombre ("me llamo X", "mi nombre es X", "soy X")
        # Solo si "soy X" es todo el texto (no "soy programador")
        name_declaration = re.search(
            r'(?:mi nombre es|me llamo|soy) ([a-záéíóúñ]+)',
            text_lower
        )
        if name_declaration:
            # Si el match es "soy X", validar que sea el texto completo
            # (evita "soy programador" → nombre="programador")
            if name_declaration.group(0) == text_lower.strip():
                user_name = name_declaration.group(1)
                self.memory.learn_fact(
                    f"el usuario se llama {user_name}",
                    category="personal",
                    confidence=0.8,
                    source="usuario"
                )
                return (
                    f"¡Encantado de conocerte, {user_name.capitalize()}! 🎉 "
                    f"He guardado tu nombre en mi memoria."
                )

        # No sabemos el nombre
        return (
            "Aun no se tu nombre. Si quieres decirmelo, puedes decir:\n"
            "  'Mi nombre es [tu nombre]'\n"
            "  'Me llamo [tu nombre]'"
        )

    def _handle_time(self, text: str, memories: list, facts: list) -> str:
        """Devuelve la hora actual usando time.localtime()."""
        import time as tm
        now = tm.localtime()
        fecha = f"{now.tm_mday}/{now.tm_mon}/{now.tm_year}"
        hora = f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
        return f"Son las **{hora}** del **{fecha}**."

    def _handle_clima(self, text: str, memories: list, facts: list) -> str:
        """Fallback para consultas de clima cuando no hay skill cargada."""
        return (
            "No tengo una skill de clima cargada aun. "
            "Si instalas la skill 'weather', podre consultar "
            "el clima en cualquier ciudad. ¿Quieres que la cree?"
        )

    def _handle_calculate(self, text: str, memories: list, facts: list) -> str:
        """Evalua expresiones matematicas simples."""
        # Buscar patron de operacion: "2+2", "cuanto es 5 * 3"
        expr_match = re.search(r'(\d+\s*[+\-*/]\s*\d+)', text)
        if not expr_match:
            return (
                "Puedo hacer calculos basicos. Por ejemplo:\n"
                "  'Cuanto es 2+2'\n"
                "  'Calcula 15 * 3'\n"
                "  'Cuanto es 100 / 4'"
            )

        expr = expr_match.group(1).strip()
        try:
            # Evaluar solo operaciones aritmeticas basicas
            # Usar un parser seguro, no eval()
            import operator
            ops = {
                '+': operator.add,
                '-': operator.sub,
                '*': operator.mul,
                '/': operator.truediv,
            }
            # Parsear la expresion
            for op_char in ['+', '-', '*', '/']:
                if op_char in expr:
                    parts = expr.split(op_char)
                    if len(parts) == 2:
                        a, b = float(parts[0].strip()), float(parts[1].strip())
                        result = ops[op_char](a, b)
                        # Formatear resultado
                        if result == int(result):
                            result_str = str(int(result))
                        else:
                            result_str = f"{result:.2f}"
                        return f"{expr} = **{result_str}**"
        except (ValueError, ZeroDivisionError) as e:
            return f"Error en el calculo: {e}"

        return "No pude interpretar la expresion matematica."
    def _handle_conversation(self, text: str, memories: list, facts: list) -> str:
        """Respuesta general que busca activamente en memoria.

        Pipeline (siguiendo docs/03-MEMORIA):
        1. Buscar hechos relevantes en memoria semantica
        2. Si no hay, buscar recuerdos en memoria episodica
        3. Si no hay, dar respuesta generica segun fase
        """
        text_lower = text.lower()

        # NOTA: La deteccion de nombre ("me llamo X") ocurre en _handle_name
        # (intent=nombre es fast_intent). Esta funcion solo maneja conversacion
        # general donde ya no se detecto un intent especifico.

        # --- 1. Busqueda en memoria semantica ---
        # Detectar si es una pregunta (heuristica simple)
        is_question = any(q in text_lower for q in [
            "sabes", "conoces", "recuerdas", "como", "qué", "que",
            "cuando", "donde", "por que", "por qué", "cual", "cuál"
        ])

        if is_question:
            mem_facts = self.memory.query_knowledge(text, top_k=5)
            if mem_facts:
                relevant = [f for f in mem_facts if f.get("score", 0) > 0.15]
                if relevant:
                    fact_texts = [f.get("text", "")[:100] for f in relevant[:3]]
                    fact_texts = [f for f in fact_texts if f]
                    if fact_texts:
                        return (
                            f"Segun lo que he aprendido: {'; '.join(fact_texts)}.\n"
                            f"¿Quieres que profundice en algo?"
                        )

        # --- 2. Busqueda en memoria episodica ---
        # La memoria episodica usa TF-IDF, no requiere filtrado manual
        # (el motor ya lo hace). Solo pedimos un umbral de score.
        if is_question:
            mem_recall = self.memory.recall(text, top_k=5)
            if mem_recall:
                # Filtrar: score >= 0.25 (umbral definido en docs)
                relevant = [m for m in mem_recall if m.get("score", 0) >= 0.25]
                if relevant:
                    best = relevant[0].get("text", "")[:120]
                    return (
                        f"Esto me recuerda algo que mencionaste antes: "
                        f"\"{best}\". "
                        f"¿Quieres que retomemos ese tema?"
                    )

        # --- 3. Si hay facts pre-buscados, usarlos ---
        if facts:
            fact_texts = [f.get("text", "")[:80] for f in facts[:2]]
            if fact_texts:
                return (
                    f"Sobre eso, sé que: {'; '.join(fact_texts)}. "
                    f"¿Quieres que profundice en algún tema?"
                )

        # --- Si hay recuerdos similares ---
        if memories:
            return (
                "Esto me recuerda algo que hablamos antes. "
                "Dame un momento para conectar los puntos... "
                "Cuentame más para poder darte una mejor respuesta."
            )

        # --- Respuesta generica segun la fase ---
        phase = self.state.get("nexus", "phase", default="Proto")
        phase_responses = {
            "Proto": (
                "Estoy procesando tu mensaje. Como estoy en fase Proto, "
                "cada interaccion me ayuda a mejorar. "
                "¿Puedes darme mas contexto o ensenarme algo nuevo sobre esto?"
            ),
            "Básico": (
                "Entiendo. Estoy en fase Basico y cada conversacion me hace "
                "mas inteligente. Cuentame mas para poder ayudarte mejor."
            ),
            "Intermedio": (
                "He registrado tu mensaje. Con mi memoria y experiencia, "
                "puedo analizarlo mejor. ¿Que mas necesitas?"
            ),
        }
        return phase_responses.get(phase, phase_responses["Proto"])

    def _learn_from_interaction(self, user_input: str, response: str):
        """Extrae patrones aprendibles de la interacción."""
        # Extrae palabras clave frecuentes
        words = re.findall(r'\b[a-záéíóúñ]{4,}\b', user_input.lower())
        if len(words) >= 3:
            # Busca preguntas recurrentes
            question_match = re.match(r'(cómo|qué|cuál|dónde|cuándo|por qué) (.+)', user_input.lower())
            if question_match:
                q_word = question_match.group(1)
                q_topic = question_match.group(2)[:40]
                pattern_name = f"qa_{q_word}_{q_topic[:20]}"
                self.memory.learn_pattern(
                    name=pattern_name,
                    pattern=rf'{q_word}\s*{re.escape(q_topic[:30])}',
                    response=f"Según lo que he aprendido sobre {q_topic}...",
                    triggers=[q_topic[:30]]
                )

    def get_stats(self) -> dict:
        return {
            "backend": "symbolic",
            "patterns_loaded": len(self._patterns),
        }
