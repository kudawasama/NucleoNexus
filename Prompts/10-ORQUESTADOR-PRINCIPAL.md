# 10 — Orquestador Principal (`main.py`)

> **NexusCore.process()** — El flujo principal que coordina todos los componentes.
> Inicializa todo, procesa cada mensaje, aprende, sincroniza.

---

## Arquitectura (diagrama del módulo)

```
+---------------------------------------------------------------+
|                     INTERFAZ                                   |
|             (CLI / API / Web)                                 |
+---------------------------------------------------------------+
|                   CAPA COGNITIVA                               |
|  +----------+  +----------+  +-----------------------------+  |
|  | Simbolico |  |   SLM    |  | Inyector de               |
|  | (default) |  | (Qwen,   |  | Contexto                   |
|  |           |  |  Phi...) |  | Dinamico                   |
|  +----------+  +----------+  +-----------------------------+ |
+---------------------------------------------------------------+
|                  SKILLS / ACCIONES                             |
|      (Function Calling . Registry . Builtins)                 |
+---------------------------------------------------------------+
|                MOTOR DE ESTADO                                 |
|   (JSON persistente . Metricas . Fases)                      |
+---------------------------------------------------------------+
|                MEMORIA PERSISTENTE                             |
|  +----------+  +----------+  +-----------------------------+  |
|  |Epi-sodica|  |Semantica |  |Procedimental               |
|  | (Que     |  | (Hechos) |  | (Como hacer)               |
|  |  paso)   |  |          |  |                             |
|  +----------+  +----------+  +-----------------------------+  |
|              SQLite + TF-IDF                                   |
+---------------------------------------------------------------+
|              SISTEMA (archivos, DB)                            |
+---------------------------------------------------------------+
```

---

## `NexusCore.process(user_input, on_status=None)` — Flujo principal

```python
def process(self, user_input: str, on_status: callable = None) -> tuple:
    """
    Procesa la entrada del usuario y genera respuesta.

    Modos de operacion:
    - symbolic:   solo motor simbolico (sin modelo, sin internet)
    - slm:        solo SLM local (modelo responde todo)
    - hybrid:     intents rapidas en simbolico, general en SLM
    """
```

### Pasos del proceso (en orden)

```
[1] on_status("🔍 Analizando mensaje...")
    ↓
[2] _get_response(user_input)   ←  elige modo, consulta symbolic/SLM
    ↓
[3] on_status("📚 Aprendiendo de la interacción...")
    ↓
[4] learn_from_all(user_input, memory, source="usuario")
    ↓
[5] learn_from_all(response, memory, source="respuesta")
    ↓
[6] handle_feedback(user_input, memory)
    ↓
[7] si metadata["web_results"]  →  _learn_from_web_search(...)
    ↓
[8] reinforce_from_feedback(user_input, memory)
    ↓
[9] memory.remember("user", user_input, context={"backend": "main"})
    memory.remember("nexus", response, context={"backend": "main"})
    ↓
[10] state.record_interaction(success=True)
     state.evolve_phase()
    ↓
[11] utils.git_auto.auto_commit_push(...)
```

**Status callbacks** (mensajes en vivo para la UI):
- `🔍 Analizando mensaje...`
- `📚 Aprendiendo de la interacción...`

---

## `__init__()` — Inicialización

Inicializa los componentes en este orden:

1. `StateEngine(data_dir)` — motor de estado
2. `SkillRegistry(skills_dir)` — carga skills desde `skills/builtins/`
3. `NexusMemory(db_path, state)` — memoria unificada
4. `ActionRegistry()` + `register_skill_actions()` — actions
5. `SymbolicEngine(state, memory, skills, actions)` — motor simbólico
6. `SLMBackend(config)` — backend LLM
7. `ContextBuilder(state, skills, memory)` — inyector de contexto
8. `NexusAgent(self)` — agente orquestador (multi-tool)
9. `auto_pull()` — sincroniza con GitHub al arrancar

---

## `_get_response(user_input, on_status)` — Selección de backend

Decide qué backend usar según `ENGINE['mode']`:

| Modo | Comportamiento |
|------|----------------|
| `symbolic` | Solo motor simbólico. Sin modelo, sin internet. |
| `slm` | Solo SLM local (con fallback a simbólico si falla). |
| `hybrid` | Intents rápidos en simbólico, general en SLM. |

**Detección de intents rápidos (modo hybrid):**
- Saludos, hora, fase → simbólico directo
- Comandos `[[accion:...]]` → simbólico
- Todo lo demás → SLM

**Retorno:** `(response_str, metadata_dict)` donde metadata incluye:
```python
{
    "backend": "symbolic" | "slm",
    "interactions": int,
    "facts_learned": int,
    "facts_extracted": int,
    "web_results": [...],   # si hubo web_search
    "tokens": {...},        # si fue SLM
}
```

---

## `_strip_react(text)` — Limpieza de formato ReAct

Cuando el SLM responde en formato ReAct, **extrae solo la respuesta del usuario**:

**Patrones de respuesta ReAct:**
```
Pensamiento: ...
Acción: ...
Observación: ...
Respuesta: ...   ← esto es lo que extrae
```

**Marcadores aceptados** (orden de prioridad):
1. `"Respuesta:"`
2. `"RESPUESTA:"`
3. `"respuesta:"`
4. `"**Respuesta:**"`

**Algoritmo:**
1. Buscar el primer marcador en el texto
2. Si lo encuentra → tomar todo lo que sigue
3. Limpiar marcadores residuales (líneas `---...`)
4. Si no encuentra ningún marcador → devolver texto original (max 300 chars)

---

## Filosofía

> *"Nucleo Nexus — Punto de Entrada. Inicializa todos los componentes y lanza la interfaz."*

`main.py` es el **director de orquesta** — no calcula nada por sí mismo, pero coordina que cada componente (memoria, skills, SLM, git) haga su parte en el momento correcto.
