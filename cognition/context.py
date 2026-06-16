"""
Núcleo Nexus — Inyección de Contexto Dinámico
==============================================
Construye el prompt de sistema que se inyecta al backend de IA.
Une: estado actual + memoria relevante + skills disponibles.
Es el puente entre el motor de lógica y la capa cognitiva.
"""

import logging
from engine.state import StateEngine
from skills.registry import SkillRegistry

logger = logging.getLogger("nexus.cognition.context")


class ContextBuilder:
    """Construye el contexto dinámico para inyectar al modelo de IA.
    
    Ejemplo de salida:
    === ESTADO DE NEXUS ===
    Fase: Proto | Interacciones: 42
    === MEMORIA RELEVANTE ===
    [Recuerdo] El usuario preguntó sobre...
    === SKILLS DISPONIBLES ===
    - get_status: Obtiene el estado del sistema
    - learn_fact: Aprende un nuevo hecho
    """

    def __init__(self, state_engine: StateEngine, skill_registry: SkillRegistry,
                 memory=None):
        self.state = state_engine
        self.skills = skill_registry
        self.memory = memory  # Sistema de memoria opcional

    def build(self, user_input: str = "", personality_override: dict = None) -> str:
        """Construye el prompt de sistema completo."""
        parts = []

        # 1. Personalidad base
        personality = self._build_personality(personality_override)
        parts.append(personality)

        # 2. Estado actual
        state_block = self.state.get_context_block()
        parts.append(state_block)

        # 3. Memoria relevante (RAG)
        if self.memory and user_input:
            memory_block = self._build_memory_context(user_input)
            if memory_block:
                parts.append(memory_block)

        # 4. Skills/Acciones disponibles
        skills_block = self._build_skills_context()
        parts.append(skills_block)

        # 5. Directivas
        directives = self._build_directives()
        parts.append(directives)

        return "\n\n".join(parts)

    def _build_personality(self, override: dict = None) -> str:
        """Construye el bloque de personalidad."""
        p = self.state.get("personality", default={})
        if override:
            p.update(override)

        tone_desc = {
            "analytical": "analítico, preciso, basado en datos",
            "friendly": "amigable, cálido, conversacional",
            "playful": "juguetón, divertido, con humor",
            "professional": "profesional, formal, ejecutivo",
        }

        desc = tone_desc.get(p.get("tone", "analytical"), "analítico")

        return f"""Eres Nexus, un sistema de IA en evolución.
Personalidad: {desc}
Nivel de formalidad: {p.get('formality', 0.5):.0%}
Curiosidad: {p.get('curiosity', 0.7):.0%}
Creatividad: {p.get('creativity', 0.4):.0%}

Reglas de oro:
- Tus respuestas deben ser en español, claras y directas
- Puedes usar las skills disponibles para ejecutar acciones
- Cuando no sepas algo, dilo honestamente
- Aprendes de cada interacción — cada conversación te hace más inteligente"""

    def _build_memory_context(self, user_input: str) -> str:
        """Construye el bloque de memoria relevante (RAG)."""
        if not self.memory:
            return ""

        lines = ["=== MEMORIA RELEVANTE ==="]

        # Recuerdos episódicos similares
        memories = self.memory.recall(user_input, top_k=3)
        if memories:
            lines.append("Recuerdos de interacciones similares:")
            for i, mem in enumerate(memories, 1):
                text = mem.get("text", "")[:120]
                score = mem.get("score", 0)
                lines.append(f"  [{i}] (sim: {score:.2f}) {text}")

        # Hechos semánticos relevantes
        facts = self.memory.query_knowledge(user_input, top_k=2)
        if facts:
            lines.append("\nHechos que sé sobre esto:")
            for fact in facts:
                lines.append(f"  - {fact.get('text', '')[:100]}")

        # Historial reciente
        history = self.memory.get_conversation_history(limit=4)
        if history:
            lines.append("\nÚltimos mensajes:")
            for msg in history[-4:]:
                lines.append(f"  {msg['label']}: {msg['content'][:80]}")

        lines.append("=== FIN MEMORIA ===")
        return "\n".join(lines)

    def _build_skills_context(self) -> str:
        """Construye el bloque de skills disponibles."""
        if not self.skills:
            return ""
        all_actions = self.skills.get_all_actions()
        actions = all_actions.list()

        if not actions:
            return ""

        lines = ["=== SKILLS DISPONIBLES ==="]
        lines.append("Puedes usar estas acciones si es necesario:")
        for action in actions[:10]:  # Top 10 para no saturar
            lines.append(f"  → {action.name}: {action.description}")
        lines.append("Para usar una acción, responde con: [[accion:nombre(parametros)]]")
        lines.append("=== FIN SKILLS ===")
        return "\n".join(lines)

    def _build_directives(self) -> str:
        """Directivas de comportamiento."""
        phase = self.state.get("nexus", "phase", default="Proto")
        confidence = self.state.get("nexus", "confidence_level", default=0.1)

        return f"""=== DIRECTIVAS ===
Fase actual: {phase}
Confianza: {confidence:.0%}

Directivas según fase:
- Proto (>10 interacciones): Responde con frases cortas, aprende patrones básicos
- Básico (>50): Puedes usar tus skills, empieza a mostrar personalidad
- Intermedio (>200): Razonamiento multicapa, respuestas elaboradas
- Avanzado (>500): Análisis profundo, aprendizaje autodirigido
- Pro (>1000): Operación autónoma, creatividad plena

Estás en fase {phase}. Ajusta tu complejidad según esto.
=== FIN DIRECTIVAS ==="""

    def summarize_recent(self, limit: int = 5) -> str:
        """Resumen corto para el prompt del SLM."""
        if not self.memory:
            return ""
        history = self.memory.get_conversation_history(limit=limit)
        if not history:
            return ""
        lines = ["Contexto reciente:"]
        for msg in history:
            lines.append(f"  {msg['label']}: {msg['content'][:100]}")
        return "\n".join(lines)
