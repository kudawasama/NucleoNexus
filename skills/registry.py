"""
Núcleo Nexus — Registro de Skills
==================================
Las skills son módulos funcionales que expanden capacidades.
Cada skill se auto-registra con acciones para function calling.
Sigue el mismo patrón que ContanoPet: skills como funciones de código.
"""

import logging
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Callable

from engine.actions import Action, ActionRegistry

logger = logging.getLogger("nexus.skills.registry")


class Skill:
    """Una skill modular con nombre, descripción y acciones."""

    def __init__(self, name: str, description: str, version: str = "1.0.0",
                 author: str = "Nexus"):
        self.name = name
        self.description = description
        self.version = version
        self.author = author
        self.actions = ActionRegistry()
        self.active = True
        self.load_count = 0

    def register_action(self, name: str, description: str, handler: Callable,
                        parameters: dict = None, category: str = None):
        """Registra una acción dentro de esta skill."""
        cat = category or self.name
        action = Action(name, description, handler, parameters, cat)
        self.actions.register(action)
        return action

    def get_specs(self) -> dict:
        """Devuelve el manifesto de la skill."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "actions": [a.name for a in self.actions.list()],
            "active": self.active,
        }

    def __repr__(self):
        return f"<Skill '{self.name}' v{self.version} ({len(self.actions.list())} actions)>"


class SkillRegistry:
    """Registro central de skills cargadas en Nexus."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        """Registra una skill."""
        self._skills[skill.name] = skill
        logger.info(f"Skill registrada: {skill.name} v{skill.version}")

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list(self, active_only: bool = True) -> list[Skill]:
        skills = self._skills.values()
        if active_only:
            skills = [s for s in skills if s.active]
        return list(skills)

    def get_all_actions(self) -> ActionRegistry:
        """Recolecta todas las acciones de todas las skills en un solo registro."""
        master = ActionRegistry()
        for skill in self._skills.values():
            if skill.active:
                for action in skill.actions.list():
                    master.register(action)
        return master

    def stats(self) -> dict:
        total_actions = sum(len(s.actions.list()) for s in self._skills.values())
        return {
            "skills_loaded": len(self._skills),
            "active_skills": len([s for s in self._skills.values() if s.active]),
            "total_actions": total_actions,
        }

    def load_builtins(self, builtins_dir: str = None):
        """Carga las skills nativas desde skills/builtins/."""
        if builtins_dir is None:
            builtins_dir = str(Path(__file__).parent / "builtins")

        builtins_path = Path(builtins_dir)
        if not builtins_path.exists():
            logger.warning(f"Directorios de builtins no encontrado: {builtins_dir}")
            return

        # Carga scripts Python como skills
        for pyfile in sorted(builtins_path.glob("*.py")):
            if pyfile.name.startswith("_"):
                continue
            try:
                module_name = f"skills.builtins.{pyfile.stem}"
                spec = importlib.util.spec_from_file_location(module_name, pyfile)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Busca función register() en el módulo
                    if hasattr(module, "register"):
                        skill = module.register()
                        if isinstance(skill, Skill):
                            self.register(skill)
                            logger.info(f"Builtin cargada: {skill.name}")
            except Exception as e:
                logger.error(f"Error cargando builtin {pyfile.name}: {e}")
