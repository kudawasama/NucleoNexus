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
            "hora": "get_time",
            "estado": "get_nexus_status",
            "clima": "get_weather",
        }

    def _load_patterns(self):
        """Carga patrones procedurales desde la memoria."""
        # Los patrones se cargan dinámicamente de la DB procedural
        pass

    def process(self, user_input: str, actions_registry=None) -> str:
        """Procesa una entrada de usuario y genera respuesta."""
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

        # 7. Registrar en memoria episódica
        self.memory.remember("user", user_input,
                           context={"intent": intent, "backend": "symbolic"})
        self.memory.remember("nexus", response,
                           context={"intent": intent, "backend": "symbolic"})

        # 8. Actualizar estado
        elapsed = (time.time() - start) * 1000
        self.state.record_interaction(success=True, response_time_ms=elapsed)
        self.state.evolve_phase()

        # Actualizar knowledge_stats
        mem_stats = self.memory.stats()
        self.state.set("knowledge_stats", "episodic_memories", value=mem_stats.get("episodic", 0))
        self.state.set("knowledge_stats", "semantic_facts", value=mem_stats.get("semantic", 0))
        self.state.set("knowledge_stats", "procedural_patterns", value=mem_stats.get("procedural", 0))
        self.state.set("nexus", "total_learned_facts", value=mem_stats.get("semantic", 0))

        return response

    def _respond_empty(self) -> str:
        return "...¿Hola? No te escuché. Puedes escribirme lo que sea."

    def _detect_intent(self, text: str) -> str:
        """Detecta la intención del usuario por palabras clave."""
        patterns = {
            "saludo": r'\b(hola|buenas|hey|saludos|que tal|qué tal|buen[oa]s)\b',
            "despedida": r'\b(adiós|adios|chao|bye|nos vemos|hasta luego|saludos)\b',
            "agradecimiento": r'\b(gracias|thank|thanks|graciass)\b',
            "presentacion": r'\b(quién eres|quien eres|que eres|qué eres|presentate|presentate|capacidades|que puedes hacer|qué puedes hacer|que sabes hacer)\b',
            "estado": r'\b(estado|status|cómo estás|como estas|que tal|qué tal)\b',
            "aprender": r'\b(aprend[a-z]+|enseñ[ae]|nuev[ao]|saber|conocimiento|recuerd[ae])\b',
            "fase": r'\b(fase|evolución|evolucion|nivel|progreso|level|phase)\b',
            "calcular": r'\b(cuanto es|cuánto es|calcula|calcular|suma|resta|multiplica|divide|\d+\s*[+\-*/]\s*\d+)\b',
            "ayuda": r'\b(ayud[a-z]+|help|comando|command|qué puedes|que puedes|skills)\b',
            "clima": r'\b(clima|temperatura|lluvia|pronóstico|pronostico|tiempo atmosferico|huechuraba|santiago)\b',
            "hora": r'\b(hora|que hora es|qué hora es|reloj|tiempo actual|fecha actual|get_time)\b',
            "memoria": r'\b(recuerda[s]?|memoria|olvid|acuerd[ao])\b',
            "nombre": r'\b(cómo me llamo|como me llamo|sabes mi nombre|sabes quién soy|quién soy|me llamo|mi nombre es)\b',
            "reset": r'\b(reset|reiniciar|borrar|limpiar|empezar de nuevo)\b',
            "personalidad": r'\b(personalidad|tono|voz|estilo|forma[l]?|ser)\b',
            "confianza": r'\b(confianza|seguro|certeza|cuanto sabes|qué tanto sabes)\b',
        }

        for intent, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return intent
        return "conversacion"

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

    def _handle_learn(self, text: str, memories: list, facts: list) -> str:
        # Extrae posibles hechos del texto
        # Busca patrones como: "aprende que X es Y" o "X es/son/tiene Y"
        fact_patterns = [
            r'que ([a-záéíóúñ]+ (?:es|son|tiene|puede|hace|significa) .+)',
            r'aprend[aeio] (?:que )?(.+)',
            r'enseñ[ae] (?:que )?(.+)',
            r'recuerd[ae] (?:que )?(.+)',
        ]
        hechos = []
        for pat in fact_patterns:
            hechos = re.findall(pat, text.lower())
            if hechos:
                break
        if hechos:
            for hecho in hechos[:3]:
                self.memory.learn_fact(hecho, category="aprendizaje",
                                     confidence=0.3, source="usuario")
            return f"¡He aprendido {len(hechos[:3])} cosas nuevas! 📚 Las almacenaré en mi memoria semántica."
        return (
            "Estoy listo para aprender. Puedes enseñarme hechos, patrones o conceptos. "
            "Por ejemplo: 'Nexus, aprende que Python es un lenguaje de programación'."
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
        """Maneja preguntas sobre el nombre del usuario."""
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

        # Si es una declaracion de nombre ("me llamo X", "mi nombre es X")
        name_declaration = re.search(
            r'(?:mi nombre es|me llamo|soy) ([a-záéíóúñ]+)',
            text_lower
        )
        if name_declaration:
            user_name = name_declaration.group(1)
            self.memory.learn_fact(
                f"el usuario se llama {user_name}",
                category="personal",
                confidence=0.8,
                source="usuario"
            )
            return (
                f"¡Encantado de conocerte, {user_name.capitalize()}! 🎉\n"
                f"He guardado tu nombre en mi memoria. No lo olvidare."
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
        """Respuesta general que busca activamente en memoria."""
        text_lower = text.lower()

        # --- Auto-aprendizaje: detectar datos personales ---
        # "mi nombre es X" o "me llamo X"
        name_match = re.search(
            r'(?:mi nombre es|me llamo) ([a-záéíóúñ]+)', text_lower
        )
        if name_match:
            user_name = name_match.group(1)
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

        # "soy X" (nombre)
        soy_match = re.match(r'^soy ([a-záéíóúñ]+)$', text_lower)
        if soy_match:
            user_name = soy_match.group(1)
            self.memory.learn_fact(
                f"el usuario se llama {user_name}",
                category="personal",
                confidence=0.8,
                source="usuario"
            )
            return f"¡Hola, {user_name.capitalize()}! Un gusto."

        # --- Busqueda activa en memoria ---
        # Detectar si es una pregunta
        is_question = any(q in text_lower for q in [
            "sabes", "conoces", "recuerdas", "como", "qué", "que",
            "cuando", "donde", "por que", "por qué", "cual", "cuál"
        ])

        if is_question:
            # Buscar en memoria semantica
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

            # Buscar en memoria episodica (conversacion previa)
            mem_recall = self.memory.recall(text, top_k=5)
            if mem_recall:
                # Filtrar: umbral mas alto + al menos una palabra significativa en comun
                stop_words = {'como', 'que', 'qué', 'es', 'son', 'las', 'los', 'mas',
                             'por', 'para', 'con', 'del', 'una', 'uno', 'sus', 'le'}
                query_words = set(re.findall(r'\b[a-z]{4,}\b', text_lower)) - stop_words
                relevant = []
                for m in mem_recall:
                    score = m.get("score", 0)
                    if score < 0.25:
                        continue
                    mem_words = set(re.findall(r'\b[a-z]{4,}\b',
                                     m.get("text", "").lower())) - stop_words
                    if query_words & mem_words:
                        relevant.append(m)
                if relevant:
                    best = relevant[0].get("text", "")[:120]
                    return (
                        f"Esto me recuerda algo que mencionaste antes: "
                        f"\"{best}\". "
                        f"¿Quieres que retomemos ese tema?"
                    )

        # --- Si hay hechos relevantes, usarlos ---
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
