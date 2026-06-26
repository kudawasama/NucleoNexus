# 11 — Interfaz CLI (`interface/cli.py` + `nexus.py`)

> **Terminal interactiva + punto de entrada con subcomandos.**

---

## A) `nexus.py` — CLI con subcomandos

Punto de entrada desde terminal. Tabla de comandos:

| Comando | Acción | Descripción |
|---------|--------|-------------|
| `nexus` (sin args) | `cmd_start` | Inicia el chat interactivo |
| `nexus start` | `cmd_start` | Igual que arriba |
| `nexus update` | `cmd_update` | `git pull` desde GitHub |
| `nexus restart` | `cmd_restart` | `git pull` + estado fresco |
| `nexus status` | `cmd_status` | Muestra estado del sistema |
| `nexus model list` | `cmd_model` (list) | Lista modelos Ollama instalados |
| `nexus model use <m>` | `cmd_model` (use) | Cambia al modelo especificado |
| `nexus model test [q]` | `cmd_model` (test) | Compara todos los backends |
| `nexus config` | `cmd_config` | Muestra config actual |
| `nexus config edit` | `cmd_config` (edit) | Abre `config.py` en editor |
| `nexus backup` | `cmd_backup` | Backup del estado y memoria |
| `nexus logs` | `cmd_logs` | Muestra últimas líneas del log |
| `nexus version` | `cmd_version` | Versión, commit, build |
| `nexus clean` | `cmd_clean` | Limpia cache y temporales |
| `nexus help` | `cmd_help` | Muestra la ayuda |

### `cmd_status()` — Salida

```
╔══ Estado de Nexus ══╗
  Version:       0.1.0+build.42
  Commit:        #19
  Fase:          Proto
  Backend:       symbolic
  SLM cargado:   🟢 Si
  Modelo config: hermes3:3b
  Interacciones: 42
  Hechos aprendidos: 128
  Skills:        15
  Confianza:     12.5%
  Personalidad:  analytical (form: 50%)
  Exitos:        38/42
  Memoria:       1,000 episodica, 5,000 semantica

  Modelos Ollama:
    ⭐ hermes3:3b (1.5GB, 3B)
       qwen2.5:0.5b (0.5GB, 0.5B)
```

### `cmd_version()` — Salida

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

### `cmd_model use <m>`

Cambia el modelo activo:
1. Actualiza `config.ENGINE["llm"]["model_name"]`
2. Actualiza el state
3. Muestra: `✅ Modelo cambiado a: {nombre}. Reinicia Nexus para aplicar: nexus restart`

### `cmd_backup()`

Backup automático a `backups/nexus_backup_{YYYYMMDD_HHMMSS}/`:
- `nexus_state.json` (estado)
- `nexus.db` (memoria SQLite)

### `cmd_clean()`

Limpia:
- `__pycache__/` (raíz)
- `data/logs/`
- `__pycache__/` recursivo en todo el proyecto

> ⚠️ **No borra**: `data/memory/`, `data/state/`, `data/knowledge/`.

---

## B) `interface/cli.py` — Terminal interactiva

> **NexusCLI** — Terminal interactivo de Núcleo Nexus.
> *"Con colores, historial y comandos."*

### Comandos slash (en chat)

| Comando | Acción |
|---------|--------|
| `/help` | Muestra ayuda |
| `/status` | Estado del sistema |
| `/fase` | Fase actual + progreso |
| `/personalidad` | Muestra/configura personalidad |
| `/reset` | Reinicia estado (requiere confirmación) |
| `/clear` | Limpia pantalla |
| `/history` | Historial de la sesión |
| `/facts` | Hechos aprendidos |
| `/skills` | Lista de skills cargadas |
| `/exit`, `/quit` | Salir |

### Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `↑` / `↓` | Navegar historial |
| `Tab` | Autocompletar comandos |
| `Ctrl+C` | Cancelar input actual |
| `Ctrl+D` | Salir (EOF) |

### Formato de salida

- **Colores ANSI**:
  - Verde → respuestas de Nexus
  - Cyan → prompts del sistema
  - Amarillo → advertencias
  - Rojo → errores
  - Gris → metadata y debug

- **Prompt**: `> ` (cyan)

### Status callbacks

Durante operaciones largas (SLM, web search), muestra:
```
🔍 Analizando mensaje...
📚 Aprendiendo de la interacción...
```

Vienen de `on_status` en `NexusCore.process()`.

---

## C) `interface/menu.py` — Menú interactivo con teclado

> *"Navegación con flechas ↑↓, selección con Enter/Espacio, cancelar con Esc/q."*

### `interactive_menu(title, options, default=0)`

```python
from interface.menu import interactive_menu

options = ["Ver modelo actual", "Lista modelos", "Cambio rápido", "Test"]
choice = interactive_menu("Gestión de Modelos", options)

if choice == 0:    # Ver modelo actual
    ...
if choice is None:  # usuario canceló
    return
```

**Comportamiento:**
- `↑` / `↓` → mover cursor
- `Enter` → seleccionar
- `Espacio` → toggle (para multi-select)
- `Esc` / `q` → cancelar (retorna `None`)
- `default` → índice resaltado al inicio

**Returns:**
- `int` — índice seleccionado (0-based)
- `None` — si el usuario canceló
