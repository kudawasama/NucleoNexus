# Desarrollo

Guía para entender y contribuir al proyecto.

## Estructura del Proyecto

```
NucleoNexus/
├── main.py                  # Punto de entrada
├── config.py                # Configuración central
├── engine/                  # Motores internos
│   ├── state.py             # Estado persistente del sistema
│   └── actions.py           # Registro de acciones
├── memory/                  # Sistema de memoria
│   ├── store.py             # Fachada NexusMemory
│   ├── semantic.py          # Memoria semántica (hechos)
│   ├── episodic.py          # Memoria episódica (conversaciones)
│   └── procedural.py        # Memoria procedural (patrones)
├── cognition/               # Capa cognitiva
│   ├── symbolic.py          # Motor simbólico
│   ├── slm.py               # Backend SLM (Ollama)
│   └── context.py           # Constructor de contexto
├── knowledge/               # Conocimiento
│   └── loader.py            # Cargador de conocimiento inicial
├── learning/                # Aprendizaje
│   └── extractor.py         # Extractor automático de hechos
├── skills/                  # Skills
│   ├── registry.py          # Registro de skills
│   └── builtins/            # Skills nativas
├── interface/               # Interfaces
│   └── cli.py               # Interfaz de línea de comandos
├── data/                    # Datos persistentes
│   ├── memory/              # Base de datos SQLite
│   ├── knowledge/           # Archivos de conocimiento JSON
│   ├── state/               # Estado en JSON
│   └── logs/                # Logs
└── docs/                    # Documentación
    ├── 01-VISION/
    ├── 02-ARQUITECTURA/
    ├── 03-MEMORIA/
    ├── 04-COGNICION/
    ├── 05-APRENDIZAJE/
    ├── 06-INVESTIGACION/
    ├── 07-SKILLS/
    ├── 08-CONFIGURACION/
    └── 09-DESARROLLO/
```

## Dependencias

Mínimas: **Python 3.11+** sin dependencias externas para el modo simbólico.

Para el SLM: **Ollama** instalado con algún modelo (`qwen2.5:0.5b` recomendado).

## Comandos básicos

```bash
# Iniciar Nexus
python main.py

# Modo solo simbólico (más rápido, sin modelo)
# Cambiar en config.py: ENGINE["mode"] = "symbolic"

# Probar un componente específico
python -c "from memory.store import NexusMemory; m = NexusMemory('data/memory/nexus_memory.db')"
```

## Cómo contribuir

1. **Nuevo conocimiento**: Agrega archivos JSON en `data/knowledge/`
2. **Nuevo patrón de extracción**: Edita `learning/extractor.py` agregando más verbos
3. **Nueva skill**: Crea un archivo en `skills/builtins/`
4. **Nuevo intent**: Agrega el regex en `cognition/symbolic.py` y su handler
