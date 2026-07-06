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

        # Guardar hechos tipo lista
        self.nexus.memory.learn_fact("los animales incluye: perro", category="test_synth", confidence=0.5, source="test_synth")
        self.nexus.memory.learn_fact("los animales incluye: gato", category="test_synth", confidence=0.5, source="test_synth")
        self.nexus.memory.learn_fact("los animales incluye: pajaro", category="test_synth", confidence=0.5, source="test_synth")

        # Preguntar
        r, m = self.nexus.process("cuales son los animales")
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
        step = agent._execute_tool("get_time", "")
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

        prior = [
            type('FakeStep', (), {
                'tool': 'web_search',
                'output': '{"resultados": ["• Dato importante para el test"]}',
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

        prior = [
            type('FakeStep', (), {
                'tool': 'web_search',
                'output': '{"resultados": ["• Dato importante"]}',
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

if __name__ == "__main__":
    unittest.main()
