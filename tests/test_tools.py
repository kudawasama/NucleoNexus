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
        original_loaded = self.nexus.slm.loaded
        original_backend = self.nexus.state.get("capabilities", "backend")
        
        # Simular SLM cargado para que el flujo llegue al modo hibrido
        self.nexus.slm.loaded = True
        self.nexus.state.set("capabilities", "backend", value="hybrid")
        self.nexus.slm.model_name = "qwen2.5:0.5b"  # Forzar modo estructurado
        self.nexus.slm.generate = lambda *a, **k: {
            "response": '{"accion": "mi_herramienta_custom", "valor": "secreto123"}',
            "model": "qwen2.5:0.5b"
        }

        try:
            r, m = self.nexus.process("activa mi herramienta de test")
            self.assertEqual(m.get("tool_called"), "mi_herramienta_custom")
            self.assertIn("secreto123", r)
        finally:
            self.nexus.slm.generate = original_generate
            self.nexus.slm.model_name = original_model
            self.nexus.slm.loaded = original_loaded
            self.nexus.state.set("capabilities", "backend", value=original_backend)

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

    def test_git_security_auto_exclusion(self):
        """Verifica que el sistema de git automático bloquee y auto-excluya archivos sensibles."""
        import os
        from utils.git_auto import auto_commit_push
        
        # 1. Crear un archivo temporal sensible
        secret_file = "test_credentials.env"
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write("API_KEY=secreto123\n")
            
        # Leer el contenido original de .gitignore
        gitignore_path = ".gitignore"
        original_gitignore = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                original_gitignore = f.read()

        try:
            # 2. Ejecutar auto_commit_push, debería bloquearse
            success = auto_commit_push("test commit")
            self.assertFalse(success, "auto_commit_push debió bloquearse ante el archivo sensible")
            
            # 3. Verificar que se haya añadido al .gitignore
            with open(gitignore_path, "r", encoding="utf-8") as f:
                current_gitignore = f.read()
            self.assertIn(secret_file, current_gitignore, "El archivo sensible no fue añadido a .gitignore")
            
        finally:
            # Limpiar el archivo sensible
            if os.path.exists(secret_file):
                os.remove(secret_file)
            # Restaurar .gitignore
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(original_gitignore)

if __name__ == "__main__":
    unittest.main()
