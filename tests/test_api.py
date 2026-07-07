"""
Nucleo Nexus -- Pruebas del Servidor API
=========================================
Verifica el funcionamiento de los endpoints de la API y sus restricciones de seguridad.
"""

import unittest
import sys

try:
    from fastapi.testclient import TestClient
    from interface.api_server import app, get_nexus
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from main import NexusCore


@unittest.skipIf(not HAS_FASTAPI, "fastapi no instalado")
class TestAPIServer(unittest.TestCase):


class TestAPIServer(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Crear un core de pruebas y mockear la inyección de dependencias de get_nexus
        cls.nexus = NexusCore()
        app.dependency_overrides[get_nexus] = lambda: cls.nexus
        cls.client = TestClient(app)
        cls.valid_token = "nexus_secret_key_2026"

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.nexus.shutdown()

    def test_status_endpoint_unauthorized(self):
        """Verifica que status retorne 401 si no se envía token."""
        response = self.client.get("/v1/status")
        self.assertEqual(response.status_code, 401)

    def test_status_endpoint_bad_token(self):
        """Verifica que status retorne 401 con token incorrecto."""
        response = self.client.get("/v1/status", headers={"Authorization": "Bearer badtoken"})
        self.assertEqual(response.status_code, 401)

    def test_status_endpoint_authorized(self):
        """Verifica que status retorne 200 con token correcto."""
        response = self.client.get(
            "/v1/status",
            headers={"Authorization": f"Bearer {self.valid_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("nexus", data)

    def test_chat_endpoint(self):
        """Verifica que el chat responda correctamente con token válido."""
        response = self.client.post(
            "/v1/chat",
            json={"message": "hola"},
            headers={"Authorization": f"Bearer {self.valid_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("response", data)

    def test_memory_endpoint(self):
        """Verifica que memory registre hechos con token válido."""
        response = self.client.post(
            "/v1/memory",
            json={"fact": "La Tierra es el tercer planeta del sistema solar.", "category": "ciencia"},
            headers={"Authorization": f"Bearer {self.valid_token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()
