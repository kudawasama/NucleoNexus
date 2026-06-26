# 02 — Agente SLM (`cognition/slm.py`)

> **SLMBackend** — Backend de generación con Ollama (Qwen 0.5B, hermes3:3b, deepseek, etc).
> Define el **system prompt que fuerza salida JSON** y el esquema de respuesta.

---

## System prompt (inyectado en Ollama cuando `structured=True`)

```
Responde SOLO con JSON valido. El campo 'accion' determina
que hace Nexus con tu respuesta:
- "responder": solo responde al usuario (mas comun)
- "buscar_memoria": busca un tema en la base de conocimiento
- "calcular": evalua una expresion matematica
- "usar_herramienta": ejecuta una herramienta del sistema
  (web_search, read_file, write_file, search_files,
   run_command, python_eval)

Esquema:
{"respuesta": "texto al usuario",
 "accion": "responder|buscar_memoria|calcular|usar_herramienta",
 "tema": "tema a buscar (si accion=buscar_memoria)",
 "expresion": "2+2 (si accion=calcular)",
 "herramienta": "web_search (si accion=usar_herramienta)",
 "parametros": {"query": "termino busqueda"}}
```

> Si se pasa `system_prompt` extra, se concatena **antes** de esta instrucción JSON.

---

## Configuración Ollama

| Parámetro | Valor |
|-----------|-------|
| Endpoint | `POST http://localhost:11434/api/generate` |
| `format` | `"json"` (fuerza JSON válido) |
| `stream` | `false` |
| `num_predict` | `self.max_tokens` (config) |
| `temperature` | `self.temperature` (config) |

Si la respuesta NO es JSON válido → se descarta y devuelve `None`.

---

## Esquema de respuesta del SLM (lo que el código espera recibir)

```json
{
  "razonamiento": "...",
  "accion": "responder|web_search|calcular|buscar_memoria|usar_herramienta|hora_actual|pdf_rename",
  "respuesta": "texto final al usuario",
  "query": "...",
  "expresion": "...",
  "tema": "...",
  "herramienta": "...",
  "parametros": { "...": "..." },
  "path": "...",
  "dry_run": true|false
}
```

> Ver [05-APRENDIZAJE-FEW-SHOT.md](./05-APRENDIZAJE-FEW-SHOT.md) para los 7 ejemplos de entrenamiento.

---

## Comportamiento de generación

- `_generate_ollama_structured()` — Ollama con `format="json"` y system prompt de esquema.
- `_generate_ollama()` — Ollama sin forzar formato (para respuestas libres como guías de documentos).
- `_generate_openai()` — API compatible OpenAI (LM Studio, OpenCode, etc).

---

## Reglas de validación

- **JSON inválido** → `None` (caller hace fallback al motor simbólico).
- **Respuesta vacía** → `None`.
- **Errores de red / timeout 30-45s** → `None` + log de error.

---

## Metadata devuelta en cada llamada

```python
{
    "response": str,            # texto del modelo
    "model": str,               # nombre del modelo
    "tokens_prompt": int,       # tokens consumidos en el prompt
    "tokens_generated": int,    # tokens generados
    "duration_ms": float,       # tiempo de generación
    "total_duration_ms": float, # tiempo total (incluye carga)
}
```
