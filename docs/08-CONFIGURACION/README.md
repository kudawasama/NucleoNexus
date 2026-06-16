# Configuración del Sistema

Toda la configuración centralizada en `config.py`.

## Engine (Motor de IA)

```python
ENGINE = {
    "mode": "hybrid",       # "symbolic" | "hybrid" | "llm"
    "symbolic": {
        "max_patterns": 5000,
        "min_confidence": 0.15,
        "learning_rate": 0.1,
    },
    "llm": {
        "backend": "ollama",          # "ollama" | "llamacpp" | "openai" | None
        "model_path": None,           # Ruta al modelo GGUF (llamacpp)
        "model_name": "qwen2.5:0.5b", # Modelo en Ollama
        "api_base": "http://localhost:11434/v1",
        "api_key": "not-needed",
        "max_tokens": 1024,
        "temperature": 0.7,
    }
}
```

### Modos del engine

| Modo | Descripción |
|---|---|
| `symbolic` | Solo motor simbólico, sin LLM |
| `hybrid` | Simbólico para intents rápidas + SLM para preguntas complejas |
| `llm` | Todo via SLM (experimental) |

---

## Memoria

```python
MEMORY = {
    "episodic_limit": 10000,   # Máximo de entradas episódicas
    "semantic_limit": 5000,     # Máximo de hechos semánticos
    "vector_dim": 256,          # (reservado para embeddings)
    "similarity_top_k": 5,      # Resultados por búsqueda
    "decay_rate": 0.99,         # Decaimiento de recuerdos antiguos
}
```

---

## Aprendizaje

```python
LEARNING = {
    "pattern_extraction": True,  # Extraer patrones procedurales
    "concept_mining": True,      # Extraer conceptos
    "reinforcement": True,       # Reforzar con feedback
    "auto_skill_create": False,  # Crear skills automáticamente
    "feedback_tracking": True,   # Rastrear feedback del usuario
}
```

---

## Interfaz

```python
INTERFACE = {
    "type": "cli",    # "cli" | "api"
    "cli": {
        "prompt": "Nexus> ",
        "max_history": 1000,
        "colors": True,
    },
    "api": {
        "host": "127.0.0.1",
        "port": 8712,
    }
}
```

---

## Cambiar de modelo

Editar `config.py`:

```python
# Para usar llama3.2:3b (más potente, más lento)
ENGINE["llm"]["model_name"] = "llama3.2:3b"

# Para desactivar el SLM y usar solo simbólico
ENGINE["mode"] = "symbolic"

# Para usar un servidor OpenAI compatible
ENGINE["llm"]["backend"] = "openai"
ENGINE["llm"]["api_base"] = "http://tu-servidor:8000/v1"
ENGINE["llm"]["api_key"] = "tu-api-key"
```
