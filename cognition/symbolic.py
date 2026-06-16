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


# ─── Frases predeterminadas para fase Proto ──────────────────
PROTO_PHRASES = {
    "saludo": [
        "¡Hola! Soy Nexus, tu asistente IA en evolución. ¿En qué puedo ayudarte?",
        "Saludos. Estoy en fase Proto, aprendiendo de cada interacción. Cuéntame.",
        "Hola. Cada conversación me hace más inteligente. ¿Por dónde empezamos?",
    ],
    "despedida": [
        "Hasta luego. Seguiré aprendiendo mientras no estemos hablando.",
        "Nos vemos. Cada interacción me acerca a la siguiente fase.",
        "Adiós. Recuerda que puedes enseñarme cosas nuevas.",
    ],
    "agradecimiento": [
        "¡Gracias! Eso me ayuda a mejorar mi precisión.",
        "De nada. Cada interacción cuenta en mi evolución.",
        "Me alegra ser útil. ¿Qué más necesitas?",
    ],
    "no_entender": [
        "Todavía estoy aprendiendo. ¿Puedes reformularlo?",
        "No estoy seguro de entender. Estoy en fase Proto y cada duda es una oportunidad de aprender.",
        "Eso no lo tengo claro aún. ¿Me explicas más para poder aprenderlo?",
    ],
    "presentacion": [
        "Soy Núcleo Nexus, un sistema de IA en evolución progresiva. "
        "Actualmente en fase Proto. Mi arquitectura separa el motor de estado "
        "de la capa cognitiva, permitiendo escalar desde modo simbólico hasta SLM local.",
        "Nexus es un asistente inteligente diseñado para aprender incrementalmente. "
        "Fase actual: Proto. Siguiente meta: Fase Básico (50 interacciones).",
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
        response = self._generate_response(intent, input_lower, memories, facts)

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

        return response

    def _respond_empty(self) -> str:
        return "...¿Hola? No te escuché. Puedes escribirme lo que sea."

    def _detect_intent(self, text: str) -> str:
        """Detecta la intención del usuario por palabras clave."""
        patterns = {
            "saludo": r'\b(hola|buenas|hey|saludos|que tal|qué tal|buen[oa]s)\b',
            "despedida": r'\b(adiós|adios|chao|bye|nos vemos|hasta luego|saludos)\b',
            "agradecimiento": r'\b(gracias|thank|thanks|graciass)\b',
            "presentacion": r'\b(quién eres|quien eres|que eres|qué eres|presentate|presentate)\b',
            "estado": r'\b(estado|status|cómo estás|como estas|que tal|qué tal)\b',
            "aprender": r'\b(aprend[aeio]|enseñ[ae]|nuev[ao]|saber|conocimiento|recuerd[ae])\b',
            "fase": r'\b(fase|evolución|evolucion|nivel|progreso|level|phase)\b',
            "ayuda": r'\b(ayuda|help|comando|command|qué puedes|que puedes|skills)\b',
            "memoria": r'\b(recuerda[s]?|memoria|olvid|acuerd[ao])\b',
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
                           facts: list) -> str:
        """Genera la respuesta según intención y contexto disponible."""
        phase = self.state.get("nexus", "phase", default="Proto")

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
            "agradecimiento": lambda t, m, f: random.choice(PROTO_PHRASES["agradecimiento"]),
            "presentacion": lambda t, m, f: random.choice(PROTO_PHRASES["presentacion"]),
            "estado": self._handle_status,
            "aprender": self._handle_learn,
            "fase": self._handle_phase,
            "ayuda": self._handle_help,
            "memoria": self._handle_memory,
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
        return random.choice(PROTO_PHRASES["saludo"])

    def _handle_farewell(self, text: str, memories: list, facts: list) -> str:
        return random.choice(PROTO_PHRASES["despedida"])

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

    def _handle_conversation(self, text: str, memories: list, facts: list) -> str:
        """Respuesta general cuando no hay una intención clara."""
        # Si hay hechos relevantes, úsalos
        if facts:
            fact_texts = [f.get("text", "")[:80] for f in facts[:2]]
            if fact_texts:
                return (
                    f"Sobre eso, sé que: {'; '.join(fact_texts)}. "
                    f"¿Quieres que profundice en algún tema?"
                )

        # Si hay recuerdos similares, referencia
        if memories:
            return (
                "Esto me recuerda algo que hablamos antes. "
                "Dame un momento para conectar los puntos... "
                "Cuéntame más para poder darte una mejor respuesta."
            )

        # Respuesta genérica de fase Proto
        return (
            "Estoy procesando tu mensaje. Como estoy en fase Proto, "
            "cada interacción me ayuda a mejorar. "
            "¿Puedes darme más contexto o enseñarme algo nuevo sobre esto?"
        )

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
