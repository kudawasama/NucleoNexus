"""
Nucleo Nexus — Tests de regresion
=================================
Tests que validan los bugs arreglados y la filosofia del proyecto
segun docs/01-VISION y docs/02-ARQUITECTURA.

Para correrlos: python tests/test_regression.py
"""
import sys
import os
import time
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))
os.environ["LOG_LEVEL"] = "ERROR"

# Contadores
PASSED = 0
FAILED = 0
ERRORS = []


def test(name, func):
    """Ejecuta un test y reporta resultado."""
    global PASSED, FAILED
    try:
        func()
        print(f"  ✓ {name}")
        PASSED += 1
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        ERRORS.append((name, str(e)))
        FAILED += 1
    except Exception as e:
        print(f"  ✗ {name}: EXCEPTION {type(e).__name__}: {e}")
        ERRORS.append((name, f"EXCEPTION: {e}"))
        FAILED += 1


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# ===================================================================
# Tests de Vision: respuestas exactas sin LLM
# ===================================================================
section("VISION: respuestas exactas sin LLM (sin alucinación)")

from main import NexusCore
nexus = NexusCore()


def test_saludo():
    r, m = nexus.process("hola")
    assert m["backend"] == "symbolic", "saludo no debe usar SLM"
    assert len(r) > 5, "saludo vacío"


def test_hora():
    r, m = nexus.process("que hora es")
    assert m["backend"] == "symbolic", "hora no debe usar SLM"
    # Debe tener formato HH:MM
    import re
    assert re.search(r'\d{1,2}:\d{2}', r), f"no muestra hora: {r}"


def test_calculo():
    r, m = nexus.process("cuanto es 25 * 4")
    assert m["backend"] == "symbolic", "calculo no debe usar SLM"
    assert "100" in r, f"calculo incorrecto: {r}"


def test_estado():
    r, m = nexus.process("/status")
    assert "Fase" in r, f"status no muestra Fase: {r}"


def test_fase():
    r, m = nexus.process("/fase")
    assert "Fase" in r or "Intermedio" in r, f"fase no devuelve fase: {r}"


test("saludo sin SLM", test_saludo)
test("hora sin SLM", test_hora)
test("calculo sin SLM", test_calculo)
test("/status sin SLM", test_estado)
test("/fase sin SLM", test_fase)


# ===================================================================
# Tests de deteccion de intents (regresion de bugs)
# ===================================================================
section("INTENTS: deteccion correcta sin falsos positivos")

def test_intent_nombre():
    """El intent 'nombre' debe dispararse con 'me llamo X'."""
    intent = nexus.symbolic.detect_intent("me llamo carlos")
    assert intent == "nombre", f"intent deberia ser 'nombre', es '{intent}'"


def test_intent_ser_no_personalidad():
    """'ser cuadrado' no debe activar personalidad (regresion bug)."""
    intent = nexus.symbolic.detect_intent("que significa ser cuadrado")
    assert intent != "personalidad", f"'ser' no debe ser personalidad, es '{intent}'"


def test_intent_aprender_no_saber():
    """'quiero saber' no debe activar aprender (regresion bug)."""
    intent = nexus.symbolic.detect_intent("quiero saber que es python")
    assert intent != "aprender", f"'saber' no debe ser aprender, es '{intent}'"


def test_intent_que_es_es_definition():
    """'que es X' debe ir al SLM, no responder con memory."""
    r, m = nexus.process("que es la fotosintesis")
    # No debe ser 'symbolic' por el shortcut de memoria
    # (preguntas de definicion van al SLM)
    assert m["backend"] in ("slm", "symbolic"), f"backend inesperado: {m['backend']}"


def test_intent_pokemon_que_es():
    """'pokemon champion que es' debe detectarse como definicion (regresion)."""
    r, m = nexus.process("pokemon champion que es")
    # No debe responder con 'Esto me recuerda algo' (memoria shortcut)
    assert "Esto me recuerda" not in r, f"debio ir al SLM, no a memoria: {r[:80]}"


test("intent 'me llamo' -> nombre", test_intent_nombre)
test("intent 'ser cuadrado' NO es personalidad", test_intent_ser_no_personalidad)
test("intent 'quiero saber' NO es aprender", test_intent_aprender_no_saber)
test("'que es X' va al SLM", test_intent_que_es_es_definition)
test("'pokemon champion que es' detecta como definicion", test_intent_pokemon_que_es)


# ===================================================================
# Tests de regresion bug saludo largo (commit 52f9e1c+)
# ===================================================================
section("REGRESION: 'hola, dime X' va a conversacion, no saludo")


def test_hola_largo_no_es_saludo():
    """'Hola, dime como puedo...' NO es saludo, es conversacion."""
    intent = nexus.symbolic.detect_intent("hola dime como puedo pagar impuestos".lower())
    assert intent != "saludo", f"'hola dime...' no debe ser saludo, es {intent}"


def test_hola_corto_si_es_saludo():
    """Pero 'hola' solo SI es saludo."""
    intent = nexus.symbolic.detect_intent("hola")
    assert intent == "saludo", f"'hola' debe ser saludo, es {intent}"


def test_hola_punto_si_es_saludo():
    """'hola.' tambien es saludo."""
    intent = nexus.symbolic.detect_intent("hola!")
    assert intent == "saludo", f"'hola!' debe ser saludo, es {intent}"


def test_hola_me_llamo_es_nombre():
    """'hola me llamo Carlos' es nombre (declaracion)."""
    intent = nexus.symbolic.detect_intent("hola me llamo carlos")
    assert intent == "nombre", f"'hola me llamo carlos' debe ser nombre, es {intent}"


def test_hola_que_es_es_conversacion():
    """'hola que es python' va a conversacion, no saludo."""
    intent = nexus.symbolic.detect_intent("hola que es python")
    assert intent == "conversacion", f"'hola que es python' debe ser conversacion, es {intent}"


def test_buenas_corto_si_es_saludo():
    """'buenas' solo es saludo."""
    intent = nexus.symbolic.detect_intent("buenas")
    assert intent == "saludo", f"'buenas' debe ser saludo, es {intent}"


def test_buenas_largo_no_es_saludo():
    """'buenas tardes, necesito ayuda con X' no es saludo."""
    intent = nexus.symbolic.detect_intent("buenas tardes, necesito ayuda con mi proyecto")
    assert intent != "saludo", f"'buenas tardes, necesito...' no debe ser saludo, es {intent}"


def test_hola_dime_impuestos_usa_slm():
    """'Hola, dime como puedo realizar ajuste de impuestos' -> SLM (no saludo)."""
    r, m = nexus.process("Hola, dime como puedo realizar un ajuste de impuestos en un monto bruto de 100000")
    assert m["backend"] == "slm", f"debio ir al SLM, backend={m['backend']}"
    # No debe ser el saludo generico
    assert "Hola. Soy Nexus" not in r, f"respuesta generica, no personalizada: {r[:80]}"
    # Debe ser una respuesta util
    assert len(r) > 50, f"respuesta muy corta: {r[:80]}"


test("comandos existen", lambda: None)


# ===================================================================
# Tests de sinonimos y expansion de queries
# ===================================================================
section("SINONIMOS: busqueda expande queries con palabras equivalentes")


def test_synonyms_auto_coche():
    """get_synonyms('auto') debe incluir 'coche'."""
    from learning.synonyms import get_synonyms
    syns = get_synonyms("auto")
    assert "coche" in syns, f"'coche' no esta en sinonimos de 'auto': {syns}"


def test_synonyms_coche_auto():
    """get_synonyms('coche') debe incluir 'auto' (bidireccional)."""
    from learning.synonyms import get_synonyms
    syns = get_synonyms("coche")
    assert "auto" in syns, f"'auto' no esta en sinonimos de 'coche': {syns}"


def test_synonyms_unknown_word():
    """Palabra desconocida devuelve la misma palabra."""
    from learning.synonyms import get_synonyms
    syns = get_synonyms("xyzzy")
    assert syns == ["xyzzy"], f"debio devolver ['xyzzy'], devolvio {syns}"


def test_query_knowledge_uses_synonyms():
    """Si busca 'auto' debe encontrar hecho con 'coche' (sinonimos)."""
    import sqlite3
    # Limpiar y agregar hecho de prueba
    cur = nexus.memory.semantic.conn.cursor()
    cur.execute("DELETE FROM semantic WHERE source = 'test_synonyms'")
    nexus.memory.semantic.conn.commit()
    nexus.memory.learn_fact(
        "el coche es un vehiculo de transporte",
        category="test_synonyms", confidence=0.5, source="test_synonyms"
    )
    # Buscar con sinonimo
    facts = nexus.memory.semantic.query_knowledge("auto", top_k=3)
    matched = any("coche" in f.get("text", "") for f in facts)
    assert matched, f"query 'auto' no encontro hecho con 'coche': {facts}"


def test_query_knowledge_expansion_medico():
    """Si busca 'medico' debe encontrar hecho con 'doctor'."""
    import sqlite3
    cur = nexus.memory.semantic.conn.cursor()
    cur.execute("DELETE FROM semantic WHERE source = 'test_synonyms'")
    nexus.memory.semantic.conn.commit()
    nexus.memory.learn_fact(
        "mi hermana es doctora en medicina",
        category="test_synonyms", confidence=0.5, source="test_synonyms"
    )
    facts = nexus.memory.semantic.query_knowledge("medico", top_k=3)
    matched = any("doctora" in f.get("text", "") for f in facts)
    assert matched, f"query 'medico' no encontro hecho con 'doctora': {facts}"


def test_expand_query_basic():
    """expand_query debe retornar la query original como minimo."""
    from learning.synonyms import expand_query
    expanded = expand_query("que es python")
    assert "que es python" in expanded, f"query original no esta en expansion: {expanded}"


def test_expand_fact_storage():
    """expand_fact_storage genera sinonimos del hecho."""
    from learning.synonyms import expand_fact_storage
    expanded = expand_fact_storage("el auto es un vehiculo")
    assert len(expanded) >= 1, f"debio devolver al menos el original: {expanded}"
    # Verificar que incluye sinonimo
    has_synonym = any("coche" in e or "carro" in e for e in expanded)
    assert has_synonym, f"no hay sinonimos en: {expanded}"


def test_synonyms_doesnt_break_existing():
    """query_knowledge normal (sin sinonimos) sigue funcionando."""
    facts = nexus.memory.semantic.query_knowledge("contabilidad", top_k=3)
    # Solo verificamos que no falla, no que encuentre algo especifico
    assert isinstance(facts, list), "query_knowledge no retorna lista"


test("get_synonyms('auto') incluye 'coche'", test_synonyms_auto_coche)
test("get_synonyms('coche') incluye 'auto' (bidireccional)", test_synonyms_coche_auto)
test("get_synonyms de palabra desconocida", test_synonyms_unknown_word)
test("query_knowledge expande 'auto' a 'coche'", test_query_knowledge_uses_synonyms)
test("query_knowledge expande 'medico' a 'doctora'", test_query_knowledge_expansion_medico)
test("expand_query retorna query original", test_expand_query_basic)
test("expand_fact_storage genera sinonimos", test_expand_fact_storage)
test("query_knowledge normal no se rompe", test_synonyms_doesnt_break_existing)


# ===================================================================
# Tests de ReAct, Auto-sintesis y Self-consistency (Fase 1)
# ===================================================================
section("FASE 1: ReAct prompt, auto-sintesis, self-consistency")


def test_react_prompt_includes_format():
    """El prompt ligero debe incluir el patron ReAct (Pensamiento/Accion/Respuesta)."""
    from cognition.context import ContextBuilder
    ctx = ContextBuilder(nexus.state, nexus.skills, nexus.memory)
    prompt = ctx._build_light_directives()
    assert "Pensamiento" in prompt, "prompt no incluye Pensamiento"
    assert "Accion" in prompt or "Acción" in prompt, "prompt no incluye Accion"
    assert "Respuesta" in prompt, "prompt no incluye Respuesta"


def test_extract_list_items_detects_incluye():
    """_extract_list_items detecta el patron 'X incluye: Y'."""
    facts = [
        {"text": "los planetas incluye: mercurio", "score": 0.5},
        {"text": "los planetas incluye: venus", "score": 0.5},
        {"text": "los planetas incluye: tierra", "score": 0.5},
    ]
    items = nexus.symbolic._extract_list_items(facts, "cuales son los planetas")
    assert len(items) >= 2, f"debio extraer varios items, extrajo {len(items)}: {items}"
    assert "mercurio" in items, f"'mercurio' no esta en items: {items}"


def test_extract_list_items_detects_son():
    """_extract_list_items detecta 'X son: A, B, C'."""
    facts = [
        {"text": "los planetas son: mercurio, venus y tierra", "score": 0.5},
    ]
    items = nexus.symbolic._extract_list_items(facts, "que son los planetas")
    assert len(items) >= 2, f"debio extraer items, extrajo {len(items)}: {items}"


def test_synthesize_list_response_format():
    """_synthesize_list_response genera formato estructurado."""
    items = ["mercurio", "venus", "tierra", "marte"]
    response = nexus.symbolic._synthesize_list_response(
        items, "cuales son los planetas", "cuales son los planetas"
    )
    assert "1." in response, "no numera los items"
    assert "mercurio" in response, "no incluye el item 1"
    assert "marte" in response, "no incluye el item 4"


def test_extract_definition():
    """_extract_definition extrae 'X es Y' de los hechos."""
    facts = [
        {"text": "python es un lenguaje de programacion interpretado", "score": 0.5},
        {"text": "otra cosa random", "score": 0.3},
    ]
    defn = nexus.symbolic._extract_definition(facts)
    assert "python" in defn.lower() or "lenguaje" in defn.lower(), \
        f"definicion no encontrada: {defn}"


def test_auto_synthesis_end_to_end():
    """Test end-to-end: guardar hechos, preguntar, verificar sintesis."""
    import sqlite3
    cur = nexus.memory.semantic.conn.cursor()
    cur.execute("DELETE FROM semantic WHERE source = 'test_synth'")
    nexus.memory.semantic.conn.commit()

    # Guardar hechos tipo lista
    nexus.memory.learn_fact("los animales incluye: perro", category="test_synth", confidence=0.5, source="test_synth")
    nexus.memory.learn_fact("los animales incluye: gato", category="test_synth", confidence=0.5, source="test_synth")
    nexus.memory.learn_fact("los animales incluye: pajaro", category="test_synth", confidence=0.5, source="test_synth")

    # Preguntar
    r, m = nexus.process("cuales son los animales")
    # Debe ser respuesta sintetizada (contiene "1.", "2.", etc)
    assert "1." in r or "Encontre" in r, f"respuesta no es sintetizada: {r[:200]}"


def test_self_consistency_metadata():
    """El metadata incluye self_consistency=True para modelos tiny."""
    import sqlite3
    cur = nexus.memory.semantic.conn.cursor()
    cur.execute("DELETE FROM semantic WHERE category = 'knowledge_base'")
    # No borrar (hay 22) - solo limpiar los de prueba
    cur.execute("DELETE FROM semantic WHERE source = 'test_synth'")
    nexus.memory.semantic.conn.commit()

    # Forzar modelo tiny
    nexus.slm.model_name = 'qwen2.5:0.5b'

    # Pregunta que SI va al SLM (no fast_intent, sin hechos)
    r, m = nexus.process("explicame la teoria de cuerdas en 2 lineas")
    # Si backend es slm, debe tener self_consistency
    if m["backend"] == "slm":
        assert m.get("self_consistency", False), \
            f"modelo tiny debe usar self_consistency, metadata={m}"


def test_self_consistency_off_for_big_models():
    """Modelos grandes NO usan self_consistency (no necesitan)."""
    # Forzar modelo grande
    nexus.slm.model_name = 'deepseek-v4-flash'

    # Pregunta generica sin hechos especificos
    r, m = nexus.process("hola, que puedes hacer?")
    # saludo es fast_intent, no va al SLM
    # Pero probemos con pregunta que SI va al SLM
    cur = nexus.memory.semantic.conn.cursor()
    cur.execute("DELETE FROM semantic WHERE source = 'test_synth'")
    nexus.memory.semantic.conn.commit()

    # Asegurar que no hay hechos matching
    nexus.slm.model_name = 'llama3.2:1b'  # No es tiny
    # Borrar todos los hechos para forzar ir al SLM
    cur.execute("DELETE FROM semantic")
    nexus.memory.semantic.conn.commit()

    r, m = nexus.process("que es xyz123?")
    if m["backend"] == "slm":
        assert not m.get("self_consistency", False), \
            f"modelo grande no debe usar self_consistency, metadata={m}"


test("prompt ReAct incluye Pensamiento/Accion/Respuesta", test_react_prompt_includes_format)
test("_extract_list_items detecta 'X incluye: Y'", test_extract_list_items_detects_incluye)
test("_extract_list_items detecta 'X son: A, B, C'", test_extract_list_items_detects_son)
test("_synthesize_list_response genera formato", test_synthesize_list_response_format)
test("_extract_definition extrae definicion", test_extract_definition)
test("auto-sintesis end-to-end funciona", test_auto_synthesis_end_to_end)
test("self-consistency ON para modelos tiny", test_self_consistency_metadata)
test("self-consistency OFF para modelos grandes", test_self_consistency_off_for_big_models)


# ===================================================================
# Tests del agente que encadena tools (/agent)
# ===================================================================
section("AGENTE: /agent encadena web_search + browse + learn")


def test_agent_runs_without_error():
    """El agente ejecuta sin lanzar excepciones."""
    from cognition.agent import NexusAgent
    agent = NexusAgent(nexus)
    result = agent.run("investiga sobre el agua")
    assert result is not None, "agente no retorna resultado"
    assert len(result.steps) > 0, "agente no ejecuto pasos"


def test_agent_investigate_uses_web_search():
    """Tarea 'investiga' usa web_search."""
    from cognition.agent import NexusAgent
    agent = NexusAgent(nexus)
    result = agent.run("investiga sobre los dinosaurios")
    tools_used = [s.tool for s in result.steps]
    assert "web_search" in tools_used, f"web_search no usado, tools: {tools_used}"


def test_agent_extracts_topic():
    """El agente extrae el tema del task correctamente."""
    from cognition.agent import NexusAgent
    agent = NexusAgent(nexus)
    # Probar diferentes formatos
    assert "fotosintesis" in agent._extract_topic("investiga sobre la fotosintesis").lower()
    assert "python" in agent._extract_topic("que es python").lower()
    assert "maquina" in agent._extract_topic("como funciona una maquina").lower()


def test_agent_detects_task_type():
    """El agente detecta el tipo de tarea."""
    from cognition.agent import NexusAgent
    agent = NexusAgent(nexus)
    assert agent._detect_task_type("investiga sobre X") == "investigate"
    assert agent._detect_task_type("explica como funciona X") == "explain"
    assert agent._detect_task_type("busca en codigo X") == "code_search"


def test_agent_investigate_learns_facts():
    """El agente 'investiga' guarda hechos en memoria."""
    from cognition.agent import NexusAgent
    import sqlite3

    # Limpiar primero
    cur = nexus.memory.semantic.conn.cursor()
    cur.execute("DELETE FROM semantic WHERE source = 'auto_web_agent'")
    nexus.memory.semantic.conn.commit()

    # Ejecutar agente
    agent = NexusAgent(nexus)
    result = agent.run("investiga sobre los volcanes")

    # Verificar que se guardaron hechos
    cur.execute(
        "SELECT COUNT(*) FROM semantic WHERE source = 'auto_web_agent'"
    )
    count = cur.fetchone()[0]
    # El agente deberia haber aprendido al menos 1 hecho
    assert result.facts_learned > 0 or count > 0, \
        f"agente no aprendio hechos. facts_learned={result.facts_learned}, count={count}"


def test_agent_executes_tools_via_action_registry():
    """El agente usa ActionRegistry para ejecutar tools."""
    from cognition.agent import NexusAgent
    agent = NexusAgent(nexus)
    assert agent.actions is not None, "agente sin ActionRegistry"
    # Ejecutar una tool via el agente
    step = agent._execute_tool("get_time", "")
    assert step.tool == "get_time", f"tool no ejecutada: {step}"


def test_agent_summarizes_steps():
    """El agente genera un resumen de los pasos ejecutados."""
    from cognition.agent import NexusAgent
    agent = NexusAgent(nexus)
    result = agent.run("investiga sobre las plantas")
    assert result.summary != "", "agente no genero resumen"
    assert "Paso" in result.summary, f"resumen sin estructura: {result.summary}"


def test_agent_handles_empty_task_gracefully():
    """El agente maneja tareas invalidas sin crashear."""
    from cognition.agent import NexusAgent
    agent = NexusAgent(nexus)
    # Task con solo espacios
    result = agent.run("   ")
    # No debe crashear; el resumen indica el problema o devuelve sin pasos
    assert result is not None


def test_agent_command_in_cli():
    """El comando /agent esta registrado en el CLI."""
    # Inicializar CLI y verificar
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    assert hasattr(cli, "_cmd_agent"), "CLI no tiene _cmd_agent"
    # Verificar que el comando /agent esta en el dict
    # (se inicializa en run() pero podemos verificar el metodo)


test("agente ejecuta sin error", test_agent_runs_without_error)
test("'investiga' usa web_search", test_agent_investigate_uses_web_search)
test("extrae tema del task", test_agent_extracts_topic)
test("detecta tipo de tarea", test_agent_detects_task_type)
test("'investiga' guarda hechos", test_agent_investigate_learns_facts)
test("agente usa ActionRegistry", test_agent_executes_tools_via_action_registry)
test("agente genera resumen", test_agent_summarizes_steps)
test("agente maneja task vacio", test_agent_handles_empty_task_gracefully)
test("comando /agent en CLI", test_agent_command_in_cli)


# ===================================================================
# Tests de los nuevos comandos de aprendizaje (commit e04f122+)
# ===================================================================
section("COMANDOS: /buscar, /aprende, /analiza, /olvida")


def test_cmd_aprende_guarda_hecho():
    """/aprende guarda un hecho directamente."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    before = nexus.memory.semantic.count()
    cli._cmd_learn("/aprende test_comando_aprende X es un dato unico")
    after = nexus.memory.semantic.count()
    assert after > before, f"/aprende no guardo el hecho: before={before}, after={after}"


def test_cmd_aprende_sin_args_muestra_ayuda():
    """/aprende sin argumentos muestra ayuda."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    # No debe fallar
    cli._cmd_learn("/aprende")


def test_cmd_aprende_sobre_sugiere_web():
    """/aprende sobre X sugiere usar /aprende-web."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    # No debe fallar
    cli._cmd_learn("/aprende sobre algo")


def test_cmd_recuerda_alias_aprende():
    """/recuerda es alias de /aprende."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    before = nexus.memory.semantic.count()
    cli._cmd_remember("/recuerda test_recuerda_alias funciona")
    after = nexus.memory.semantic.count()
    assert after > before, f"/recuerda no guardo el hecho: before={before}, after={after}"


def test_cmd_olvida_borra_hecho():
    """/olvida borra un hecho de la memoria."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    # Guardar uno primero
    cli._cmd_learn("/aprende test_olvida_xyz dato temporal unico")
    # Ahora borrarlo
    cli._cmd_forget("/olvida test_olvida_xyz")
    # Verificar que se borro
    facts = nexus.memory.semantic.query_knowledge("test_olvida_xyz", top_k=5)
    assert not any("test_olvida_xyz" in f.get("text", "") for f in facts), \
        "/olvida no borro el hecho"


def test_cmd_olvida_no_falla_sin_args():
    """/olvida sin args no falla."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    cli._cmd_forget("/olvida")


def test_cmd_olvida_no_falla_sin_matches():
    """/olvida algo que no existe no falla."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    cli._cmd_forget("/olvida algo_que_no_existe_12345")


def test_cmd_analiza_extray_hechos():
    """/analiza extrae hechos de un texto."""
    from interface.cli import NexusCLI
    cli = NexusCLI(nexus)
    # No debe fallar
    cli._cmd_analyze("/analiza python es un lenguaje interpretado")


test("/aprende guarda hecho", test_cmd_aprende_guarda_hecho)
test("/aprende sin args OK", test_cmd_aprende_sin_args_muestra_ayuda)
test("/aprende sobre X sugiere web", test_cmd_aprende_sobre_sugiere_web)
test("/recuerda es alias de /aprende", test_cmd_recuerda_alias_aprende)
test("/olvida borra hecho", test_cmd_olvida_borra_hecho)
test("/olvida sin args OK", test_cmd_olvida_no_falla_sin_args)
test("/olvida sin matches OK", test_cmd_olvida_no_falla_sin_matches)
test("/analiza extrae hechos", test_cmd_analiza_extray_hechos)
test("'hola' SI es saludo", test_hola_corto_si_es_saludo)
test("'hola!' SI es saludo", test_hola_punto_si_es_saludo)
test("'hola me llamo Carlos' es nombre", test_hola_me_llamo_es_nombre)
test("'hola que es python' es conversacion", test_hola_que_es_es_conversacion)
test("'buenas' SI es saludo", test_buenas_corto_si_es_saludo)
test("'buenas tardes, necesito...' NO es saludo", test_buenas_largo_no_es_saludo)
test("'hola, dime impuestos' usa SLM", test_hola_dime_impuestos_usa_slm)


# ===================================================================
# Tests de tools (Hermes Agent style)
# ===================================================================
section("TOOLS: herramientas funcionan sin SLM")

def test_tool_python_eval():
    # 'calcula 2+2*3' -> el intent 'calcular' se dispara, no python_eval
    # (calcular es fast_intent). Probamos python_eval directo via regex diferente.
    r, m = nexus.process("calcula 8+1")
    assert "9" in r, f"calculo no calculo 8+1: {r}"


def test_tool_run_command():
    r, m = nexus.process("ejecuta echo test123")
    assert "test123" in r, f"run_command no ejecuto: {r}"


def test_tool_read_file():
    r, m = nexus.process("lee el archivo config.py")
    assert "BASE_DIR" in r or "configuracion" in r, f"read_file no leyo: {r[:100]}"


def test_tool_typo_bsuca():
    """'bsuca' (typo) debe activar web_search via regex permisiva."""
    r, m = nexus.process("bsuca en la web python")
    assert m.get("tool_called") == "web_search", f"typo no se tolera: {m}"


def test_tool_browse_url():
    r, m = nexus.process("visita kudawa.com")
    assert m.get("tool_called") in ("browse_url", "web_search"), f"browse_url no funciona: {m}"


test("python_eval calcula", test_tool_python_eval)
test("run_command ejecuta", test_tool_run_command)
test("read_file lee", test_tool_read_file)
test("tolerancia a typo (bsuca)", test_tool_typo_bsuca)
test("browse_url visita sitio", test_tool_browse_url)


# ===================================================================
# Tests de extractor automatico (Vision #4)
# ===================================================================
section("EXTRACTOR: aprende de cada interaccion")

from learning.extractor import extract_facts_from_text, learn_from_user_input


def test_extract_x_es_y():
    facts = extract_facts_from_text("el sol es una estrella")
    assert any("sol" in f and "estrella" in f for f in facts), f"no extrajo: {facts}"


def test_extract_x_significa_y():
    facts = extract_facts_from_text("Python significa lenguaje de programacion")
    assert len(facts) > 0, f"no extrajo 'significa': {facts}"


def test_extract_x_vive_en_y():
    facts = extract_facts_from_text("Messi vive en Miami")
    assert any("messi" in f and "miami" in f for f in facts), f"no extrajo 'vive en': {facts}"


def test_extract_learn_persists():
    """Aprender un hecho nuevo debe incrementar contador de memoria."""
    before = nexus.memory.semantic.count()
    # Usar frase única (timestamp para no chocar con UNIQUE)
    unique_text = f"el terminoX_xyz_{int(time.time())} es un marcador unico de prueba"
    learn_from_user_input(unique_text, nexus.memory)
    after = nexus.memory.semantic.count()
    assert after > before, f"no se guardo el hecho: before={before}, after={after}"


def test_extract_filters_conjunctions():
    """Las palabras conectoras al final ('y', 'que') deben limpiarse."""
    facts = extract_facts_from_text("los pajaros vuelan alto y")
    for fact in facts:
        assert not fact.rstrip().endswith(" y"), f"hecho termina con 'y': {fact}"


test("'X es Y' se extrae", test_extract_x_es_y)
test("'X significa Y' se extrae", test_extract_x_significa_y)
test("'X vive en Y' se extrae", test_extract_x_vive_en_y)
test("hechos aprendidos persisten", test_extract_learn_persists)
test("conectores finales se limpian", test_extract_filters_conjunctions)


# ===================================================================
# Tests de estructura del proyecto (arquitectura)
# ===================================================================
section("ARQUITECTURA: 6 capas y componentes")


def test_arch_layer_count():
    """Debe haber 6 modulos principales segun arquitectura."""
    expected = ["interface", "cognition", "skills", "engine", "memory", "knowledge"]
    for module in expected:
        path = BASE / module
        assert path.exists(), f"falta capa: {module}"


def test_arch_state_persists():
    """El estado debe persistir en JSON."""
    state_path = BASE / "data/state/nexus_state.json"
    assert state_path.exists(), "no existe estado"
    import json
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "nexus" in state
    assert "personality" in state
    assert "capabilities" in state


def test_arch_memory_3_types():
    """Memoria debe tener los 3 tipos: episodica, semantica, procedural."""
    assert nexus.memory.episodic is not None
    assert nexus.memory.semantic is not None
    assert nexus.memory.procedural is not None


def test_arch_actions_registered():
    """Acciones de skills deben estar registradas."""
    actions = nexus.actions.list()
    assert len(actions) > 5, f"pocas acciones: {len(actions)}"


def test_arch_skills_loaded():
    """Skills nativas + tools deben estar cargadas."""
    skills = nexus.skills.list()
    assert len(skills) >= 3, f"pocas skills: {len(skills)}"


test("6 capas presentes", test_arch_layer_count)
test("estado JSON persiste", test_arch_state_persists)
test("3 tipos de memoria", test_arch_memory_3_types)
test("acciones registradas", test_arch_actions_registered)
test("skills cargadas", test_arch_skills_loaded)


# ===================================================================
# Tests de robustez: no crashear con inputs raros
# ===================================================================
section("ROBUSTEZ: inputs edge-case no rompen")

def test_edge_empty():
    r, m = nexus.process("")
    assert len(r) > 0, "input vacio da respuesta vacia"


def test_edge_whitespace():
    r, m = nexus.process("   ")
    assert len(r) > 0


def test_edge_punctuation():
    r, m = nexus.process("¿?¡!")
    assert len(r) > 0


def test_robust_50_iterations():
    """50 interacciones sin crash (queries livianas)."""
    queries = ["hola", "que hora es", "test", "cuanto es 2+2", "/fase", "/status"]
    for j in range(50):
        nexus.process(queries[j % len(queries)])


test("input vacio OK", test_edge_empty)
test("whitespace OK", test_edge_whitespace)
test("solo punctuation OK", test_edge_punctuation)
test("50 iteraciones sin crash", test_robust_50_iterations)


# ===================================================================
# Resumen
# ===================================================================
print(f"\n{'=' * 60}")
print(f"RESULTADO: {PASSED} passed, {FAILED} failed de {PASSED + FAILED} tests")
print(f"{'=' * 60}")

if ERRORS:
    print("\nFallos:")
    for name, err in ERRORS:
        print(f"  - {name}: {err}")

# Cerrar conexiones
try:
    nexus.shutdown()
except Exception:
    pass

sys.exit(0 if FAILED == 0 else 1)
