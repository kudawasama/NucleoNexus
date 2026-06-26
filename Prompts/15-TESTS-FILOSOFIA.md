# 15 — Tests de Regresión y Filosofía (`tests/test_regression.py`)

> **Tests que validan los bugs arreglados y la filosofía del proyecto.**
> Para correrlos: `python tests/test_regression.py`

---

## Propósito

> *"Tests que validan los bugs arreglados y la filosofía del proyecto según docs/01-VISION y docs/02-ARQUITECTURA."*

Dos funciones:
1. **Anti-regresión**: cada bug arreglado tiene un test que verifica que NO vuelva a aparecer.
2. **Guarda-filosofía**: verifican que los principios de diseño (inteligencia por arquitectura, no pre-cargar conocimiento, etc.) se mantengan.

---

## Categorías de tests (resumen)

### 1. Tests de memoria

- `test_semantic_learn_reinforce()` — aprender un hecho dos veces → confianza sube.
- `test_query_knowledge_filters_stopwords()` — palabras vacías (que, el, es) NO matchean.
- `test_synonyms_expand_query()` — "auto" encuentra "coche" en memoria.
- `test_episodic_recall_orders_by_similarity()` — recuerdos más similares primero.

### 2. Tests del motor simbólico

- `test_phase_progression()` — después de N interacciones, la fase avanza.
- `test_confidence_grows_with_success()` — la confianza sube solo en interacciones exitosas.
- `test_intent_detection_saludo()` — "hola" → respuesta de saludo.
- `test_intent_detection_pregunta()` — "qué es X" → respuesta de presentación.

### 3. Tests del agente orquestador

- `test_agent_detect_investigate()` — keyword "investiga" → plan investigate.
- `test_agent_detect_explain()` — keyword "explica" → plan explain.
- `test_agent_extract_topic()` — quita prefijos ("investiga sobre", "qué es").
- `test_agent_url_filter()` — URLs bloqueadas (duckduckgo, wikipedia) → filtradas.

### 4. Tests del SLM

- `test_slm_json_format()` — si `structured=True`, la respuesta es JSON válido.
- `test_slm_handles_invalid_json()` — JSON inválido → `None`, no excepción.
- `test_few_shot_examples_count()` — siempre hay al menos 7 ejemplos.

### 5. Tests de skills

- `test_calc_skill_basic()` — `calc("2+2")` → `4`.
- `test_currency_skill_clp()` — convierte USD a CLP.
- `test_moon_skill_returns_phase()` — devuelve una fase válida.
- `test_files_skill_security()` — paths fuera del proyecto → rechazados.

### 6. Tests de extracción de hechos

- `test_extract_user_name()` — "me llamo X" → "El usuario se llama X".
- `test_extract_negation_preserved()` — "nunca como carne" → hecho negativo se guarda.
- `test_feedback_detect_positive()` — "correcto" → reforzar.
- `test_feedback_detect_negative()` — "incorrecto" → rechazar.

### 7. Tests de configuración y versión

- `test_config_has_required_keys()` — todas las secciones existen.
- `test_version_format()` — sigue el patrón `X.Y.Z+build.N`.

### 8. Tests de filosofía

- `test_no_preloaded_knowledge()` — Nexus NO carga conocimiento hardcodeado.
- `test_slm_optional()` — funciona sin SLM (modo symbolic puro).
- `test_state_persists_across_restarts()` — el estado sobrevive a reinicios.

---

## Cómo correrlos

```bash
# Todos los tests
python tests/test_regression.py

# Un test específico
python -m unittest tests.test_regression.TestMemory.test_semantic_learn_reinforce

# Verbose
python tests/test_regression.py -v
```

---

## Filosofía detrás de los tests

> *"Anti-regresión + guarda-filosofía"*

Cada vez que se arregla un bug:
1. Se escribe un test que reproduce el bug original.
2. El test verifica que el fix funciona.
3. Queda en el repo para siempre → si alguien revierte el fix, el test falla.

Cada vez que se respeta un principio de diseño:
- Se escribe un test que lo valida.
- Ejemplo: `test_no_preloaded_knowledge()` asegura que el proyecto **nunca** pre-cargue hechos hardcodeados en el código (toda la base de conocimiento se construye desde interacciones).

---

## Patrones comunes en los tests

```python
import unittest
from memory.semantic import SemanticMemory

class TestSemanticMemory(unittest.TestCase):
    def setUp(self):
        """Prepara estado limpio para cada test."""
        self.mem = SemanticMemory(db_path=":memory:")
    
    def tearDown(self):
        """Limpia después de cada test."""
        self.mem.close()
    
    def test_learn_reinforces_confidence(self):
        """Aprender el mismo hecho dos veces debe subir la confianza."""
        self.mem.learn_fact("Chile está en Sudamérica", confidence=0.5)
        self.mem.learn_fact("Chile está en Sudamérica", confidence=0.5)
        # La confianza debe haber subido
        facts = self.mem.query_knowledge("Chile")
        self.assertGreater(facts[0]["confidence"], 0.5)
```

---

## Reglas no escritas

- **Tests no dependen de Ollama** — corren sin GPU, sin internet, sin SLM.
- **Tests usan `:memory:` SQLite** — no tocan archivos reales.
- **Tests son rápidos** — todo el suite debe correr en < 5 segundos.
- **Tests son legibles** — el nombre del test describe el comportamiento esperado.
