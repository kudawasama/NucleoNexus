"""
Nucleo Nexus — Tests de Memoria y Sinonimia
==========================================
Valida el almacenamiento de hechos, alias de comandos y la expansión de consultas.
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

class TestMemoryAndSynonyms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nexus = NexusCore()
        cls.cli = NexusCLI(cls.nexus)

    def test_synonyms_auto_coche(self):
        """get_synonyms('auto') debe incluir 'coche'."""
        from learning.synonyms import get_synonyms
        syns = get_synonyms("auto")
        self.assertIn("coche", syns, f"'coche' no esta en sinonimos de 'auto': {syns}")

    def test_synonyms_coche_auto(self):
        """get_synonyms('coche') debe incluir 'auto' (bidireccional)."""
        from learning.synonyms import get_synonyms
        syns = get_synonyms("coche")
        self.assertIn("auto", syns, f"'auto' no esta en sinonimos de 'coche': {syns}")

    def test_synonyms_unknown_word(self):
        """Palabra desconocida devuelve la misma palabra."""
        from learning.synonyms import get_synonyms
        syns = get_synonyms("xyzzy")
        self.assertEqual(syns, ["xyzzy"], f"debio devolver ['xyzzy'], devolvio {syns}")

    def test_query_knowledge_uses_synonyms(self):
        """Si busca 'auto' debe encontrar hecho con 'coche' (sinonimos)."""
        # Limpiar y agregar hecho de prueba
        cur = self.nexus.memory.semantic.conn.cursor()
        cur.execute("DELETE FROM semantic WHERE source = 'test_synonyms'")
        self.nexus.memory.semantic.conn.commit()
        self.nexus.memory.learn_fact(
            "el coche es un vehiculo de transporte",
            category="test_synonyms", confidence=0.5, source="test_synonyms"
        )
        # Buscar con sinonimo
        facts = self.nexus.memory.semantic.query_knowledge("auto", top_k=3)
        matched = any("coche" in f.get("text", "") for f in facts)
        self.assertTrue(matched, f"query 'auto' no encontro hecho con 'coche': {facts}")

    def test_query_knowledge_expansion_medico(self):
        """Si busca 'medico' debe encontrar hecho con 'doctor'."""
        cur = self.nexus.memory.semantic.conn.cursor()
        cur.execute("DELETE FROM semantic WHERE source = 'test_synonyms'")
        self.nexus.memory.semantic.conn.commit()
        self.nexus.memory.learn_fact(
            "mi hermana es doctora en medicina",
            category="test_synonyms", confidence=0.5, source="test_synonyms"
        )
        facts = self.nexus.memory.semantic.query_knowledge("medico", top_k=3)
        matched = any("doctora" in f.get("text", "") for f in facts)
        self.assertTrue(matched, f"query 'medico' no encontro hecho con 'doctora': {facts}")

    def test_expand_query_basic(self):
        """expand_query debe retornar la query original como minimo."""
        from learning.synonyms import expand_query
        expanded = expand_query("que es python")
        self.assertIn("que es python", expanded, f"query original no esta en expansion: {expanded}")

    def test_expand_fact_storage(self):
        """expand_fact_storage genera sinonimos del hecho."""
        from learning.synonyms import expand_fact_storage
        expanded = expand_fact_storage("el auto es un vehiculo")
        self.assertGreaterEqual(len(expanded), 1, f"debio devolver al menos el original: {expanded}")
        has_synonym = any("coche" in e or "carro" in e for e in expanded)
        self.assertTrue(has_synonym, f"no hay sinonimos en: {expanded}")

    def test_synonyms_doesnt_break_existing(self):
        """query_knowledge normal (sin sinonimos) sigue funcionando."""
        facts = self.nexus.memory.semantic.query_knowledge("contabilidad", top_k=3)
        self.assertIsInstance(facts, list, "query_knowledge no retorna lista")

    def test_cmd_aprende_guarda_hecho(self):
        """/aprende guarda un hecho directamente."""
        before = self.nexus.memory.semantic.count()
        self.cli._cmd_learn("/aprende test_comando_aprende X es un dato unico")
        after = self.nexus.memory.semantic.count()
        self.assertGreater(after, before, f"/aprende no guardo el hecho: before={before}, after={after}")

    def test_cmd_aprende_sin_args_muestra_ayuda(self):
        """/aprende sin argumentos muestra ayuda."""
        # No debe fallar
        self.cli._cmd_learn("/aprende")

    def test_cmd_aprende_sobre_sugiere_web(self):
        """/aprende sobre X sugiere usar /aprende-web."""
        # No debe fallar
        self.cli._cmd_learn("/aprende sobre algo")

    def test_cmd_recuerda_alias_aprende(self):
        """/recuerda es alias de /aprende."""
        before = self.nexus.memory.semantic.count()
        self.cli._cmd_remember("/recuerda test_recuerda_alias funciona")
        after = self.nexus.memory.semantic.count()
        self.assertGreater(after, before, f"/recuerda no guardo el hecho: before={before}, after={after}")

    def test_cmd_olvida_borra_hecho(self):
        """/olvida borra un hecho de la memoria."""
        # Guardar uno primero
        self.cli._cmd_learn("/aprende test_olvida_xyz dato temporal unico")
        # Ahora borrarlo
        self.cli._cmd_forget("/olvida test_olvida_xyz")
        # Verificar que se borro
        facts = self.nexus.memory.semantic.query_knowledge("test_olvida_xyz", top_k=5)
        self.assertFalse(any("test_olvida_xyz" in f.get("text", "") for f in facts), "/olvida no borro el hecho")

    def test_cmd_olvida_no_falla_sin_args(self):
        """/olvida sin args no falla."""
        self.cli._cmd_forget("/olvida")

    def test_cmd_olvida_no_falla_sin_matches(self):
        """/olvida algo que no existe no falla."""
        self.cli._cmd_forget("/olvida algo_que_no_existe_12345")

    def test_contradiction_detection_raises_error(self):
        """Si existe una contradicción con un hecho de confianza > 0.8, debe lanzar ContradictionError."""
        # Limpiar
        cur = self.nexus.memory.semantic.conn.cursor()
        cur.execute("DELETE FROM semantic WHERE fact LIKE '%sol es%'")
        self.nexus.memory.semantic.conn.commit()

        # Guardar hecho con confianza 1.0 (alta)
        self.nexus.memory.learn_fact(
            "el sol es caliente y brillante",
            category="test_contra", confidence=1.0, source="test_contra"
        )

        # Intentar aprender un hecho contradictorio (antónimo: frío) con force=False
        from memory.semantic import ContradictionError
        with self.assertRaises(ContradictionError):
            self.nexus.memory.learn_fact(
                "el sol es frio y oscuro",
                category="test_contra", confidence=0.5, source="test_contra",
                force=False
            )

    def test_contradiction_detection_allows_force(self):
        """Si force=True, debe permitir guardar el hecho contradictorio."""
        # Guardar hecho con confianza 1.0 (alta)
        self.nexus.memory.learn_fact(
            "el agua es liquida y transparente",
            category="test_contra", confidence=1.0, source="test_contra",
            force=True
        )

        # Intentar aprender hecho contradictorio (negación) con force=True
        try:
            self.nexus.memory.learn_fact(
                "el agua no es liquida",
                category="test_contra", confidence=0.5, source="test_contra",
                force=True
            )
            success = True
        except Exception:
            success = False

        self.assertTrue(success, "debió permitir guardar con force=True")

    def test_arch_memory_3_types(self):
        """Memoria debe tener los 3 tipos: episodica, semantica, procedural."""
        self.assertIsNotNone(self.nexus.memory.episodic)
        self.assertIsNotNone(self.nexus.memory.semantic)
        self.assertIsNotNone(self.nexus.memory.procedural)

if __name__ == "__main__":
    unittest.main()
