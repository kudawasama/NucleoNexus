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

    def test_dynamic_action_routing(self):
        """Verifica que el orquestador resuelve dinámicamente cualquier herramienta registrada en ActionRegistry."""
        # 1. Registrar una acción de prueba en ActionRegistry
        def _dummy_tool(valor: str):
            return f"accion_ejecutada: {valor}"

        self.nexus.actions.register_fn(
            name="mi_herramienta_custom",
            description="Una herramienta dinamica de test",
            handler=_dummy_tool,
            parameters={
                "valor": {"type": "string"}
            }
        )

        original_generate = self.nexus.slm.generate
        original_model = self.nexus.slm.model_name
        
        # Simular respuesta del SLM en modo estructurado llamando a la herramienta registrada
        self.nexus.slm.model_name = "qwen2.5:0.5b"  # Forzar modo estructurado
        self.nexus.slm.generate = lambda *a, **k: {
            "response": '{"accion": "mi_herramienta_custom", "valor": "secreto123"}',
            "model": "qwen2.5:0.5b"
        }

        try:
            r, m = self.nexus.process("ejecuta mi herramienta de test")
            self.assertEqual(m.get("tool_called"), "mi_herramienta_custom")
            self.assertIn("secreto123", r)
        finally:
            self.nexus.slm.generate = original_generate
            self.nexus.slm.model_name = original_model

    def test_tool_security_allowlist(self):
        """Verifica que las herramientas bloqueen accesos y comandos fuera de PROJECT_ROOT."""
        # 1. Probar lectura/escritura/búsqueda fuera del proyecto
        res_read = self.nexus.actions.execute("read_file", path="../../../../etc/passwd")
        self.assertIn("error", res_read)
        self.assertIn("fuera del proyecto", res_read["error"])
        
        res_write = self.nexus.actions.execute("write_file", path="../../../../hacked.txt", content="malicious")
        self.assertIn("error", res_write)
        self.assertIn("fuera del proyecto", res_write["error"])

        res_search = self.nexus.actions.execute("search_files", pattern="confidencial", path="../../../../")
        self.assertIn("error", res_search)
        self.assertIn("fuera del proyecto", res_search["error"])

        # 2. Probar comandos con retroceso de directorios bloqueados
        res_cmd = self.nexus.actions.execute("run_command", command="cd ../../ && ls")
        self.assertIn("error", res_cmd)
        self.assertIn("bloqueado", res_cmd["error"])

    def test_api_mode_command_blocking(self):
        """Verifica que en modo API se bloqueen los comandos no autorizados."""
        import config
        from unittest.mock import patch

        # Modificar configuración temporalmente
        test_api_config = config.INTERFACE["api"].copy()
        test_api_config["enabled"] = True
        test_api_config["allowed_commands"] = ["git status", "dir"]

        with patch.dict(config.INTERFACE["api"], test_api_config):
            # 1. Comando no permitido en modo API
            res_bad = self.nexus.actions.execute("run_command", command="python malicious.py")
            self.assertIn("error", res_bad)
            self.assertIn("no permitido en modo API", res_bad["error"])

            # 2. Comando permitido en modo API
            res_good = self.nexus.actions.execute("run_command", command="git status")
            # Debería pasar la validación y ejecutarse (o dar error de ejecución, pero NO error de bloqueo API)
            if "error" in res_good:
                self.assertNotIn("no permitido en modo API", res_good["error"])

if __name__ == "__main__":
    unittest.main()
