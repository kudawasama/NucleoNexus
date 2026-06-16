# Skills y Acciones

El sistema de skills permite extender las capacidades de Nexus con módulos reutilizables.

## Registro de Acciones (`engine/actions.py`)

Las acciones son funciones registradas que el sistema puede ejecutar:

```python
# Registrar una acción
actions.register_fn(
    name="learn_fact",
    description="Aprende un nuevo hecho o concepto",
    handler=mi_funcion,
    parameters={
        "fact": {"type": "string", "description": "El hecho a aprender"},
        "category": {"type": "string", "description": "Categoría"},
    },
)
```

### Acciones del núcleo

| Acción | Descripción |
|---|---|
| `learn_fact` | Aprende un nuevo hecho en memoria semántica |
| `recall` | Busca recuerdos relacionados con un tema |
| `get_nexus_status` | Obtiene el estado completo del sistema |

### Acciones de skills

| Skill | Acciones |
|---|---|
| `system` | get_status, get_time, set_personality |
| `weather` | get_weather |

---

## Invocación de Acciones

### Desde el motor simbólico

Formato: `[[accion:nombre(parametros)]]`

```
[[accion:learn_fact(fact=El cielo es azul, category=ciencia)]]
```

### Desde el SLM

El SLM puede generar acciones si se incluyen en el contexto. El prompt indica:

```
Para usar una acción, responde con: [[accion:nombre(parametros)]]
```

---

## Crear una Skill

1. Crear archivo en `skills/builtins/`
2. Definir acciones
3. Registrar en `skills/registry.py`

Estructura de ejemplo:
```python
# skills/builtins/mi_skill.py
def register(skill_registry, action_registry):
    action_registry.register_fn(
        name="mi_accion",
        description="Descripción de mi acción",
        handler=lambda: {"resultado": "ok"},
    )
```
