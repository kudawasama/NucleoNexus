"""
Núcleo Nexus — Sistema de Acciones (Function Calling)
======================================================
Las acciones son funciones que la IA puede "llamar".
El motor de estado + las skills resuelven la lógica.
La IA solo orquesta — nunca calcula.
"""

from __future__ import annotations

import logging
import time
import inspect
from typing import Callable, Any

logger = logging.getLogger("nexus.engine.actions")


class Action:
    """Una acción invocable por la IA via function calling."""

    def __init__(self, name: str, description: str, handler: Callable,
                 parameters: dict = None, category: str = "general"):
        self.name = name
        self.description = description
        self.handler = handler
        self.parameters = parameters or {}
        self.category = category
        self.call_count = 0
        self.success_count = 0

    def execute(self, **kwargs) -> dict:
        """Ejecuta la accion y registra el resultado.
        Solo pasa los parametros que el handler acepta.
        """
        start = time.time()
        self.call_count += 1
        try:
            # Filtrar solo los kwargs que el handler acepta
            sig = inspect.signature(self.handler)
            valid_params = set(sig.parameters.keys())
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
            
            result = self.handler(**filtered_kwargs)
            elapsed = (time.time() - start) * 1000
            self.success_count += 1
            return {
                "success": True,
                "action": self.name,
                "result": result,
                "elapsed_ms": round(elapsed, 2),
            }
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(f"Error en acción '{self.name}': {e}")
            return {
                "success": False,
                "action": self.name,
                "error": str(e),
                "elapsed_ms": round(elapsed, 2),
            }

    def to_function_spec(self) -> dict:
        """Devuelve el spec para function calling compatible con OpenAI/Ollama."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [k for k, v in self.parameters.items()
                                 if v.get("required", False)],
                },
            },
        }

    def __repr__(self):
        return f"<Action '{self.name}' [{self.category}] {self.call_count} calls>"


class ActionRegistry:
    """Registro central de acciones disponibles para la IA."""

    def __init__(self):
        self._actions: dict[str, Action] = {}

    def register(self, action: Action):
        """Registra una acción."""
        self._actions[action.name] = action
        logger.info(f"Acción registrada: {action.name} [{action.category}]")

    def register_fn(self, name: str, description: str, handler: Callable,
                    parameters: dict = None, category: str = "general"):
        """Registra una acción desde una función directamente."""
        action = Action(name, description, handler, parameters, category)
        self.register(action)

    def get(self, name: str) -> Action | None:
        """Obtiene una acción por nombre."""
        return self._actions.get(name)

    def list(self, category: str = None) -> list[Action]:
        """Lista acciones, opcionalmente filtradas por categoría."""
        if category:
            return [a for a in self._actions.values() if a.category == category]
        return list(self._actions.values())

    def execute(self, name: str, **kwargs) -> dict:
        """Ejecuta una acción por nombre."""
        action = self.get(name)
        if not action:
            return {"success": False, "error": f"Acción '{name}' no encontrada"}
        return action.execute(**kwargs)

    def get_function_specs(self) -> list[dict]:
        """Devuelve todos los specs para function calling."""
        return [a.to_function_spec() for a in self._actions.values()]

    def stats(self) -> dict:
        return {
            "total_actions": len(self._actions),
            "total_calls": sum(a.call_count for a in self._actions.values()),
            "total_successes": sum(a.success_count for a in self._actions.values()),
        }
