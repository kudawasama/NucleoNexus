# 14 — Configuración y Versionado (`config.py` + `version.py`)

> **Configuración central y versionado semántico automático basado en git.**

---

## A) `config.py` — Configuración Central

> *"Nucleo Nexus — Configuración Central. Toda la configuración del sistema en un solo lugar.*
> *A medida que Nexus evoluciona, aquí se agregan nuevas opciones."*

### Secciones principales

```python
SYSTEM = {
    "name": "Nucleo Nexus",
    "version": "0.1.0",
    "author": "Jose Cespedes",
    "repository": "github.com/kudawasama/NucleoNexus",
    "phase": "Proto",
}

ENGINE = {
    "mode": "hybrid",          # "symbolic" | "slm" | "hybrid"
    "llm": {
        "backend": "ollama",   # "ollama" | "openai" | "opencode"
        "model_name": "hermes3:3b",
        "api_base": "http://localhost:11434",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout_s": 45,
    },
}

MEMORY = {
    "db_path": "data/memory/nexus.db",
    "episodic_limit": 1000,    # recuerdos máximos
    "semantic_limit": 5000,    # hechos máximos
    "embedding_model": "nomic-embed-text",
    "embedding_dim": 768,
    "use_embeddings_if_available": True,
}

LEARNING = {
    "pattern_extraction": True,    # extraer patrones de cada interacción
    "reinforcement": True,         # reforzar con feedback
    "auto_skill_create": False,    # meta-skill habilitado?
    "min_confidence_to_keep": 0.1, # umbral mínimo de confianza
}

INTERFACE = {
    "type": "cli",            # "cli" | "api" | "web"
    "colors": True,
    "history_size": 100,
    "show_status_callbacks": True,
}

LOG_LEVEL = "INFO"
LOG_FILE = "data/logs/nexus.log"
DATA_DIR = Path("data")
KNOWLEDGE_DIR = Path("data/knowledge")
SKILLS_DIR = Path("skills/builtins")
MEMORY_DB_PATH = "data/memory/nexus.db"
```

### Filosofía de configuración

- **Un solo lugar** — `config.py` es la fuente de verdad
- **Sin sobre-configuración** — solo lo necesario
- **Edit-able** — `nexus config edit` abre el archivo en el editor del sistema
- **Sin secretos** — los tokens van en variables de entorno o Windows Credential Manager (nunca en este archivo)

---

## B) `version.py` — Versionado Automático

> *"Lee la información de versión desde git (commits) para generar un versionado semántico automático: 0.1.0+build.COMMIT_COUNT"*
> *"La versión se recalcula llamando `refresh_version()`."*

### Constantes

```python
VERSION = "0.1.0"        # semver manual (solo patch bump automático)
BUILD = <int>            # = número de commits en el repo
COMMIT = "<short_sha>"   # = hash corto del HEAD
FULL_VERSION = "0.1.0+build.42.commit.19f3900"
```

### `refresh_version()` — Recalcular al iniciar

```python
import subprocess
result = subprocess.run(["git", "rev-list", "--count", "HEAD"], ...)
BUILD = int(result.stdout.strip())

result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], ...)
COMMIT = result.stdout.strip()

FULL_VERSION = f"{VERSION}+build.{BUILD}.commit.{COMMIT}"
```

### Salida típica de `nexus version`

```
╔══ Nucleo Nexus ══╗
  Version:  0.1.0+build.42.commit.19f3900
  Semver:   0.1.0
  Build:    42
  Commit:   #19
  Fase:     Proto
  Autor:    Jose Cespedes
  Repo:     github.com/kudawasama/NucleoNexus
```

### Auto-bump (referencia en `auto_versioning` skill)

Las reglas (no implementadas en `config.py`, sí en el flujo de auto-versioning):

| Tipo de cambio | Bump |
|----------------|------|
| `feat:` (nueva feature) | MINOR (0.1.0 → 0.2.0) |
| `fix:` (bug fix) | PATCH (0.1.0 → 0.1.1) |
| `feat!:` / `BREAKING CHANGE:` | MAJOR (0.1.0 → 1.0.0) |
| `docs:`, `chore:`, `refactor:`, `test:`, `ci:` | sin bump |

> El **auto-bump** se hace leyendo los mensajes de commit desde el último tag.

---

## Filosofía

> *"Toda la configuración del sistema en un solo lugar. A medida que Nexus evoluciona, aquí se agregan nuevas opciones."*

La configuración es la **interfaz humana** del proyecto: cambiar un valor en `config.py` no requiere entender el código de los módulos.
