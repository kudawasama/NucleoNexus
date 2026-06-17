# Arquitectura del Sistema

```
+---------------------------------------------------------------+
|                     INTERFAZ                                   |
|             (CLI / API / Web)                                 |
+---------------------------------------------------------------+
|                   CAPA COGNITIVA                               |
|  +----------+  +----------+  +-----------------------------+  |
|  | Simbolico |  |   SLM    |  | Inyector de               |  |
|  | (default) |  | (Qwen,   |  | Contexto                  |  |
|  |           |  |  Phi...) |  | Dinamico                  |  |
|  +----------+  +----------+  +-----------------------------+  |
+---------------------------------------------------------------+
|                  SKILLS / ACCIONES                             |
|      (Function Calling . Registry . Builtins)                 |
+---------------------------------------------------------------+
|                MOTOR DE ESTADO                                 |
|   (JSON persistente . Metricas . Fases)                      |
+---------------------------------------------------------------+
|                MEMORIA PERSISTENTE                             |
|  +----------+  +----------+  +-----------------------------+  |
|  |Epi-sodica|  |Semantica |  |Procedimental               |  |
|  | (Que     |  | (Hechos) |  | (Como hacer)               |  |
|  |  paso)   |  |          |  |                            |  |
|  +----------+  +----------+  +-----------------------------+  |
|              SQLite + TF-IDF                                   |
+---------------------------------------------------------------+
|              SISTEMA (archivos, DB, procesos)                  |
+---------------------------------------------------------------+
```

## Flujo de Procesamiento

### Proceso principal (`process()` en `main.py`)

```
Usuario: "¿Qué es la fotosíntesis?"
  ↓
  1. _get_response() decide qué backend usar
  ↓
  2. ¿Modo hybrid y SLM cargado?
     ├── Sí → detecta intent
     │        ├── fast_intent? (saludo, hora, etc.) → SIMBÓLICO
     │        └── ¿Hay hechos en memoria?  
     │             ├── Sí → SIMBÓLICO (responde desde memoria)
     │             └── No → SLM (Qwen genera)
     └── No → SIMBÓLICO (fallback)
  ↓
  3. Aprender de la interacción (extractor)
  ↓
  4. Registrar en memoria episódica
  ↓
  5. Actualizar estado
  ↓
  Respuesta al usuario
```

## Modos de Operación

| Modo | Qué hace | Cuándo usarlo |
|---|---|---|
| `symbolic` | Solo motor simbólico (regex + TF-IDF) | Sin modelo, pruebas, ultra-ligero |
| `slm` | Todo via SLM (Qwen) | Cuando quieres respuestas generadas siempre |
| `hybrid` | Intents rápidas → simbólico, resto → SLM | **Recomendado**: lo mejor de ambos |

### Modo Híbrido: reglas de ruteo

```
¿El intent es fast_intent?
├── Sí: ¿calcular sin números? → pasa a SLM
│                        └── No → SIMBÓLICO
└── No: ¿Hay hechos en memoria (score ≥ 0.15)?
        ├── Sí → SIMBÓLICO
        └── No → SLM
```

**Fast intents**: saludo, despedida, agradecimiento, presentacion, hora, calcular (con números), fase, ayuda, memoria, nombre, reset, personalidad, confianza, estado, clima.

**Tool intents** (se ejecutan directo sin SLM, ver `NexusCore._handle_tool_intent()`): `web_search`, `read_file`, `search_files`, `run_command`, `browse_url`. Para estos intents, Nexus extrae parámetros del texto con regex y ejecuta la herramienta via ActionRegistry. Más confiable que esperar que Qwen 0.5B genere el JSON de tool call correctamente.

## Backend SLM (Ollama)

El SLM se conecta a Ollama usando el modelo `qwen2.5:0.5b`. Si no puede cargar (Ollama caído, modelo no encontrado), el sistema cae automáticamente a modo simbólico.

### Cuándo se usa el SLM

El SLM **solo** se activa cuando:
1. No es un fast intent (saludo, hora, etc.)
2. No hay hechos relevantes en memoria semántica

Esto minimiza el uso del SLM a solo lo que realmente necesita generación de texto.

## Archivos Clave

| Archivo | Propósito |
|---|---|
| `main.py` | Punto de entrada, `NexusCore`, `process()` |
| `engine/state.py` | Motor de estado persistente |
| `engine/actions.py` | Registro de acciones |
| `cognition/symbolic.py` | Motor simbólico (pattern matching) |
| `cognition/slm.py` | Backend SLM (Ollama) |
| `cognition/context.py` | Constructor de contexto para el SLM |
| `memory/store.py` | Fachada de memoria (episódica + semántica + procedural) |
| `memory/semantic.py` | Memoria semántica con búsqueda TF-IDF |
| `memory/episodic.py` | Memoria episódica (conversaciones) |
| `memory/procedural.py` | Memoria procedural (patrones aprendidos) |
| `knowledge/loader.py` | Cargador de conocimiento inicial |
| `learning/extractor.py` | Extractor automático de hechos |
| `skills/registry.py` | Registro de skills |
| `config.py` | Configuración central |
