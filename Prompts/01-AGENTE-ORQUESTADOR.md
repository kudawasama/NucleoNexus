# 01 — Agente Orquestador (`cognition/agent.py`)

> **NexusAgent** — Encadena múltiples tools en una sola pasada para tareas complejas.
> A diferencia del flujo normal (1 tool por turno), el agente planifica → ejecuta → aprende → sintetiza.

---

## Diferencia con Hermes Agent

- **Hermes**: el LLM decide iterativamente
- **Nexus**: reglas determinísticas (rápido, no depende del SLM)

---

## Flujo del agente

1. **PLAN** — analizar la tarea, decidir qué tools usar (por palabras clave)
2. **EXECUTE** — ejecutar las tools en secuencia
3. **LEARN** — guardar resultados útiles en memoria
4. **SUMMARIZE** — sintetizar una respuesta

---

## Tipos de tareas y sus planes

| Keyword del usuario | Tipo | Plan ejecutado |
|--------------------|------|----------------|
| `investiga`, `busca información`, `aprende sobre`, `qué es`, `qué son`, `definición de` | `investigate` | `web_search` + aprender + sintetizar |
| `explica`, `detalla`, `describe`, `cómo funciona`, `cuál es la diferencia`, `por qué` | `explain` | `web_search` + `browse_website` (primera URL valiosa) + aprender + sintetizar |
| `documenta`, `crea documentación`, `genera reporte`, `escribe informe` | `document` | `web_search` + `search_files` local + aprender |
| `busca en código`, `busca en archivos`, `encuentra en el código`, `dónde está`, `cómo se usa` | `code_search` | `search_files` (definición) + `read_file` (primeros 40-50 líneas) |
| *(default)* | `investigate` | Igual que el plan investigar |

> **Prioridad de detección**: `code_search` > `document` > `explain` > `investigate`.

---

## Plan: Investigar (default)

```
1. Extraer el tema del task (quitar prefijo "investiga…", stopwords)
   → si no se puede → error "No pude entender el tema a investigar"
2. web_search(tema)
3. Parsear items del output (≥30 chars, filtrar URLs GitHub tipo "github.com/... — ...")
4. memory.learn_fact(item, category="aprendido_web", confidence=0.5, source="auto_web_agent")  [top 3]
5. Sintetizar respuesta con SLM
```

---

## Plan: Explicar

```
1. Extraer el tema (fallback: el task completo)
2. web_search(tema)
3. Extraer URLs valiosas de los resultados
4. browse_website(primera URL valiosa)
5. memory.learn_fact(items, category="aprendido_web", confidence=0.5, source="auto_web_agent")  [top 3]
6. Sintetizar respuesta con SLM
```

---

## Plan: Documentar

```
1. Extraer el tema
2. web_search(tema)
3. search_files(tema) local
4. memory.learn_fact(items, category="aprendido_web", confidence=0.5, source="auto_web_agent")  [top 3]
```

---

## Plan: Buscar en código

```
1. Detectar nombre de función/clase (regex):
   - "la funcion X" / "la funcion X()" → X
   - "el metodo X" / "el metodo X()" → X
   - "la clase X" / "la clase NexusCore" → X
   - "donde esta X" / "donde esta el X" → X
2. Si hay nombre de función:
   - search_files("def {nombre}")  (buscar definición, no menciones)
   - si no hay resultados → search_files({nombre})  (buscar por nombre de archivo)
3. Si NO hay nombre de función:
   - search_files(tema)
4. Filtrar resultados:
   - solo archivos .py
   - excluir __pycache__
   - excluir .history
5. read_file(primer archivo):
   - si hay func_name → search="def {func_name}", max_lines=40
   - si NO → max_lines=50
```

---

## Filtros de URLs (para `browse_website`)

**Bloqueadas** (no se visitan):
- `duckduckgo.com/html`, `duckduckgo.com/changelog`, `duckduckgo.com/?`, `duckduckgo.com/`
- `wikipedia.org/wiki/` (mejor usar el snippet de búsqueda)
- `facebook.com/`, `twitter.com/`, `instagram.com/`, `linkedin.com/`
- Patrones: `/redirect`, `redirect=`, `javascript:`, `login.php`, `login?`, `signin?`
- Endpoints API: `/api/`, `.json`, `.xml`
- Tracking: `utm_`, `/track`, `/share?`

> Si pasa todos los filtros → URL valiosa. **Máximo 3 URLs** por respuesta.

---

## Auto-aprendizaje (reglas de `learn_fact`)

Aprender cada item como hecho **solo si cumple TODAS**:
- Longitud > 30 caracteres
- No empieza con `http` en los primeros 50 chars
- No es un item tipo `github.com/...` con ` — ` (metadatos de repo)

Metadatos: `category="aprendido_web"`, `confidence=0.5`, `source="auto_web_agent"`.
Máximo: **3 items por interacción**.

---

## Síntesis con SLM

**System prompt:**
> Eres Nexus, asistente inteligente. Tu tarea es redactar una respuesta clara y coherente en español basada en la información proporcionada. NO inventes datos. Si la información es insuficiente, dilo. Incluye los puntos principales, no más de 200 palabras.

**User prompt:**
```
Pregunta del usuario: {task}

Información encontrada:
{context_text}

Redacta una respuesta clara y útil en español:
```

Donde `context_text` se construye:
- Para `web_search`: top 3 items rankeados por overlap léxico con el topic (palabras ≥3 letras)
- Para `browse_website`: contenido de la página (max 1500 chars)

### Fallback sin SLM

Si el SLM no está disponible, arma respuesta con:
- Título del tema
- Extractos relevantes (primeras 3 líneas, >30 chars)
- Fuentes (URLs encontradas)

---

## Formato del resumen final

```
Resultados de la investigación:

✓ Paso 1: web_search (245ms)   → primera línea del output (120 chars)
✓ Paso 2: synthesize (1890ms)  → ...

Resumen: X/Y pasos exitosos.
Errores: N pasos fallaron.    (si los hay)
```

---

## Detección de nombres de función/clase (regex)

| Patrón en el task | Extrae |
|-------------------|--------|
| `la funcion X` / `la funcion X()` / `la funcion X.` | `X` |
| `el metodo X` / `el metodo X()` | `X` |
| `la clase X` / `la clase NexusCore` | `X` |
| `donde esta X` / `donde esta el X` | `X` |

> El nombre debe cumplir `[a-z_][a-z0-9_]*` (funciones) o `[A-Z][a-zA-Z0-9_]*` (clases).
