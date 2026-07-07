"""
Nucleo Nexus — Tests del Extractor Automático
=============================================
Valida la extracción pasiva de hechos a partir de la entrada del usuario.
"""

import unittest
import sys
import time
from pathlib import Path

# Configurar path del proyecto
BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))

from main import NexusCore
from interface.cli import NexusCLI
from learning.extractor import extract_facts_from_text, learn_from_user_input

class TestFactExtractor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nexus = NexusCore()
        cls.cli = NexusCLI(cls.nexus)

    def test_cmd_analiza_extray_hechos(self):
        """/analiza extrae hechos de un texto."""
        # No debe fallar
        self.cli._cmd_analyze("/analiza python es un lenguaje interpretado")

    def test_extract_x_es_y(self):
        facts = extract_facts_from_text("el sol es una estrella")
        self.assertTrue(any("sol" in f and "estrella" in f for f in facts), f"no extrajo: {facts}")

    def test_extract_x_significa_y(self):
        facts = extract_facts_from_text("Python significa lenguaje de programacion")
        self.assertGreater(len(facts), 0, f"no extrajo 'significa': {facts}")

    def test_extract_x_vive_en_y(self):
        facts = extract_facts_from_text("un futbolista vive en Miami")
        self.assertTrue(any("futbolista" in f and "miami" in f for f in facts), f"no extrajo 'vive en': {facts}")

    def test_extract_learn_persists(self):
        """Aprender un hecho nuevo debe incrementar contador de memoria."""
        before = self.nexus.memory.semantic.count()
        unique_text = f"el marcador unico {int(time.time())} es un dato especial de prueba"
        learn_from_user_input(unique_text, self.nexus.memory)
        after = self.nexus.memory.semantic.count()
        self.assertGreater(after, before, f"no se guardo el hecho: before={before}, after={after}")

    def test_extract_filters_conjunctions(self):
        """Las palabras conectoras al final ('y', 'que') deben limpiarse."""
        facts = extract_facts_from_text("los pajaros vuelan alto y")
        for fact in facts:
            self.assertFalse(fact.rstrip().endswith(" y"), f"hecho termina con 'y': {fact}")

    def test_extract_filters_multiple_trailing_connectors(self):
        """Verifica que conectores múltiples al final son removidos recursivamente."""
        from learning.extractor import clean_fact_text
        cleaned = clean_fact_text("auto un vehiculo y de con para")
        self.assertEqual(cleaned, "auto un vehiculo")

    def test_extract_discards_stop_words_only(self):
        """Verifica que frases ruidosas compuestas en su mayoría por stop words son descartadas."""
        from learning.extractor import clean_fact_text
        # Frase con 100% de stop words
        self.assertEqual(clean_fact_text("el que de la con para"), "")
        # Frase demasiado corta
        self.assertEqual(clean_fact_text("sol"), "")

if __name__ == "__main__":
    unittest.main()
