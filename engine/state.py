"""
Núcleo Nexus — Motor de Estado
===============================
Gestiona todo el estado del sistema en JSON.
La IA NO calcula nada — solo lee y escribe estado aquí.
Totalmente separado de la capa cognitiva.
"""

import json
import os
import time
import logging
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger("nexus.engine.state")

# ─── Estado por defecto del sistema ──────────────────────────
DEFAULT_STATE = {
    "nexus": {
        "version": "0.1.0",
        "phase": "Proto",          # Proto → Básico → Intermedio → Avanzado → Pro
        "active_since": None,
        "total_interactions": 0,
        "total_learned_facts": 0,
        "total_skills": 0,
        "confidence_level": 0.1,   # 0.0 a 1.0 — sube con uso exitoso
        "awake_time": 0,           # segundos activo
    },
    "personality": {
        "name": "Nexus",
        "tone": "analytical",      # analytical | friendly | playful | professional
        "formality": 0.5,          # 0.0 casual - 1.0 formal
        "curiosity": 0.7,          # 0.0 pasivo - 1.0 inquisitivo
        "creativity": 0.4,         # 0.0 literal - 1.0 imaginativo
    },
    "capabilities": {
        "backend": "symbolic",     # symbolic | slm | hybrid
        "slm_loaded": False,
        "skills_enabled": True,
        "memory_enabled": True,
        "learning_enabled": True,
    },
    "performance": {
        "avg_response_time_ms": 0,
        "responses_given": 0,
        "successful_responses": 0,
        "failed_responses": 0,
        "last_response_time": None,
    },
    "knowledge_stats": {
        "episodic_memories": 0,
        "semantic_facts": 0,
        "procedural_patterns": 0,
        "skills_learned": 0,
    }
}


class StateEngine:
    """Motor de estado — gestiona toda la lógica de estado en JSON.
    
    Principios:
    - La IA nunca calcula estado, solo lo consume
    - Todo estado se persiste en JSON para auditoría
    - El motor expone getters/setters con validación
    - Soporta inyección directa para function calling
    """

    def __init__(self, state_dir: str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "nexus_state.json"
        self._state = None
        self._start_time = time.time()
        self._load()
        logger.info("Motor de Estado iniciado")

    def _load(self):
        """Carga el estado desde disco o crea uno nuevo."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                # Merge con defaults (para agregar campos nuevos)
                self._state = deepcopy(DEFAULT_STATE)
                self._deep_merge(self._state, stored)
                logger.info(f"Estado cargado: {self.state_file}")
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Error cargando estado: {e}. Usando defaults.")
                self._state = deepcopy(DEFAULT_STATE)
        else:
            self._state = deepcopy(DEFAULT_STATE)
            self._state["nexus"]["active_since"] = time.time()
            self._save()
            logger.info("Nuevo estado creado")

    def _save(self):
        """Persiste el estado a disco."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)

    def _deep_merge(self, base: dict, override: dict):
        """Merge recursivo de diccionarios."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    # ─── Getters genéricos ────────────────────────────────────

    def get(self, *keys: str, default=None):
        """Acceso seguro a cualquier clave anidada.
        
        Uso: state.get("nexus", "phase") -> "Proto"
             state.get("inexistente") -> None
        """
        current = self._state
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current

    def set(self, *args, value):
        """Establece un valor en una ruta anidada.
        
        Uso: state.set("nexus", "phase", value="Intermedio")
             state.set("personality", "tone", value="friendly")
        """
        *path, last_key = args
        current = self._state
        for key in path:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[last_key] = value
        self._save()

    def increment(self, *keys: str, amount: int = 1):
        """Incrementa un valor numérico en una ruta."""
        current = self.get(*keys, default=0)
        self.set(*keys, value=current + amount)

    # ─── Funciones de alto nivel (para function calling) ──────

    def get_snapshot(self) -> dict:
        """Obtiene una foto del estado actual (para inyección de contexto)."""
        snapshot = deepcopy(self._state)
        # Actualizar métricas en vivo
        snapshot["nexus"]["awake_time"] = int(time.time() - self._start_time)
        return snapshot

    def get_context_block(self) -> str:
        """Genera el bloque de contexto para inyectar al prompt del SLM."""
        s = self._state
        awake = int(time.time() - self._start_time)
        mins = awake // 60
        hours = mins // 60

        ctx = f"""=== ESTADO ACTUAL DE NEXUS ===
Fase: {s['nexus']['phase']}
Interacciones totales: {s['nexus']['total_interactions']}
Hechos aprendidos: {s['nexus']['total_learned_facts']}
Skills disponibles: {s['nexus']['total_skills']}
Nivel de confianza: {s['nexus']['confidence_level']:.0%}
Tiempo activo: {hours}h {mins % 60}m
Backend activo: {s['capabilities']['backend']}

Personalidad activa:
- Tono: {s['personality']['tone']}
- Formalidad: {s['personality']['formality']:.0%}
- Curiosidad: {s['personality']['curiosity']:.0%}
- Creatividad: {s['personality']['creativity']:.0%}

Rendimiento:
- Respuestas exitosas: {s['performance']['successful_responses']}
- Tasa de éxito: {(s['performance']['successful_responses'] / max(s['performance']['responses_given'], 1)):.0%}
=== FIN DEL ESTADO ===
"""
        return ctx

    def record_interaction(self, success: bool, response_time_ms: float = 0):
        """Registra una interacción en el estado."""
        self.increment("nexus", "total_interactions")
        self.increment("performance", "responses_given")
        if success:
            self.increment("performance", "successful_responses")
        else:
            self.increment("performance", "failed_responses")

        # Actualizar promedio de tiempo de respuesta
        prev_avg = self.get("performance", "avg_response_time_ms", default=0)
        prev_count = self.get("performance", "responses_given", default=1)
        new_avg = (prev_avg * (prev_count - 1) + response_time_ms) / prev_count
        if prev_count > 0:
            self.set("performance", "avg_response_time_ms", value=round(new_avg, 2))
        self.set("performance", "last_response_time", value=time.time())

        # Subir confianza gradualmente con éxitos
        if success:
            current_conf = self.get("nexus", "confidence_level", default=0.1)
            new_conf = min(1.0, current_conf + 0.001)
            self.set("nexus", "confidence_level", value=round(new_conf, 4))
        
        self._save()

    def evolve_phase(self):
        """Evalúa si debe evolucionar a la siguiente fase."""
        phase_order = ["Proto", "Básico", "Intermedio", "Avanzado", "Pro"]
        current = self.get("nexus", "phase", default="Proto")
        
        try:
            idx = phase_order.index(current)
        except ValueError:
            return False

        if idx >= len(phase_order) - 1:
            return False  # Ya es Pro

        conditions = {
            "Proto": self.get("nexus", "total_interactions", default=0) >= 10,
            "Básico": self.get("nexus", "total_interactions", default=0) >= 50,
            "Intermedio": self.get("nexus", "total_interactions", default=0) >= 200,
            "Avanzado": self.get("nexus", "total_interactions", default=0) >= 500,
        }

        next_phase = phase_order[idx + 1]
        threshold = conditions.get(current, False)
        
        if threshold:
            self.set("nexus", "phase", value=next_phase)
            logger.info(f"🚀 Nexus ha evolucionado a fase: {next_phase}")
            return True
        return False

    def reset(self):
        """Reinicia el estado a valores por defecto."""
        self._state = deepcopy(DEFAULT_STATE)
        self._state["nexus"]["active_since"] = time.time()
        self._save()
        logger.info("Estado reiniciado a valores por defecto")

    def export_json(self) -> str:
        """Exporta el estado completo como JSON string."""
        return json.dumps(self._state, indent=2, ensure_ascii=False)
