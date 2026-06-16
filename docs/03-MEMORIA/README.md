# Sistema de Memoria

El sistema de memoria de Nexus está inspirado en el modelo de memoria humana: tres tipos distintos que trabajan juntos.

## Arquitectura

```
NexusMemory (Fachada)
├── EpisodicMemory   → ¿Qué pasó? (conversaciones, interacciones)
├── SemanticMemory   → ¿Qué sé? (hechos, conceptos, relaciones)
└── ProceduralMemory → ¿Cómo hacerlo? (patrones, skills, secuencias)
```

Persistencia: **SQLite** (un solo archivo: `data/memory/nexus_memory.db`)

---

## Memoria Episódica (`memory/episodic.py`)

**Propósito**: Registrar cada interacción con el usuario en orden cronológico.

**Estructura**:
| Campo | Descripción |
|---|---|
| `id` | Auto-incremental |
| `timestamp` | Unix timestamp |
| `role` | "user" o "nexus" |
| `content` | Texto del mensaje |
| `context` | JSON con metadatos (intent, backend usado) |
| `importance` | Importancia del recuerdo (1.0 por defecto) |

**Búsqueda**: TF-IDF sobre contenido. Cada interacción se indexa y se puede buscar por similitud de texto.

**Límite**: 10,000 entradas (configurable). Las más antiguas se descartan.

**Métodos clave**:
```python
memoria.remember(role, content, context)  # Guardar interacción
memoria.recall(query, top_k=5)           # Buscar similares
memoria.get_recent(limit=20)             # Últimas interacciones
memoria.get_conversation_history(limit=10)  # Historial formateado
```

---

## Memoria Semántica (`memory/semantic.py`)

**Propósito**: Almacenar hechos, conceptos y relaciones que el sistema conoce.

**Estructura**:
| Campo | Descripción |
|---|---|
| `id` | Auto-incremental |
| `fact` | Texto del hecho (único) |
| `category` | Categoría (ciencia, matematica, personal...) |
| `confidence` | Confianza (0.0 - 1.0, sube con repetición) |
| `source` | Origen (knowledge_base, auto_usuario, refuerzo...) |
| `created_at` | Timestamp de creación |
| `updated_at` | Timestamp de última actualización |
| `access_count` | Veces que se ha usado |

**Búsqueda inteligente** (`query_knowledge`):
1. Tokeniza la query extrayendo términos significativos
2. Filtra **stop words** (que, es, por, para, una, etc.)
3. Normaliza acentos (á → a, é → e, etc.)
4. Calcula relevancia: qué proporción de términos significativos aparecen en el hecho
5. Penaliza matches únicos cuando hay múltiples términos en la query
6. Ordena por relevancia + confianza

**Aprendizaje**:
- `learn_fact()` inserta o refuerza (si ya existe, sube confidence +0.1)
- La repetición refuerza automáticamente

**Métodos clave**:
```python
memoria.learn_fact(fact, category, confidence, source)  # Aprender
memoria.query_knowledge(query, top_k=3)                 # Buscar
memoria.get_facts_by_category(category)                  # Por categoría
```

---

## Memoria Procedural (`memory/procedural.py`)

**Propósito**: Patrones de respuesta aprendidos de interacciones.

**Estructura**:
| Campo | Descripción |
|---|---|
| `id` | Auto-incremental |
| `name` | Nombre del patrón (único) |
| `pattern` | Expresión regular del patrón |
| `response` | Respuesta asociada |
| `triggers` | Palabras gatillo (JSON array) |
| `effectiveness` | Efectividad (0.0 - 1.0, sube/baja con uso) |
| `use_count` | Veces usado |

**Métodos clave**:
```python
memoria.learn_pattern(name, pattern, response, triggers)  # Aprender patrón
memoria.find_pattern(input_text)                          # Buscar coincidencia
memoria.reinforce_pattern(name, success)                  # Reforzar/penalizar
```

---

## Conocimiento Inicial

El sistema carga hechos desde archivos JSON en `data/knowledge/` al iniciar.

**Formato**:
```json
[
  {
    "fact": "La fotosíntesis es el proceso...",
    "category": "ciencia",
    "source": "knowledge_base"
  }
]
```

**Archivos actuales**:
| Archivo | Categoría | Hechos |
|---|---|---|
| `ciencia.json` | ciencia | 10 |
| `matematica.json` | matematica | 12 |

El cargador (`knowledge/loader.py`) procesa todos los `*.json` del directorio y los inserta en memoria semántica con `confidence=0.5`.
