"""
Nucleo Nexus — Tests de Arquitectura y Robustez
===============================================
Valida la estructura en capas del proyecto y el comportamiento ante entradas inesperadas.
"""

import unittest
import sys
import json
from pathlib import Path

# Configurar path del proyecto
BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))

from main import NexusCore

class TestArchitectureAndRobustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nexus = NexusCore()

    def test_arch_layer_count(self):
        """Debe haber 6 modulos principales segun arquitectura."""
        expected = ["interface", "cognition", "skills", "engine", "memory", "knowledge"]
        for module in expected:
            path = BASE / module
            self.assertTrue(path.exists(), f"falta capa: {module}")

    def test_arch_state_persists(self):
        """El estado debe persistir en JSON."""
        state_path = BASE / "data/state/nexus_state.json"
        self.assertTrue(state_path.exists(), "no existe estado")
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertIn("nexus", state)
        self.assertIn("personality", state)
        self.assertIn("capabilities", state)

    def test_arch_actions_registered(self):
        """Acciones de skills deben estar registradas."""
        actions = self.nexus.actions.list()
        self.assertGreater(len(actions), 5, f"pocas acciones: {len(actions)}")

    def test_arch_skills_loaded(self):
        """Skills nativas + tools deben estar cargadas."""
        skills = self.nexus.skills.list()
        self.assertGreaterEqual(len(skills), 3, f"pocas skills: {len(skills)}")

    def test_edge_empty(self):
        r, m = self.nexus.process("")
        self.assertGreater(len(r), 0, "input vacio da respuesta vacia")

    def test_edge_whitespace(self):
        r, m = self.nexus.process("   ")
        self.assertGreater(len(r), 0)

    def test_edge_punctuation(self):
        r, m = self.nexus.process("¿?¡!")
        self.assertGreater(len(r), 0)

    def test_robust_50_iterations(self):
        """50 interacciones sin crash (queries livianas)."""
        queries = ["hola", "que hora es", "test", "cuanto es 2+2", "/fase", "/status"]
        for j in range(50):
            self.nexus.process(queries[j % len(queries)])

if __name__ == "__main__":
    unittest.main()
