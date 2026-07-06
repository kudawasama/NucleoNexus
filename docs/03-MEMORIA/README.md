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

**Propósito**: Almacenar hechos, conceptos y relaciones que el sistema conoce, soportando búsqueda semántica por embeddings y consolidación dinámica de conocimientos.

**Estructura**:
| Campo | Descripción |
|---|---|
| `id` | Auto-incremental |
| `fact` | Texto del hecho (único) |
| `category` | Categoría (ciencia, matematica, personal...) |
| `confidence` | Confianza (0.0 - 1.0, sube con repetición o deduplicación) |
| `source` | Origen (knowledge_base, auto_usuario, refuerzo...) |
| `created_at` | Timestamp de creación |
| `updated_at` | Timestamp de última actualización |
| `access_count` | Veces que se ha usado / retornado por consultas |
| `embedding` | Vector float de 768 dimensiones (BLOB) almacenado como JSON UTF-8 |

**Optimización de Vectorización Asíncrona (Fase 1)**:
Para evitar latencias y bloqueos en el chat interactivo, la inserción mediante `learn_fact` guarda los hechos de inmediato con `embedding = NULL`. Un hilo worker en segundo plano (demonio) lee constantemente de la base de datos, extrae registros sin embedding y genera el vector de forma asíncrona consultando localmente a Ollama.

**Decaimiento Temporal y Frecuencia de Accesos**:
La consulta de la memoria semántica (`query_knowledge`) integra una fórmula de relevancia híbrida combinando TF-IDF, similitud semántica de coseno, decaimiento temporal y frecuencia de uso para favorecer hechos frescos y útiles frente a los viejos u obsoletos:
* **Time Decay**: $\max(0.2, \text{decay\_rate}^{\Delta t\_dias})$ (donde `decay_rate` por defecto es `0.99`).
* **Access Factor**: $1.0 + 0.1 \times \log(\text{access\_count} + 1)$.

**Deduplicación Semántica y Consolidación (Fase 2A)**:
Al procesar un nuevo embedding, el worker asíncrono realiza una búsqueda interna comparando la similitud coseno contra los vectores ya existentes en la base de datos:
* Si la similitud coseno es mayor o igual a **88%** ($sim \ge 0.88$), el hecho se considera un duplicado semántico redundante.
* **Acción**: El worker incrementa la confianza del hecho original en `+0.1` (tope `1.0`), aumenta el contador de accesos en `+1` y elimina el nuevo registro duplicado para limpiar y consolidar la memoria de fondo.

**Métodos clave**:
```python
memoria.learn_fact(fact, category, confidence, source)  # Aprender de inmediato (asíncrono)
memoria.query_knowledge(query, top_k=3)                 # Buscar con decaimiento y accesos (sincronizado)
memoria.get_facts_by_category(category)                  # Listar hechos de una categoría (sincronizado)
memoria.get_consolidable_facts(min_confidence)          # Obtener hechos listos para guardar en JSON (sincronizado)
memoria.mark_as_consolidated(fact_id)                   # Cambiar source a 'knowledge_base' al persistir (sincronizado)
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
