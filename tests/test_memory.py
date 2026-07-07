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

    def test_episodic_memory_compression(self):
        """Verifica que al alcanzar el 80% de la capacidad episódica, se comprimen los recuerdos más viejos."""
        # 1. Limpiar recuerdos episódicos de prueba
        cur_ep = self.nexus.memory.episodic.conn.cursor()
        cur_ep.execute("DELETE FROM episodic")
        self.nexus.memory.episodic.conn.commit()

        # Limpiar hechos semánticos relacionados para evitar falsos positivos
        cur_sem = self.nexus.memory.semantic.conn.cursor()
        cur_sem.execute("DELETE FROM semantic WHERE source = 'compresion_episodica'")
        self.nexus.memory.semantic.conn.commit()

        # 2. Mockear el límite de la memoria episódica en config a un número pequeño (ej. 10)
        from unittest.mock import patch
        import config
        
        # Parchear el diccionario MEMORY en config
        test_memory_config = config.MEMORY.copy()
        test_memory_config["episodic_limit"] = 10
        
        with patch.dict(config.MEMORY, test_memory_config):
            # 3. Agregar recuerdos episódicos (80% de 10 es 8. Así que al insertar el 8vo recuerdo, debería disparar compresión)
            # El recuerdo más viejo contendrá un hecho para extraer
            self.nexus.memory.remember("user", "el sol es caliente y amarillo", context={"t": "viejo"})
            
            # Insertar 6 recuerdos más (total = 7)
            for i in range(6):
                self.nexus.memory.remember("user", f"mensaje irrelevante de prueba numero {i}", context={"t": "medio"})
                
            # Verificar que hasta aquí hay 7 recuerdos y ningún hecho en memoria semántica de compresión
            self.assertEqual(self.nexus.memory.episodic.count(), 7)
            facts_before = self.nexus.memory.semantic.get_facts_by_category("aprendizaje")
            comp_facts_before = [f for f in facts_before if f.get("source") == "compresion_episodica"]
            self.assertEqual(len(comp_facts_before), 0)

            # Insertar el 8vo recuerdo para disparar la compresión (8 >= 0.8 * 10)
            # Esto purgará el 20% más viejo de 10 = 2 recuerdos.
            self.nexus.memory.remember("user", "mensaje detonador final", context={"t": "detonador"})
            
            # 4. Verificar resultados:
            # - Total de recuerdos debería ser 8 - 2 (purgados) = 6 registros
            self.assertEqual(self.nexus.memory.episodic.count(), 6)
            
            # - El hecho del primer recuerdo ("el sol es caliente y amarillo") debió ser extraído y guardado en memoria semántica
            facts_after = self.nexus.memory.semantic.get_facts_by_category("aprendizaje")
            comp_facts_after = [f for f in facts_after if f.get("source") == "compresion_episodica"]
            self.assertGreaterEqual(len(comp_facts_after), 1, "Debería haber extraído al menos 1 hecho semántico")
            self.assertTrue(any("sol" in f["fact"] for f in comp_facts_after), "Debería haber extraído la información del sol")

    def test_ivf_index_search_accuracy(self):
        """Verifica que el índice IVF se construye correctamente y filtra candidatos de forma precisa."""
        import math, random
        random.seed(42)
        # 1. Crear conjunto de datos de prueba diversos
        items = []
        for i in range(120):
            # Generar vectores sintéticos con ruido para crear clusters reales
            if i < 40:
                base = 0.1
            elif i < 80:
                base = 0.5
            else:
                base = 0.9
            noise = [random.uniform(-0.05, 0.05) for _ in range(256)]
            vec = [max(0.01, base + n) for n in noise]
            norm = math.sqrt(sum(v*v for v in vec))
            vec = [v/norm for v in vec]
            items.append((i, vec))

        from memory.semantic import IVFIndex
        # 2. Construir índice con 5 centroides
        index = IVFIndex(k=5)
        index.build(items)

        # Verificar que se crearon los centroides y buckets
        self.assertEqual(len(index.centroids), 5)
        self.assertGreater(len(index.buckets), 0)

        # 3. Buscar usando un vector similar al grupo de astronomía
        noise = [random.uniform(-0.05, 0.05) for _ in range(256)]
        query_vec = [max(0.01, 0.12 + n) for n in noise]
        norm = math.sqrt(sum(v*v for v in query_vec))
        query_vec = [v/norm for v in query_vec]

        candidates = index.search(query_vec, n_probes=2)
        # Debería retornar una parte de los 120 elementos totales (filtrado)
        self.assertLess(len(candidates), 120, "El índice IVF no filtró ningún candidato")
        self.assertGreater(len(candidates), 0, "El índice IVF no retornó ningún candidato")

        self.assertIsNotNone(self.nexus.memory.episodic)
        self.assertIsNotNone(self.nexus.memory.semantic)
        self.assertIsNotNone(self.nexus.memory.procedural)

    def test_hybrid_rrf_search(self):
        """Verifica que la búsqueda híbrida unifique resultados usando RRF."""
        # 1. Limpiar base de datos semántica para pruebas controladas
        with self.nexus.memory.semantic.lock:
            cur = self.nexus.memory.semantic.conn.cursor()
            cur.execute("DELETE FROM semantic")
            self.nexus.memory.semantic.conn.commit()

        # 2. Insertar hechos de prueba
        self.nexus.memory.learn_fact("La luna orbita alrededor de la Tierra.", category="test_rrf", confidence=0.8, force=True)
        self.nexus.memory.learn_fact("La luna es redonda y de queso.", category="test_rrf", confidence=0.8, force=True)
        self.nexus.memory.learn_fact("El mar tiene peces y pulpos.", category="test_rrf", confidence=0.8, force=True)

        original_get_embedding = None
        original_is_available = None
        import memory.embeddings as embed_module
        original_get_embedding = embed_module.get_embedding
        original_is_available = embed_module.is_available
        
        embed_module.is_available = lambda: True
        mock_vec = [0.1] * 768
        embed_module.get_embedding = lambda text: mock_vec

        # Asignar un embedding al Hecho A en la base de datos
        from memory.embeddings import embed_to_blob
        with self.nexus.memory.semantic.lock:
            cur = self.nexus.memory.semantic.conn.cursor()
            cur.execute("UPDATE semantic SET embedding = ? WHERE fact LIKE 'La luna orbita%'", (embed_to_blob(mock_vec),))
            self.nexus.memory.semantic.conn.commit()

        try:
            # 3. Realizar consulta híbrida
            results = self.nexus.memory.query_knowledge("luna orbita la Tierra", top_k=2)
            self.assertGreater(len(results), 0)
            self.assertEqual(results[0]["text"], "La luna orbita alrededor de la Tierra.")
        finally:
            embed_module.get_embedding = original_get_embedding
            embed_module.is_available = original_is_available

    def test_syntactic_reranking(self):
        """Verifica que el re-ranking sintáctico priorice hechos por categoría y fuente."""
        with self.nexus.memory.semantic.lock:
            cur = self.nexus.memory.semantic.conn.cursor()
            cur.execute("DELETE FROM semantic")
            self.nexus.memory.semantic.conn.commit()

        # Insertar hechos con la misma confianza y coincidencia léxica básica, pero distinta categoría/fuente
        self.nexus.memory.learn_fact("La fotosíntesis produce oxígeno.", category="general", source="api", force=True)
        self.nexus.memory.learn_fact("Las plantas verdes realizan fotosíntesis.", category="biologia", source="system", force=True)

        original_is_available = None
        import memory.embeddings as embed_module
        original_is_available = embed_module.is_available
        embed_module.is_available = lambda: False

        try:
            # Consultar mencionando la palabra "biologia" en la consulta
            results = self.nexus.memory.query_knowledge("fotosíntesis en biologia", top_k=2)
            self.assertEqual(len(results), 2)
            # El Hecho B debe quedar primero debido a los boosts de categoría y fuente
            self.assertEqual(results[0]["text"], "Las plantas verdes realizan fotosíntesis.")
        finally:
            embed_module.is_available = original_is_available

if __name__ == "__main__":
    unittest.main()
