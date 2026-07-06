"""
Nucleo Nexus — Tests de Herramientas de Sistema
===============================================
Valida el funcionamiento de las herramientas integradas sin requerir SLM.
"""

import unittest
import sys
from pathlib import Path

# Configurar path del proyecto
BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))

from main import NexusCore

class TestSystemTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nexus = NexusCore()

    def test_tool_python_eval(self):
        r, m = self.nexus.process("calcula 8+1")
        self.assertIn("9", r, f"calculo no calculo 8+1: {r}")

    def test_tool_run_command(self):
        r, m = self.nexus.process("ejecuta echo test123")
        self.assertIn("test123", r, f"run_command no ejecuto: {r}")

    def test_tool_read_file(self):
        r, m = self.nexus.process("lee el archivo config.py")
        self.assertTrue("BASE_DIR" in r or "configuracion" in r, f"read_file no leyo: {r[:100]}")

    def test_tool_typo_bsuca(self):
        """'bsuca' (typo) debe activar web_search via regex permisiva."""
        r, m = self.nexus.process("bsuca en la web python")
        self.assertEqual(m.get("tool_called"), "web_search", f"typo no se tolera: {m}")

    def test_tool_browse_url(self):
        r, m = self.nexus.process("visita kudawa.com")
        self.assertIn(m.get("tool_called"), ("browse_url", "web_search"), f"browse_url no funciona: {m}")

if __name__ == "__main__":
    unittest.main()
