# 06 — Aprendizaje: Extractor y Sinónimos

> **Sistema de extracción automática de hechos + expansión de queries con sinónimos.**
> Dos archivos: `learning/extractor.py` y `learning/synonyms.py`.

---

## A) Extractor Automático (`learning/extractor.py`)

> *"Extrae hechos de CADA interacción para que Qwen 0.5B se vuelva PRO conversación tras conversación."*
>
> A diferencia de v1, este extractor es mucho más agresivo: aprende de todo — preguntas, respuestas, afirmaciones, negaciones.

### `extract_facts(text)` — Patrones de extracción

Extrae hechos del texto usando todos los patrones. Devuelve lista de strings.

**Patrones principales (no exhaustivo):**

| Patrón | Ejemplo de entrada | Hecho extraído |
|--------|-------------------|----------------|
| `me llamo X` / `mi nombre es X` | "me llamo Jose" | "El usuario se llama Jose" |
| `vivo en X` | "vivo en Santiago" | "El usuario vive en Santiago" |
| `trabajo en X` | "trabajo en Acme SA" | "El usuario trabaja en Acme SA" |
| `tengo X años` | "tengo 35 años" | "El usuario tiene 35 años" |
| `X es Y` | "la capital de Chile es Santiago" | "La capital de Chile es Santiago" |
| `se llama X` | "el lenguaje se llama Python" | "El lenguaje se llama Python" |
| `me gusta X` | "me gusta el cafe" | "Al usuario le gusta el cafe" |
| `prefiero X` | "prefiero el té" | "El usuario prefiere el té" |
| `siempre X` | "siempre llego tarde" | "El usuario siempre llega tarde" |
| `nunca X` | "nunca como carne" | "El usuario nunca come carne" |
| `pienso que X` | "pienso que la IA es util" | "El usuario piensa que la IA es util" |
| `creo que X` | "creo que va a llover" | "El usuario cree que va a llover" |

> Las negaciones (`no es`, `nunca`, `jamás`) se conservan como hecho negativo.

---

### `learn_from_all(text, memory, source)` — Aprender de todo

Aprende de CUALQUIER texto: preguntas, respuestas, afirmaciones.

```python
learn_from_all(user_input, memory, source="usuario")
learn_from_all(response, memory, source="respuesta")
```

**Filtros aplicados:**
- Hechos muy cortos (< 10 chars) → descartados
- Hechos duplicados exactos → descartados
- Hechos con palabras exclusivamente de stopwords → descartados

**Metadata:**
- `category="aprendido_usuario"` o `"aprendido_respuesta"` o `"correccion"`
- `confidence=0.5` (base, sube con refuerzo)
- `source=source`

---

### `detect_feedback(text)` — Detección de feedback

Detecta si el usuario está dando feedback positivo o negativo.

**Patrones positivos** → retorna `"reforzar"`:
- "si", "correcto", "exacto", "asi es", "perfecto", "muy bien", "bien", "ok", "bueno", "gracias", "eso es", "efectivamente", "claro que si", "por supuesto"

**Patrones negativos** → retorna `"rechazar"`:
- "no", "incorrecto", "mal", "equivocado", "no es asi", "estas mal", "no es cierto", "falso", "mentira", "error", "no es verdad", "ese no es"

**Sin match** → retorna `"ninguno"`.

---

### `handle_feedback(text, memory)` — Procesar feedback

Procesa feedback del usuario: refuerza o rechaza hechos recientes.

**Algoritmo:**
1. Detectar tipo de feedback
2. Si es reforzar → los hechos mencionados en el mensaje ganan `+0.1` de confianza
3. Si es rechazar → los hechos mencionados pierden `0.2` de confianza
4. Si la confianza cae a < 0.1 → el hecho se elimina

Retorna `True` si se realizó alguna acción.

---

## B) Diccionario de Sinónimos (`learning/synonyms.py`)

> *"Mapea palabras equivalentes para expandir queries y mejorar la búsqueda en memoria semántica."*
>
> Cuando el usuario pregunta por "auto", también debe encontrar hechos guardados como "coche", "carro", "vehículo".

### `get_synonyms(word)` — Lista de sinónimos

Devuelve la lista de sinónimos de una palabra. Si no está en el diccionario, devuelve `[word]`.

**Ejemplos de grupos sinonímicos** (extracto):

```
auto, coche, carro, vehículo, automovil
feliz, contento, alegre, dichoso
triste, melancolico, deprimido
casa, hogar, residencia, domicilio
trabajo, empleo, labor, oficio
dinero, plata, efectivo, lana, luca
computador, computadora, pc, ordenador
celular, telefono, movil, smartphone
chico, pequeno, bajo, reducido
grande, enorme, gigante, amplio
bonito, lindo, bello, hermoso
feo, horrible, desagradable
rapido, veloz, agil, pronto
lento, pausado, tardio
amigo, companero, colega
estudiar, aprender, investigar
```

### `expand_query(query)` — Expandir query

Genera variantes de la query agregando sinónimos de sus términos clave.

**Ejemplo:**
```python
"que es python"
# → ['que es python', 'definicion python', 'significado python', 'que significa python']
```

**Algoritmo:**
1. Tokenizar la query
2. Para cada palabra clave (>3 letras, no stopword):
   - Buscar sinónimos en el diccionario
   - Generar variantes reemplazando la palabra original por cada sinónimo
3. Devolver lista de queries alternativas (max 5)

### `expand_fact_storage(fact)` — Expandir al guardar

Genera sinónimos de un hecho para guardarlo en memoria.

**Lógica:**
- Si el hecho contiene "auto", también se guarda como sinónimo "coche" (con menos confianza) para mejorar la búsqueda.
- Cada variante tiene `confidence *= 0.8` (penalización por ser derivado, no original).

**Returns:** Lista de hechos alternativos (con sinónimos).

---

## Filosofía

> *"Con sinonimos el sistema entiende más sin necesitar embeddings."*
> *"Visión: Inteligencia por arquitectura, no por tamaño"*

El extractor + sinónimos son el **cerebro lateral** de Nexus: permiten que un sistema pequeño (incluso sin embeddings) tenga búsqueda semántica decente.
