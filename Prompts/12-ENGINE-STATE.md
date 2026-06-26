# 12 — Engine: State + Actions (`engine/`)

> **El contrato entre la IA y el sistema.**
> La IA orquesta, el engine ejecuta y persiste.

---

## A) Motor de Estado (`engine/state.py`)

> *"Gestiona todo el estado del sistema en JSON. La IA NO calcula nada — solo lee y escribe estado aquí. Totalmente separado de la capa cognitiva."*

### Principios

1. **La IA nunca calcula estado, solo lo consume.**
2. **Todo estado se persiste en JSON para auditoría.**
3. **El motor expone getters/setters con validación.**
4. **Soporta inyección directa para function calling.**

### Estructura del estado

```json
{
  "nexus": {
    "version": "0.1.0+build.42",
    "commit": 19,
    "phase": "Proto",
    "total_interactions": 42,
    "total_learned_facts": 128,
    "total_skills": 15,
    "confidence_level": 0.125,
    "started_at": "2026-06-15T10:00:00",
    "last_interaction": "2026-06-19T13:25:00"
  },
  "capabilities": {
    "backend": "hybrid",
    "slm_loaded": true,
    "model_name": "hermes3:3b",
    "embeddings_available": false
  },
  "performance": {
    "responses_given": 42,
    "successful_responses": 38,
    "avg_response_time_ms": 1240,
    "tokens_consumed": 54200
  },
  "personality": {
    "tone": "analytical",
    "formality": 0.5,
    "curiosity": 0.7,
    "creativity": 0.4
  },
  "model_state": {
    "backend": "ollama",
    "model_name": "hermes3:3b"
  }
}
```

### API principal

```python
# Acceso seguro a claves anidadas
state.get("nexus", "phase")                  # → "Proto"
state.get("inexistente", default=None)       # → None
state.get("inexistente", "sub", default=0)   # → 0

# Escritura
state.set("nexus", "phase", value="Intermedio")
state.set("personality", "tone", value="friendly")

# Snapshot completo (para inyección de contexto)
state.get_snapshot()                         # → dict completo

# Bloque de contexto (formato markdown)
state.get_context_block()                    # → "=== ESTADO DE NEXUS ===\n..."
```

### Reglas de validación

- **Tipos permitidos** para valores: `str`, `int`, `float`, `bool`, `list`, `dict`, `None`.
- **Paths anidados**: usa `/` o tuplas — ej: `state.get(("nexus", "phase"))`.
- **Persistencia**: cada `set()` con flag `persist=True` (default) escribe a `data/state/nexus_state.json` con escritura atómica (`.tmp` + rename).

---

## B) Sistema de Acciones (`engine/actions.py`)

> *"Las acciones son funciones que la IA puede 'llamar'. El motor de estado + las skills resuelven la lógica. La IA solo orquesta — nunca calcula."*

### Clases

```python
@dataclass
class Action:
    name: str                          # nombre de la acción
    description: str                   # para function calling
    handler: callable                  # función Python
    params: dict                       # spec de parámetros
    skill: str = None                  # skill dueña (si aplica)

class ActionRegistry:
    actions: dict[str, Action]         # name → Action

    def register(self, action: Action)
    def execute(self, name: str, **kwargs) -> dict
    def to_function_spec(self) -> list[dict]  # OpenAI/Ollama format
```

### `execute(name, **kwargs)` — Ejecución

```python
result = actions.execute("weather", city="Santiago")
# → {"success": true, "result": {...}, "metadata": {...}}
```

**Algoritmo:**
1. Buscar acción por nombre
2. Validar parámetros (filtra los que el handler no acepta)
3. Llamar al handler
4. Capturar excepciones
5. Auditar la llamada (log)

**Validación de parámetros:**
- Usa `inspect.signature(handler)` para ver qué parámetros acepta
- Solo pasa los kwargs que el handler declara
- Si falta un parámetro requerido → `TypeError` → retorna `{"success": false, "error": "..."}`

### `to_function_spec()` — Spec para function calling

Devuelve el spec compatible con OpenAI/Ollama function calling:

```json
[
  {
    "name": "web_search",
    "description": "Busca en la web usando DuckDuckGo Lite",
    "parameters": {
      "type": "object",
      "properties": {
        "query": { "type": "string", "description": "Término de búsqueda" }
      },
      "required": ["query"]
    }
  },
  ...
]
```

---

## Filosofía

> *"El motor de estado + las skills resuelven la lógica. La IA solo orquesta — nunca calcula."*

El **engine** es el límite arquitectónico entre:
- Lo que la IA decide (qué tool invocar, con qué parámetros)
- Lo que el sistema hace (calcular, persistir, ejecutar)

La IA **nunca** modifica el estado directamente — solo pide cambios vía acciones.
