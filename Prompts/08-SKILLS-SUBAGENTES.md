# 08 — Skills / Sub-agentes (`skills/builtins/*`)

> **17 skills modulares** que se auto-registran como acciones de function-calling.
> Cada skill es como un "sub-agente" especializado: encapsula una capacidad con su nombre, descripción y lógica.

---

## Patrón de auto-registro

Toda skill sigue este contrato (del weather_skill.py docstring):

> *"Para crear una skill nueva solo necesitas:*
> 1. *Crear un archivo .py en skills/builtins/*
> 2. *Definir una función `register()` que devuelva un `Skill`*
> 3. *Registrar acciones con `skill.register_action()`*
> 4. *Listo — Nexus la carga automáticamente al iniciar"*

---

## Las 17 skills builtin

### 1. `calc_skill` — Calculadora Científica

- **Doc**: *"Operaciones matemáticas avanzadas usando `math` de la stdlib. Sin dependencias externas."*
- **Acciones expuestas**:
  - `calc(expr)` — evalúa expresión matemática (sqrt, sin, log, etc)

### 2. `csv_skill` — Lector CSV

- **Doc**: *"Lee archivos CSV y muestra resumen de datos. Usa solo la stdlib (csv, statistics)."*
- **Acciones expuestas**:
  - `csv_summary(path)` — primeras N filas + estadísticas básicas
  - `csv_query(path, condition)` — filtrar filas

### 3. `currency_skill` — Conversor de Monedas

- **Doc**: *"Consulta valores del dólar, UF, UTM, euro en CLP. Usa mindicador.cl (API gratuita chilena, sin API key)."*
- **Acciones expuestas**:
  - `currency(moneda, fecha?)` — convierte o consulta valor
  - Monedas: USD, EUR, CLP, UF, UTM, IVP

### 4. `files_skill` — Archivos Locales

- **Doc**: *"Lee, escribe y lista archivos en el sistema. Opera solo dentro del directorio del proyecto por seguridad."*
- **Acciones expuestas**:
  - `read_file(path, max_lines?, search?)`
  - `write_file(path, content)`
  - `list_files(directory?, pattern?)`
- **Regla de seguridad**: paths absolutos fuera del proyecto → rechazados.

### 5. `images_skill` — Imágenes

- **Doc**: *"Lista y analiza imágenes en el sistema.*
  - *Sin dependencias: muestra metadatos (nombre, tamaño, dimensiones)*
  - *Con SLM vision: describe el contenido (si el modelo lo soporta)"*
- **Acciones expuestas**:
  - `list_images(directory?)`
  - `image_info(path)` — metadatos
  - `image_describe(path)` — solo si hay SLM vision

### 6. `meta_skill` — Auto-mejora (Autoskill)

- **Doc**: *"Sistema de auto-mejora: detecta correcciones, extrae patrones, edita código de otras skills con respaldo y diff."*

**Ciclo completo (7 pasos):**
1. Detecta corrección en la conversación
2. Extrae: qué patrón cambiar → por qué reemplazarlo
3. Identifica la skill y el punto exacto de edición
4. Genera el nuevo código con un template
5. Muestra diff antes de aplicar
6. Crea backup + aplica cambio
7. Verifica sintaxis post-cambio

- **Acciones expuestas**:
  - `meta_analyze(correction_text)`
  - `meta_propose_change(skill_name, old_code, new_code)`
  - `meta_apply_change(proposal_id)`

### 7. `moon_skill` — Fase Lunar

- **Doc**: *"Calcula la fase de la luna para cualquier fecha. Algoritmo astronómico simple, sin APIs externas."*
- **Acciones expuestas**:
  - `moon_phase(date?)` — fase actual o de una fecha

### 8. `network_skill` — Network / IP / DNS

- **Doc**: *"Consulta IP pública, resuelve dominios, ping. Usa servicios públicos gratuitos."*
- **Acciones expuestas**:
  - `public_ip()`
  - `dns_resolve(domain)`
  - `ping(host, count?)`

### 9. `notes_skill` — Notas Persistentes

- **Doc**: *"Guarda y recupera notas personales usando SQLite. Las notas persisten entre sesiones automáticamente."*
- **Acciones expuestas**:
  - `note_add(title, content, tags?)`
  - `note_get(id?)` o `note_get(query)`
  - `note_list()`
  - `note_delete(id)`

### 10. `reminders_skill` — Recordatorios

- **Doc**: *"Crea recordatorios con tiempo. Al iniciar, revisa si hay recordatorios vencidos y los notifica."*
- **Acciones expuestas**:
  - `reminder_add(text, when)`
  - `reminder_list()`
  - `reminder_delete(id)`
  - `reminder_check()` — revisa vencidos

### 11. `system_skill` — Sistema Base

- **Doc**: *"Skill base del sistema: estado, versión, métrica, salud."*
- **Acciones expuestas**:
  - `get_status()` — estado completo
  - `get_version()` — versión + commit + fase
  - `get_metrics()` — interacciones, éxito, hechos aprendidos
  - `health_check()`

### 12. `todo_skill` — Todo List

- **Doc**: *"Lista de tareas pendientes persistente en SQLite. CRUD completo: agregar, listar, completar, eliminar."*
- **Acciones expuestas**:
  - `todo_add(task, priority?)`
  - `todo_list(filter?)` — `pending|done|all`
  - `todo_complete(id)`
  - `todo_delete(id)`

### 13. `tools_skill` — Tools estilo Hermes Agent

- **Doc**: *"Tools: web_search, read_file, write_file, search_files, run_command, python_eval, browse_website.*
> *Cada tool se auto-registra como acción en el ActionRegistry de Nexus."*
- **Acciones expuestas (las 7 nativas)**:
  - `web_search(query)` — DuckDuckGo Lite
  - `read_file(path, ...)` — leer archivo con contexto
  - `write_file(path, content)` — escribir archivo
  - `search_files(pattern, path?, file_glob?)` — grep-like
  - `run_command(command, timeout?)` — shell con timeout
  - `python_eval(expr)` — evaluar expresión Python
  - `browse_website(url)` — extraer contenido textual

### 14. `weather_skill` — Clima

- **Doc**: *"Skill de ejemplo que muestra cómo extender Nexus con nuevas capacidades. Usa wttr.in (gratuito, sin API key) para consultar el clima."*
- **Acciones expuestas**:
  - `weather(city)` — clima actual
  - `weather_forecast(city, days?)` — pronóstico

### 15. `web_search_skill` — Búsqueda Web (dedicada)

- **Doc**: *"Busca en internet usando DuckDuckGo Lite (sin API key).*
> *Requiere: pip install requests (opcional, si no está instalado falla graceful)"*
- **Acciones expuestas**:
  - `web_search(query, max_results?)` — devuelve top 5-10 resultados

### 16. `tools_skill` (alias de function-calling principal) — ver punto 13

> ⚠️ **Nota**: `tools_skill.py` (627 líneas) es el contenedor principal de las 7 tools nativas. Las otras 16 skills se especializan en dominios.

### 17. (interna) `__init__.py` — carga automática

Carga todas las skills en el directorio `skills/builtins/` al iniciar Nexus.

---

## Convenciones de cada skill

### Estructura típica

```python
"""
Skill — {Nombre}
{descripción corta}
"""

def register() -> Skill:
    skill = Skill(
        name="nombre_skill",
        description="Lo que hace esta skill",
    )

    @skill.register_action(
        name="nombre_accion",
        description="Qué hace esta acción",
        params={...}
    )
    def nombre_accion(param1: str, param2: int = 0) -> dict:
        # lógica
        return {"success": True, "result": ...}

    return skill
```

### Contrato de retorno de cada acción

```json
{
  "success": true | false,
  "result": "...",        // output principal
  "error": "...",         // si success=False
  "metadata": { ... }     // opcional
}
```

---

## Cómo el SLM las invoca

El SLM emite JSON:
```json
{
  "accion": "usar_herramienta",
  "herramienta": "weather",
  "parametros": { "city": "Santiago" }
}
```

`ActionRegistry.execute()` valida parámetros, llama al handler, registra la llamada para auditoría, y devuelve el resultado al SLM.

Ver [02-AGENTE-SLM.md](./02-AGENTE-SLM.md) para el esquema JSON completo.
