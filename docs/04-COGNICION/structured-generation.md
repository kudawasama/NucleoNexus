# Structured Generation

Nexus usa **JSON mode nativo de Ollama** para forzar que el SLM genere respuestas en un formato estructurado y predecible.

## Cómo funciona

1. Las consultas que van al SLM se envían con `"format": "json"` en la API de Ollama
2. El sistema instruye al modelo para que genere JSON con campos específicos
3. La respuesta JSON se parsea para extraer la respuesta y acciones
4. Las acciones detectadas se ejecutan automáticamente

## Esquema JSON

```json
{
  "respuesta": "texto de respuesta al usuario",
  "accion": "responder | buscar_memoria | calcular | usar_herramienta",
  "tema": "tema a buscar (si accion=buscar_memoria)",
  "expresion": "expresión a calcular (si accion=calcular)",
  "herramienta": "web_search (si accion=usar_herramienta)",
  "parametros": {"query": "termino busqueda"}
}
```

## Acciones Soportadas

| accion | Descripción |
|---|---|
| `responder` | Solo devuelve la respuesta del SLM (la más común) |
| `buscar_memoria` | Busca un tema en la base de conocimiento y lo aprende |
| `calcular` | Evalúa una expresión matemática |
| `usar_herramienta` | Ejecuta una herramienta del sistema (web_search, read_file, etc.) |

> **Nota**: Las herramientas también se ejecutan **directamente** desde el intent
> detectado (ver `NexusCore._handle_tool_intent()`), no solo via JSON.
> Esto es más confiable porque Qwen 0.5B no siempre genera el JSON correcto.

## Implementación

**Archivo**: `cognition/slm.py` — método `_generate_ollama_structured()`

```python
slm.generate(prompt, system_prompt=ctx, structured=True)
# → devuelve dict con 'response', 'model', 'tokens_prompt', 
#   'tokens_generated', 'duration_ms'
```

**Flujo en main.py**:
1. SLM genera JSON
2. Se parsea con `json.loads()`
3. Se extrae `respuesta` y `accion`
4. Si `accion == "buscar_memoria"` → busca en memoria semántica y aprende
5. Si `accion == "calcular"` → registra la operación
6. Si `accion == "usar_herramienta"` → ejecuta la herramienta via ActionRegistry
7. Si `accion == "responder"` → solo devuelve la respuesta

## Ventajas

- **Formato garantizado**: Ollama fuerza JSON a nivel de token, el modelo no puede desviarse
- **Sin dependencias extra**: usa el `format: json` nativo de Ollama
- **Acciones detectables**: el sistema puede ejecutar acciones basadas en campos del JSON
- **Fallback seguro**: si el JSON no es válido, se usa la respuesta como texto plano
