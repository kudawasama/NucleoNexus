# 07 — Memoria (`memory/`)

> **Sistema de memoria persistente con SQLite + TF-IDF + embeddings opcionales.**
> Tres tipos de memoria: **Episódica** (qué pasó), **Semántica** (qué sé), **Procedimental** (cómo hacer).

---

## Arquitectura

```
NexusMemory (fachada unificada)
  ├── EpisodicMemory   — registro cronológico de interacciones
  ├── SemanticMemory   — hechos y conceptos con confianza
  ├── ProceduralMemory — patrones aprendidos y skills adquiridas
  └── EmbeddingIndex   — búsqueda por similitud coseno (opcional)
```

---

## 1. Memoria Semántica (`memory/semantic.py`)

> *"Almacenamiento de hechos, conceptos y relaciones. Cada hecho tiene un nivel de confianza que aumenta con la repetición."*

### `learn_fact(fact, category, confidence, source, with_embedding)`

Aprende un hecho. Si ya existe, **refuerza confianza**.

**Parámetros:**
- `fact` — texto del hecho
- `category` — default `"general"`
- `confidence` — 0-1 (default 0.5)
- `source` — origen del hecho (`"usuario"`, `"respuesta"`, `"auto_web_agent"`, etc)
- `with_embedding` — si True, genera embedding (default True). `False` para cargas masivas.

**Refuerzo:**
- Si el hecho ya existe → `confidence += 0.1 * repetitions` (cap en 1.0)
- Si llega a `confidence = 1.0` → se considera un hecho **consolidado**

### `query_knowledge(query, top_k)`

Busca hechos por **relevancia semántica de términos significativos**.

**Algoritmo:**
1. Filtra palabras vacías (stop words) para evitar matches por "que", "es", "el"
2. Normaliza acentos para búsqueda robusta
3. Expande la query con sinónimos (vía `learning/synonyms.expand_query`)
4. Calcula score = intersección de términos significativos
5. Si hay embeddings → usa similitud coseno (más rápido y robusto)
6. Si no → usa TF-IDF como fallback
7. Devuelve top_k hechos rankeados

> **Score refleja**: cuántos términos significativos de la query aparecen en el hecho.

---

## 2. Memoria Episódica (`memory/episodic.py`)

> *"Registro cronológico de interacciones con el usuario. Cada recuerdo es una interacción completa con timestamp."*

### Estructura de un recuerdo

```json
{
  "id": int,
  "role": "user" | "nexus",
  "content": "texto del mensaje",
  "timestamp": "ISO 8601",
  "context": { "backend": "main", "intent": "..." }
}
```

### `TFIDFIndex` — Índice liviano (sin dependencias)

Construye índice TF-IDF en memoria para búsqueda de recuerdos similares.

- Vocabulario: tokens normalizados (sin acentos, minúsculas)
- IDF: log(N / df) sobre el corpus
- Similitud: coseno entre vectores sparse

### `recall(query, top_k)` — Recordar interacciones similares

Algoritmo:
1. Tokenizar query
2. Vectorizar con TF-IDF
3. Calcular similitud coseno con todos los recuerdos
4. Devolver top_k con `score >= 0.1` (umbral mínimo)

### `get_recent(limit)` — Recuerdos recientes

Devuelve los últimos N recuerdos en orden cronológico inverso.

### `get_conversation_history(limit)` — Historial para contexto

Devuelve los últimos N mensajes formateados como:
```
user: texto (max 80 chars)
nexus: texto (max 80 chars)
```

> Límite por defecto: 5.

---

## 3. Memoria Procedimental (`memory/procedural.py`)

> *"Patrones de respuesta aprendidos de interacciones. Cada patrón tiene efectividad que sube o baja según su uso."*

### `learn_pattern(intent, response_template, effectiveness)`

Aprende un patrón:
- `intent` — descripción del patrón (ej: "saludo", "pregunta_hora", "queja")
- `response_template` — plantilla de respuesta (puede tener `{variables}`)
- `effectiveness` — 0-1 (default 0.5)

**Refuerzo:**
- Si el patrón se usa con éxito → `effectiveness += 0.05`
- Si falla → `effectiveness -= 0.1`
- Cap en [0, 1]

### `match_pattern(text)`

Encuentra el patrón que mejor matchea un texto del usuario.
Devuelve el `response_template` con las variables substituidas.

### `get_top_patterns(limit)`

Devuelve los N patrones con mayor effectiveness, ordenados descendentemente.

---

## 4. Embeddings Vectoriales (`memory/embeddings.py`)

> *"Genera embeddings usando nomic-embed-text (Ollama) y realiza búsqueda semántica por similitud de coseno."*
> *"Reemplaza la búsqueda TF-IDF con búsqueda por significado."*

### `get_embedding(text)` — Vector de 768 dimensiones

Genera embedding para un texto usando `nomic-embed-text`.

**Returns:** Lista de 768 floats, o `None` si falla.

### `is_available()` — Detección

Verifica si el modelo de embeddings está disponible en Ollama.

- Endpoint: `GET http://localhost:11434/api/tags`
- Busca modelo que contenga `"nomic"` o `"embed"`

### `EmbeddingIndex` — Índice en memoria

Mantiene todos los embeddings cargados para calcular similitud coseno sin consultas SQL complejas.

**Métodos:**
- `add(text, embedding)` — agregar embedding
- `search(query_embedding, top_k)` — top_k más similares
- `save(path)` / `load(path)` — persistir índice a disco

### Activación / desactivación

El sistema usa embeddings **solo si están disponibles**. Si no, cae a TF-IDF automáticamente.

---

## 5. Almacén unificado (`memory/store.py`)

> `NexusMemory` — Fachada unificada para los tres tipos de memoria.

### API principal

```python
memory = NexusMemory(db_path, state_engine)

# Aprender
memory.learn_fact(fact, category=..., confidence=0.5, source=...)
memory.remember(role, content, context={...})

# Recordar
memory.recall(query, top_k=3)        # recuerdos similares
memory.query_knowledge(query, top_k=2)  # hechos relevantes
memory.get_conversation_history(limit=5)  # historial reciente

# Patrones
memory.learn_pattern(intent, template, effectiveness=0.5)
memory.match_pattern(text)
```

### Persistencia

- **SQLite** (`data/memory/nexus.db`) — recuerdos y hechos
- **JSON** (`data/memory/embeddings.json`) — índice de embeddings (opcional)
- **State** (`data/state/nexus_state.json`) — métricas, fase, confianza

---

## Filosofía

> *"Sistema completo de memoria con SQLite + TF-IDF. Implementa los tres tipos de memoria del modelo arquitectónico: Episódica, Semántica, Procedimental."*

- **Sin dependencias externas** para el modo básico (solo stdlib)
- **Embeddings opcionales** como upgrade (requiere `nomic-embed-text` en Ollama)
- **Capas progresivas**: TF-IDF → sinónimos → embeddings → futuro fine-tuning
