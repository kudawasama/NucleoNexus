# Capa Cognitiva

La capa cognitiva es el cerebro de Nexus. Decide cómo procesar cada mensaje, qué contexto inyectar, y qué backend usar.

## Componentes

```
Capa Cognitiva
├── SymbolicEngine  → Motor simbólico (pattern matching + TF-IDF)
├── SLMBackend      → Modelo local (Ollama / qwen2.5:0.5b)
└── ContextBuilder  → Constructor de contexto para el SLM
```

---

## Motor Simbólico (`cognition/symbolic.py`)

**Propósito**: Responder sin necesidad de un LLM. Usa pattern matching, memoria y reglas.

### Detección de Intenciones

El motor detecta qué quiere el usuario mediante regex:

| Intención | Patrón | Ejemplo |
|---|---|---|
| `saludo` | hola, buenas, hey, saludos | "Hola" |
| `despedida` | adiós, chao, bye, nos vemos | "Chao" |
| `agradecimiento` | gracias, thank | "Gracias" |
| `presentacion` | quién eres, qué puedes hacer | "¿Quién eres?" |
| `estado` | estado, cómo estás | "¿Cómo estás?" |
| `hora` | hora, qué hora es | "¿Qué hora es?" |
| `calcular` | cuanto es, calcula, suma | "2+2" |
| `fase` | fase, evolución, nivel | "¿En qué fase estás?" |
| `ayuda` | ayuda, help, comandos | "Ayuda" |
| `clima` | clima, temperatura, santiago | "¿Cómo está en Santiago?" |
| `memoria` | recuerdas, memoria | "¿Qué recuerdas?" |
| `nombre` | cómo me llamo, quién soy | "¿Sabes mi nombre?" |
| `aprender` | aprende, enseña, nuevo | "Aprende que..." |
| `reset` | reset, reiniciar | "Reset" |
| `personalidad` | personalidad, tono, estilo | "Cambia tu tono" |
| `confianza` | confianza, qué tanto sabes | "¿Cuánto sabes?" |
| `conversacion` | (ninguno de los anteriores) | "¿Qué opinas de...?" |

### Procesamiento (`process()`)

```
1. Detectar llamado de acción [[accion:...]]
2. Detectar intención
3. Buscar en memoria episódica (TF-IDF)
4. Buscar hechos en memoria semántica
5. Generar respuesta según intención + contexto
6. Aprender de la interacción
7. Registrar en memoria episódica
8. Actualizar estado
```

### Handlers de intención

Cada intención tiene su propio handler:
- `_handle_greeting()` → frases de saludo según la fase
- `_handle_farewell()` → frases de despedida
- `_handle_status()` → estado del sistema (uptime, fase, stats)
- `_handle_calculate()` → evalúa expresiones matemáticas
- `_handle_time()` → hora actual con time.localtime()
- `_handle_conversation()` → búsqueda en memoria + respuesta genérica

---

## Backend SLM (`cognition/slm.py`)

**Propósito**: Conectar modelos de lenguaje pequeños locales (Ollama, llama.cpp, OpenAI).

### Modos de conexión

| Modo | Descripción |
|---|---|
| `ollama` | Se conecta a servidor Ollama local (puerto 11434) |
| `llamacpp` | Ejecuta llama-server con un modelo GGUF |
| `openai` | API compatible OpenAI (cualquier endpoint) |

### Ciclo de vida

```python
slm = SLMBackend(config)  # Constructor (no conecta)
slm.load()                # Conecta con Ollama
slm.generate(prompt)      # Genera respuesta
slm.unload()              # Desconecta
```

---

## Constructor de Contexto (`cognition/context.py`)

**Propósito**: Construir el prompt de sistema que se inyecta al SLM antes de cada respuesta.

### Modo completo (para modelos medianos/grandes)

```
Eres Nexus, un sistema de IA en evolución.
Personalidad: analítica, precisa...
=== MEMORIA RELEVANTE ===
[Recuerdos similares]
[Hechos relevantes]
[Últimos mensajes]
=== SKILLS DISPONIBLES ===
→ get_weather: Obtiene el clima
→ get_time: Obtiene la hora
=== DIRECTIVAS ===
Fase: Intermedio | Confianza: 20%
Directivas según fase...
```

### Modo ligero (para Qwen 0.5B)

```
Eres Nexus, un asistente conversacional en fase Intermedio.
=== MEMORIA RELEVANTE ===
[Recuerdos similares si existen]
[Hechos relevantes si existen]
=== INSTRUCCIONES ===
- Responde en español, claro y directo
- Si no sabes algo, dilo honestamente
- NO inventes datos ni horarios
- Usa el contexto de memoria si es relevante
- Mantén respuestas cortas y naturales
```

El modo ligero **omite** la lista de skills y las directivas complejas de fase, porque los modelos pequeños se confunden con tanta información.

---

## Modo Híbrido: Cómo se conectan

```
SymbolicEngine.detect_intent() → ¿Fast intent?
├── Sí: SymbolicEngine.process() → respuesta instantánea
└── No: SemanticMemory.query_knowledge() → ¿Hechos?
        ├── Sí: SymbolicEngine.process() → respuesta desde memoria
        └── No: ContextBuilder.build(light_mode=True)
                 → SLMBackend.generate() → respuesta generada
                 → (aprendizaje automático del contenido)
```

El modo híbrido es el cerebro del sistema: usa cada componente para lo que mejor sabe hacer.
