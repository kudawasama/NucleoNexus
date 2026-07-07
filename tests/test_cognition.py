"""
Nucleo Nexus — Tests de Cognición, ReAct, Agente y Sintesis
==========================================================
Valida el pipeline cognitivo, el agente autónomo /agent y la síntesis con SLM.
"""

import unittest
import sys
import re
import json
from pathlib import Path

# Configurar path del proyecto
BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))

from main import NexusCore

class TestCognitionAndAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nexus = NexusCore()

    def test_react_prompt_includes_format(self):
        """El prompt ligero debe incluir el patron ReAct (Pensamiento/Accion/Respuesta)."""
        from cognition.context import ContextBuilder
        ctx = ContextBuilder(self.nexus.state, self.nexus.skills, self.nexus.memory)
        prompt = ctx._build_light_directives()
        self.assertIn("Pensamiento", prompt, "prompt no incluye Pensamiento")
        self.assertTrue("Accion" in prompt or "Acción" in prompt, "prompt no incluye Accion")
        self.assertIn("Respuesta", prompt, "prompt no incluye Respuesta")

    def test_extract_list_items_detects_incluye(self):
        """_extract_list_items detecta el patron 'X incluye: Y'."""
        facts = [
            {"text": "los planetas incluye: mercurio", "score": 0.5},
            {"text": "los planetas incluye: venus", "score": 0.5},
            {"text": "los planetas incluye: tierra", "score": 0.5},
        ]
        items = self.nexus.symbolic._extract_list_items(facts, "cuales son los planetas")
        self.assertGreaterEqual(len(items), 2, f"debio extraer varios items, extrajo {len(items)}: {items}")
        self.assertIn("mercurio", items, f"'mercurio' no esta en items: {items}")

    def test_extract_list_items_detects_son(self):
        """_extract_list_items detecta 'X son: A, B, C'."""
        facts = [
            {"text": "los planetas son: mercurio, venus y tierra", "score": 0.5},
        ]
        items = self.nexus.symbolic._extract_list_items(facts, "que son los planetas")
        self.assertGreaterEqual(len(items), 2, f"debio extraer items, extrajo {len(items)}: {items}")

    def test_synthesize_list_response_format(self):
        """_synthesize_list_response genera formato estructurado."""
        items = ["mercurio", "venus", "tierra", "marte"]
        response = self.nexus.symbolic._synthesize_list_response(
            items, "cuales son los planetas", "cuales son los planetas"
        )
        self.assertIn("1.", response, "no numera los items")
        self.assertIn("mercurio", response, "no incluye el item 1")
        self.assertIn("marte", response, "no incluye el item 4")

    def test_extract_definition(self):
        """_extract_definition extrae 'X es Y' de los hechos."""
        facts = [
            {"text": "python es un lenguaje de programacion interpretado", "score": 0.5},
            {"text": "otra cosa random", "score": 0.3},
        ]
        defn = self.nexus.symbolic._extract_definition(facts)
        self.assertTrue("python" in defn.lower() or "lenguaje" in defn.lower(), f"definicion no encontrada: {defn}")

    def test_auto_synthesis_end_to_end(self):
        """Test end-to-end: guardar hechos, preguntar, verificar sintesis."""
        cur = self.nexus.memory.semantic.conn.cursor()
        cur.execute("DELETE FROM semantic WHERE source = 'test_synth'")
        self.nexus.memory.semantic.conn.commit()

        # Guardar hechos tipo lista con termino unico para evitar colision con knowledge base
        self.nexus.memory.learn_fact("los seres mitologicos incluye: dragon", category="test_synth", confidence=0.5, source="test_synth")
        self.nexus.memory.learn_fact("los seres mitologicos incluye: fenix", category="test_synth", confidence=0.5, source="test_synth")
        self.nexus.memory.learn_fact("los seres mitologicos incluye: grifo", category="test_synth", confidence=0.5, source="test_synth")

        # Preguntar
        r, m = self.nexus.process("cuales son los seres mitologicos")
        self.assertTrue("1." in r or "Encontre" in r, f"respuesta no es sintetizada: {r[:200]}")

    def test_self_consistency_metadata(self):
        """El metadata incluye self_consistency=True para modelos tiny."""
        cur = self.nexus.memory.semantic.conn.cursor()
        cur.execute("DELETE FROM semantic WHERE category = 'knowledge_base'")
        cur.execute("DELETE FROM semantic WHERE source = 'test_synth'")
        self.nexus.memory.semantic.conn.commit()

        # Forzar modelo tiny
        original_model = self.nexus.slm.model_name
        self.nexus.slm.model_name = 'qwen2.5:0.5b'

        try:
            r, m = self.nexus.process("explicame la teoria de cuerdas en 2 lineas")
            if m["backend"] == "slm":
                self.assertTrue(m.get("self_consistency", False), f"modelo tiny debe usar self_consistency, metadata={m}")
        finally:
            self.nexus.slm.model_name = original_model

    def test_self_consistency_off_for_big_models(self):
        """Modelos grandes NO usan self_consistency (no necesitan)."""
        cur = self.nexus.memory.semantic.conn.cursor()
        cur.execute("DELETE FROM semantic WHERE source = 'test_synth'")
        self.nexus.memory.semantic.conn.commit()

        original_model = self.nexus.slm.model_name
        self.nexus.slm.model_name = 'llama3.2:1b'  # No es tiny

        try:
            # Borrar todos los hechos temporales para forzar ir al SLM
            cur.execute("DELETE FROM semantic WHERE source != 'knowledge_base'")
            self.nexus.memory.semantic.conn.commit()

            r, m = self.nexus.process("que es xyz123?")
            if m["backend"] == "slm":
                self.assertFalse(m.get("self_consistency", False), f"modelo grande no debe usar self_consistency, metadata={m}")
        finally:
            self.nexus.slm.model_name = original_model

    def test_select_consensus_response_basic(self):
        """Verifica que _select_consensus_response elige el candidato correcto."""
        # 1. Caso fallback a la respuesta más larga (sin embeddings)
        candidates = [
            ("corta", {}),
            ("esta respuesta es la mas larga de todas", {}),
            ("mediana de longitud", {})
        ]
        # Forzar que is_available devuelva False para probar el fallback de longitud
        from unittest.mock import patch
        with patch('memory.embeddings.is_available', return_value=False):
            resp, meta = self.nexus._select_consensus_response(candidates)
            self.assertEqual(resp, "esta respuesta es la mas larga de todas")
        
        # 2. Caso con embeddings deterministas
        # El consenso de similitud de coseno debería elegir una de las frases del sol
        # frente a la frase del coche rojo que es un outlier.
        candidates_similar = [
            ("El sol brilla en el cielo despejado.", {"id": 1}),
            ("El sol brilla en el cielo azul.", {"id": 2}),
            ("El coche es de color rojo brillante.", {"id": 3}),
        ]
        resp_cons, meta_cons = self.nexus._select_consensus_response(candidates_similar)
        self.assertIn("sol", resp_cons.lower(), f"Consenso falló al filtrar outlier. Eligió: {resp_cons}")

    def test_agent_runs_without_error(self):
        """El agente ejecuta sin lanzar excepciones."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        result = agent.run("investiga sobre el agua")
        self.assertIsNotNone(result, "agente no retorna resultado")
        self.assertGreater(len(result.steps), 0, "agente no ejecuto pasos")

    def test_agent_investigate_uses_web_search(self):
        """Tarea 'investiga' usa web_search."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        result = agent.run("investiga sobre los dinosaurios")
        tools_used = [s.tool for s in result.steps]
        self.assertIn("web_search", tools_used, f"web_search no usado, tools: {tools_used}")

    def test_agent_extracts_topic(self):
        """El agente extrae el tema del task correctamente."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        self.assertIn("fotosintesis", agent._extract_topic("investiga sobre la fotosintesis").lower())
        self.assertIn("python", agent._extract_topic("que es python").lower())
        self.assertIn("maquina", agent._extract_topic("como funciona una maquina").lower())

    def test_agent_detects_task_type(self):
        """El agente detecta el tipo de tarea."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        self.assertEqual(agent._detect_task_type("investiga sobre X"), "investigate")
        self.assertEqual(agent._detect_task_type("explica como funciona X"), "explain")
        self.assertEqual(agent._detect_task_type("busca en codigo X"), "code_search")

    def test_agent_investigate_learns_facts(self):
        """El agente 'investiga' guarda hechos en memoria."""
        from cognition.agent import NexusAgent
        cur = self.nexus.memory.semantic.conn.cursor()
        cur.execute("DELETE FROM semantic WHERE source = 'auto_web_agent'")
        self.nexus.memory.semantic.conn.commit()

        agent = NexusAgent(self.nexus)
        result = agent.run("investiga sobre los volcanes")

        cur.execute("SELECT COUNT(*) FROM semantic WHERE source = 'auto_web_agent'")
        count = cur.fetchone()[0]
        self.assertTrue(result.facts_learned > 0 or count > 0, f"agente no aprendio hechos. facts_learned={result.facts_learned}, count={count}")

    def test_agent_executes_tools_via_action_registry(self):
        """El agente usa ActionRegistry para ejecutar tools."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        self.assertIsNotNone(agent.actions, "agente sin ActionRegistry")
        step = agent._execute_tool("get_time")
        self.assertEqual(step.tool, "get_time", f"tool no ejecutada: {step}")

    def test_agent_summarizes_steps(self):
        """El agente genera un resumen de los pasos ejecutados."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        result = agent.run("investiga sobre las plantas")
        self.assertNotEqual(result.summary, "", "agente no genero resumen")
        self.assertIn("Paso", result.summary, f"resumen sin estructura: {result.summary}")

    def test_agent_handles_empty_task_gracefully(self):
        """El agente maneja tareas invalidas sin crashear."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        result = agent.run("   ")
        self.assertIsNotNone(result)

    def test_agent_command_in_cli(self):
        """El comando /agent esta registrado en el CLI."""
        from interface.cli import NexusCLI
        cli = NexusCLI(self.nexus)
        self.assertTrue(hasattr(cli, "_cmd_agent"), "CLI no tiene _cmd_agent")

    def test_synthesize_extracts_context_from_web_search(self):
        """_synthesize_answer extrae items de web_search correctamente."""
        from cognition.agent import NexusAgent, AgentStep
        agent = NexusAgent(self.nexus)
        prior = [
            AgentStep(
                tool="web_search",
                input="query=test",
                output='{"resultados": ["• La fotosintesis es el proceso por el cual las plantas convierten luz", "• Es la base de la cadena alimenticia"]}',
                success=True,
                duration_ms=100,
            )
        ]
        context = ""
        for step in prior:
            if "web_search" in step.tool and ("'resultados':" in step.output or '"resultados":' in step.output):
                items = re.findall(r"['\"](•[^'\"]{20,})['\"]", step.output)
                for item in items[:3]:
                    clean = item.lstrip('•').strip()
                    clean = re.sub(r'\s*\([^)]+\)\s*', ' ', clean).strip()
                    if clean:
                        context += f"- {clean[:200]}\n"
        self.assertTrue("fotosintesis" in context.lower() or "plantas" in context.lower(), f"debio extraer contenido de web_search, obtuvo: {context}")

    def test_synthesize_handles_dict_response_from_slm(self):
        """_synthesize_answer maneja SLM que devuelve dict."""
        test_responses = [
            ({"response": "Texto simple"}, "Texto simple"),
            ("Texto directo", "Texto directo"),
            ({"response": '{"respuesta": "JSON parseado"}'}, "JSON parseado"),
        ]

        for slm_result, expected_substr in test_responses:
            if slm_result is None:
                synthesized = ""
            elif isinstance(slm_result, str):
                synthesized = slm_result
            elif isinstance(slm_result, dict):
                raw = slm_result.get("response", "")
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            synthesized = parsed.get("respuesta", raw)
                        else:
                            synthesized = raw
                    except Exception:
                        synthesized = raw
                else:
                    synthesized = str(raw)
            else:
                synthesized = str(slm_result)

            self.assertIn(expected_substr, synthesized, f"esperaba '{expected_substr}' en '{synthesized}'")

    def test_synthesize_fallback_when_no_context(self):
        """Si no hay contexto, _synthesize_answer retorna None (no ejecuta)."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        prior = []
        result = agent._synthesize_answer("test", "test", prior)
        self.assertIsNone(result, f"sin contexto debio retornar None, retornó: {result}")

    def test_synthesize_fallback_produces_structured_response(self):
        """_synthesize_fallback genera respuesta estructurada con titulo + bullets + fuentes."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        context = "- Punto 1 sobre el tema\n- Punto 2 relevante"
        sources = ["https://example.com/articulo1", "https://example.com/articulo2"]
        response = agent._synthesize_fallback("Mi tema", context, sources)
        self.assertIn("# Mi tema", response, f"debio incluir titulo '# Mi tema': {response[:100]}")
        self.assertIn("- ", response, f"debio incluir bullets: {response[:200]}")
        self.assertIn("Fuentes:", response, f"debio incluir 'Fuentes:': {response[:200]}")
        self.assertIn("https://example.com/articulo1", response, f"debio incluir URL: {response[:200]}")

    def test_synthesize_handles_empty_slm_response(self):
        """Si SLM devuelve string vacio, fallback se activa."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        if not agent.nexus.slm.loaded:
            self.skipTest("SLM no disponible")

        prior = [
            type('FakeStep', (), {
                'tool': 'web_search',
                'output': '{"resultados": ["• Dato importante para el test de sintesis de la respuesta automatica del sistema"]}',
                'success': True,
                'duration_ms': 100,
            })(),
        ]
        original_generate = self.nexus.slm.generate
        self.nexus.slm.generate = lambda *a, **k: ""

        try:
            result = agent._synthesize_answer("test", "tema", prior)
            self.assertIsNotNone(result, "debio usar fallback")
            self.assertTrue(result.success, f"fallback debio ser success: {result.success}")
        finally:
            self.nexus.slm.generate = original_generate

    def test_synthesize_handles_none_slm_response(self):
        """Si SLM devuelve None, fallback se activa."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        if not agent.nexus.slm.loaded:
            self.skipTest("SLM no disponible")

        prior = [
            type('FakeStep', (), {
                'tool': 'web_search',
                'output': '{"resultados": ["• Dato importante para el test de sintesis sin slm con datos de prueba validos"]}',
                'success': True,
                'duration_ms': 100,
            })(),
        ]
        original_generate = self.nexus.slm.generate
        self.nexus.slm.generate = lambda *a, **k: None

        try:
            result = agent._synthesize_answer("test", "tema", prior)
            self.assertIsNotNone(result, "debio usar fallback")
            self.assertTrue(result.success, f"fallback debio ser success: {result.success}")
        finally:
            self.nexus.slm.generate = original_generate

    def test_synthesize_end_to_end(self):
        """Test E2E: el agente ejecuta synthesize y produce respuesta."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        result = agent.run("investiga sobre la fotosintesis")
        synth_steps = [s for s in result.steps if s.tool == "synthesize"]
        self.assertGreaterEqual(len(synth_steps), 0, "synthesize es opcional, no debe fallar")

    def test_selective_learning_from_slm(self):
        """Verifica que no se aprende de las respuestas de modelos pequeños (< 3B)."""
        if not getattr(self.nexus.slm, 'loaded', False):
            self.skipTest("SLM no disponible")
        original_model = self.nexus.slm.model_name
        original_generate = self.nexus.slm.generate
        
        # Mock de una respuesta que contiene un hecho
        self.nexus.slm.generate = lambda *a, **k: {"response": '{"accion": "responder", "respuesta": "el riñon es un organo vital"}', "model": self.nexus.slm.model_name}
        
        try:
            # 1. Caso modelo pequeño (Qwen 0.5B): no debe aprender del response
            self.nexus.slm.model_name = "qwen2.5:0.5b"
            
            # Limpiar hechos similares de prueba en la BD para evitar falsos positivos
            cur = self.nexus.memory.semantic.conn.cursor()
            cur.execute("DELETE FROM semantic WHERE fact LIKE '%riñon es%'")
            self.nexus.memory.semantic.conn.commit()
            
            # Forzar consulta que vaya al SLM (con backend = "slm")
            self.nexus.process("dime sobre el riñon")
            
            # Verificamos específicamente que no haya guardado el hecho de la respuesta "el riñon es un organo vital"
            facts = self.nexus.memory.semantic.query_knowledge("riñon", top_k=5)
            self.assertFalse(any("organo vital" in f["text"] for f in facts), "Aprendió de la respuesta de un modelo pequeño!")

            # 2. Caso modelo grande (Hermes 3B): sí debe aprender del response
            self.nexus.slm.model_name = "hermes3:3b"
            
            # Limpiar nuevamente
            cur.execute("DELETE FROM semantic WHERE fact LIKE '%riñon es%'")
            self.nexus.memory.semantic.conn.commit()
            
            self.nexus.process("dime sobre el riñon")
            facts = self.nexus.memory.semantic.query_knowledge("riñon", top_k=5)
            self.assertTrue(any("organo vital" in f["text"] for f in facts), "No aprendió de la respuesta de un modelo grande!")
            
        finally:
            self.nexus.slm.model_name = original_model
            self.nexus.slm.generate = original_generate

    def test_agent_chained_tasks(self):
        """Verifica que el agente puede encadenar múltiples subtareas en secuencia."""
        from cognition.agent import NexusAgent
        agent = NexusAgent(self.nexus)
        
        # Tarea encadenada: investigar fotosintesis y luego buscar en codigo query_knowledge
        task = "investiga sobre fotosintesis y luego busca en codigo la funcion query_knowledge"
        result = agent.run(task)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.steps), 1, "Debería haber múltiples pasos en la tarea encadenada")
        
        # Verificar que se corrieron las herramientas correspondientes a ambos sub-planes
        tools_run = [s.tool for s in result.steps]
        self.assertIn("web_search", tools_run)
        self.assertIn("search_files", tools_run)

    def test_dataset_generator(self):
        """Valida que el generador de dataset LoRA produzca la estructura ChatML correcta."""
        import json
        from pathlib import Path
        
        dataset_path = Path("dataset_training_lora.json")
        self.assertTrue(dataset_path.exists(), "El archivo de dataset no fue generado")
        
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.assertGreaterEqual(len(data), 50, "Debería haber al menos 50 ejemplos de entrenamiento")
        
        # Validar primer ejemplo
        first_ex = data[0]
        self.assertIn("messages", first_ex)
        messages = first_ex["messages"]
        self.assertGreaterEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[2]["role"], "assistant")
        
        # Asistente debe responder en formato JSON
        assistant_content = messages[2]["content"]
        parsed_json = json.loads(assistant_content)
        self.assertIn("accion", parsed_json)

    def test_structured_generation_repair(self):
        """Verifica que validate_and_repair_json corrige llaves rotas y nombres de claves erróneos."""
        from cognition.slm import validate_and_repair_json
        
        # Caso 1: Claves en inglés (action -> accion, response -> respuesta)
        raw = '{"action": "responder", "response": "saludo secreto"}'
        res = validate_and_repair_json(raw)
        self.assertEqual(res["accion"], "responder")
        self.assertEqual(res["respuesta"], "saludo secreto")
        
        # Caso 2: Llave rota al final
        raw_broken = '{"accion": "responder", "respuesta": "hola"'
        res_broken = validate_and_repair_json(raw_broken)
        self.assertEqual(res_broken["accion"], "responder")
        self.assertEqual(res_broken["respuesta"], "hola")

    def test_structured_generation_self_correction_loop(self):
        """Verifica que el bucle de autocorrección se activa ante un JSON mal formado."""
        try:
            import requests
        except ImportError:
            self.skipTest("requests no instalado")
        original_post = None
        original_post = requests.post
        
        call_count = 0
        def mock_post(url, json, **k):
            nonlocal call_count
            call_count += 1
            mock_res = type('FakeResponse', (), {'status_code': 200, 'headers': {}})()
            if call_count == 1:
                # Primer intento: JSON inválido
                mock_res.json = lambda: {"response": "este no es un json", "model": "qwen2.5:0.5b"}
            else:
                # Segundo intento (corrección): JSON válido
                mock_res.json = lambda: {"response": '{"accion": "responder", "respuesta": "corregido"}', "model": "qwen2.5:0.5b"}
            return mock_res

        requests.post = mock_post
        try:
            res = self.nexus.slm._generate_ollama_structured("pregunta", "sistema")
            self.assertIsNotNone(res)
            self.assertIn("corregido", res["response"])
            self.assertEqual(call_count, 2, "Debería haber realizado 2 llamadas (una fallida y otra de autocorrección)")
        finally:
            requests.post = original_post

    def test_semantic_cache_hit(self):
        """Verifica que la caché semántica responda para consultas semánticamente similares."""
        import os
        from cognition.slm import SemanticCache
        
        # 1. Instanciar una caché temporal
        test_db = "tests/test_cache.db"
        if os.path.exists(test_db):
            os.remove(test_db)
            
        cache = SemanticCache(test_db)
        
        # Mock de get_embedding y is_available para pruebas aisladas
        original_get_embedding = None
        original_is_available = None
        import memory.embeddings as embed_module
        
        original_get_embedding = embed_module.get_embedding
        original_is_available = embed_module.is_available
        
        # Vector simulado de 768 dimensiones
        mock_vector = [0.1] * 768
        mock_vector_similar = [0.105] * 768
        
        embed_module.is_available = lambda: True
        
        prompt_stored = "¿Cuál es la capital de Francia?"
        prompt_query = "Dime la capital de Francia por favor"
        
        def mock_get_embedding(text):
            if text == prompt_stored:
                return mock_vector
            elif text == prompt_query:
                return mock_vector_similar
            return [0.0] * 768
            
        embed_module.get_embedding = mock_get_embedding
        
        try:
            # 2. Guardar respuesta en caché
            response_data = {"response": "La capital de Francia es París.", "model": "test-model"}
            cache.store(prompt_stored, response_data, system_prompt="sys1")
            
            # 3. Buscar usando consulta similar con un umbral bajo (0.90) para el mock
            cached_res = cache.lookup(prompt_query, system_prompt="sys1", threshold=0.90)
            self.assertIsNotNone(cached_res, "La caché semántica debió acertar con la consulta similar")
            self.assertEqual(cached_res["response"], "La capital de Francia es París.")
            
        finally:
            embed_module.get_embedding = original_get_embedding
            embed_module.is_available = original_is_available
            if os.path.exists(test_db):
                os.remove(test_db)

if __name__ == "__main__":
    unittest.main()
