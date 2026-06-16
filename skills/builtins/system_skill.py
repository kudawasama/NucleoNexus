"""
Skills Builtin — Sistema
=========================
Skill base del sistema: estado, version, metrica, salud.
"""

import time
from skills.registry import Skill


def register() -> Skill:
    """Registra y devuelve la skill del sistema."""
    skill = Skill(
        name="system",
        description="Habilidades base del sistema: estado, métricas, configuración",
        version="1.0.0",
        author="Nexus Core"
    )

    # ─── get_status ───────────────────────────────────────────
    def _get_status(state_engine=None):
        """Obtiene el estado actual del sistema."""
        if state_engine:
            return state_engine.get_snapshot()
        return {"status": "ok", "message": "Nexus operativo"}

    skill.register_action(
        name="get_status",
        description="Obtiene el estado actual completo del sistema Nexus",
        handler=_get_status,
        parameters={
            "include_all": {
                "type": "boolean",
                "description": "Incluir todas las métricas",
                "default": True,
            }
        },
    )

    # ─── get_time ─────────────────────────────────────────────
    def _get_time():
        """Devuelve la hora actual."""
        return {"timestamp": time.time(), "human": time.strftime("%Y-%m-%d %H:%M:%S")}

    skill.register_action(
        name="get_time",
        description="Obtiene la fecha y hora actual del sistema",
        handler=_get_time,
    )

    # ─── set_personality ──────────────────────────────────────
    def _set_personality(tone: str = None, formality: float = None,
                          curiosity: float = None, creativity: float = None,
                          state_engine=None):
        """Ajusta la personalidad de Nexus."""
        if not state_engine:
            return {"error": "state_engine no disponible"}
        changes = {}
        if tone:
            state_engine.set("personality", "tone", value=tone)
            changes["tone"] = tone
        if formality is not None:
            state_engine.set("personality", "formality", value=min(1.0, max(0.0, formality)))
            changes["formality"] = formality
        if curiosity is not None:
            state_engine.set("personality", "curiosity", value=min(1.0, max(0.0, curiosity)))
            changes["curiosity"] = curiosity
        if creativity is not None:
            state_engine.set("personality", "creativity", value=min(1.0, max(0.0, creativity)))
            changes["creativity"] = creativity
        return {"success": True, "changes": changes}

    skill.register_action(
        name="set_personality",
        description="Ajusta los parámetros de personalidad de Nexus",
        handler=_set_personality,
        parameters={
            "tone": {
                "type": "string",
                "description": "Tono: analytical, friendly, playful, professional",
                "enum": ["analytical", "friendly", "playful", "professional"],
            },
            "formality": {
                "type": "number",
                "description": "Nivel de formalidad (0.0 casual - 1.0 formal)",
            },
            "curiosity": {
                "type": "number",
                "description": "Nivel de curiosidad (0.0 pasivo - 1.0 inquisitivo)",
            },
            "creativity": {
                "type": "number",
                "description": "Nivel de creatividad (0.0 literal - 1.0 imaginativo)",
            },
        },
    )

    return skill
