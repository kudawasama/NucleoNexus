"""
Nucleo Nexus — Tests de Ruteo e Intents
=======================================
Valida la clasificación de intenciones de usuario y la navegación básica.
"""

import unittest
import sys
from pathlib import Path

# Configurar path del proyecto
BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))

from main import NexusCore

class TestRoutingAndIntents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nexus = NexusCore()

    def test_saludo(self):
        r, m = self.nexus.process("hola")
        self.assertEqual(m["backend"], "symbolic", "saludo no debe usar SLM")
        self.assertGreater(len(r), 5, "saludo vacío")

    def test_hora(self):
        r, m = self.nexus.process("que hora es")
        self.assertEqual(m["backend"], "symbolic", "hora no debe usar SLM")
        import re
        self.assertTrue(re.search(r'\d{1,2}:\d{2}', r), f"no muestra hora: {r}")

    def test_calculo(self):
        r, m = self.nexus.process("cuanto es 25 * 4")
        self.assertEqual(m["backend"], "symbolic", "calculo no debe usar SLM")
        self.assertIn("100", r, f"calculo incorrecto: {r}")

    def test_estado(self):
        r, m = self.nexus.process("/status")
        self.assertIn("Fase", r, f"status no muestra Fase: {r}")

    def test_fase(self):
        r, m = self.nexus.process("/fase")
        self.assertTrue("Fase" in r or "Intermedio" in r, f"fase no devuelve fase: {r}")

    def test_intent_nombre(self):
        """El intent 'nombre' debe dispararse con 'me llamo X'."""
        intent = self.nexus.symbolic.detect_intent("me llamo carlos")
        self.assertEqual(intent, "nombre", f"intent deberia ser 'nombre', es '{intent}'")

    def test_intent_ser_no_personalidad(self):
        """'ser cuadrado' no debe activar personalidad (regresion bug)."""
        intent = self.nexus.symbolic.detect_intent("que significa ser cuadrado")
        self.assertNotEqual(intent, "personalidad", f"'ser' no debe ser personalidad, es '{intent}'")

    def test_intent_aprender_no_saber(self):
        """'quiero saber' no debe activar aprender (regresion bug)."""
        intent = self.nexus.symbolic.detect_intent("quiero saber que es python")
        self.assertNotEqual(intent, "aprender", f"'saber' no debe ser aprender, es '{intent}'")

    def test_intent_que_es_es_definition(self):
        """'que es X' debe ir al SLM, no responder con memory."""
        r, m = self.nexus.process("que es la fotosintesis")
        self.assertIn(m["backend"], ("slm", "symbolic"), f"backend inesperado: {m['backend']}")

    def test_intent_pokemon_que_es(self):
        """'pokemon champion que es' debe detectarse como definicion (regresion)."""
        if not getattr(self.nexus.slm, 'loaded', False):
            self.skipTest("SLM no disponible")
        r, m = self.nexus.process("pokemon champion que es")
        self.assertNotIn("Esto me recuerda", r, f"debio ir al SLM, no a memoria: {r[:80]}")

    def test_hola_largo_no_es_saludo(self):
        """'Hola, dime como puedo...' NO es saludo, es conversacion."""
        intent = self.nexus.symbolic.detect_intent("hola dime como puedo pagar impuestos".lower())
        self.assertNotEqual(intent, "saludo", f"'hola dime...' no debe ser saludo, es {intent}")

    def test_hola_corto_si_es_saludo(self):
        """Pero 'hola' solo SI es saludo."""
        intent = self.nexus.symbolic.detect_intent("hola")
        self.assertEqual(intent, "saludo", f"'hola' debe ser saludo, es {intent}")

    def test_hola_punto_si_es_saludo(self):
        """'hola.' tambien es saludo."""
        intent = self.nexus.symbolic.detect_intent("hola!")
        self.assertEqual(intent, "saludo", f"'hola!' debe ser saludo, es {intent}")

    def test_hola_me_llamo_es_nombre(self):
        """'hola me llamo Carlos' es nombre (declaracion)."""
        intent = self.nexus.symbolic.detect_intent("hola me llamo carlos")
        self.assertEqual(intent, "nombre", f"'hola me llamo carlos' debe ser nombre, es {intent}")

    def test_hola_que_es_es_conversacion(self):
        """'hola que es python' va a conversacion, no saludo."""
        intent = self.nexus.symbolic.detect_intent("hola que es python")
        self.assertEqual(intent, "conversacion", f"'hola que es python' debe ser conversacion, es {intent}")

    def test_buenas_corto_si_es_saludo(self):
        """'buenas' solo es saludo."""
        intent = self.nexus.symbolic.detect_intent("buenas")
        self.assertEqual(intent, "saludo", f"'buenas' debe ser saludo, es {intent}")

    def test_buenas_largo_no_es_saludo(self):
        """'buenas tardes, necesito ayuda con X' no es saludo."""
        intent = self.nexus.symbolic.detect_intent("buenas tardes, necesito ayuda con mi proyecto")
        self.assertNotEqual(intent, "saludo", f"'buenas tardes, necesito...' no debe ser saludo, es {intent}")

    def test_hola_dime_impuestos_usa_slm(self):
        """'Hola, dime como puedo realizar ajuste de impuestos' -> SLM (no saludo)."""
        if not getattr(self.nexus.slm, 'loaded', False):
            self.skipTest("SLM no disponible")
        r, m = self.nexus.process("Hola, dime como puedo realizar un ajuste de impuestos en un monto bruto de 100000")
        self.assertEqual(m["backend"], "slm", f"debio ir al SLM, backend={m['backend']}")
        self.assertNotIn("Hola. Soy Nexus", r, f"respuesta generica, no personalizada: {r[:80]}")
        self.assertGreater(len(r), 50, f"respuesta muy corta: {r[:80]}")

if __name__ == "__main__":
    unittest.main()
