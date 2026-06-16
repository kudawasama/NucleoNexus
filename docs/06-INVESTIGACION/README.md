# Investigación: Técnicas para Potenciar LLMs Pequeños

Esta sección documenta la investigación sobre métodos para hacer que un LLM pequeño (0.5B - 3B) se comporte como uno mucho más grande mediante arquitectura de sistema.

---

## 1. ReAct (Reasoning + Acting)

**Paper**: [*"ReAct: Synergizing Reasoning and Acting in Language Models"*](https://arxiv.org/abs/2210.03629) — Yao et al., 2022

### Idea principal

El modelo no solo genera texto, sino que **piensa en voz alta** (Thought) y **decide acciones** (Action) en un ciclo:

```
Thought:  Necesito saber qué es la fotosíntesis.
Action:   buscar_memoria("fotosíntesis")
Observation: La fotosíntesis convierte luz solar en energía química.
Thought:  Ahora tengo la información. Puedo responder.
Response: La fotosíntesis es el proceso...
```

### Por qué funciona con modelos pequeños

El formato estructurado obliga al modelo a razonar paso a paso. Modelos de 1B con ReAct superan a modelos de 7B sin él. La estructura reduce alucinaciones porque el modelo "piensa" antes de responder.

### Implementación propuesta para Nexus

En el `ContextBuilder._build_light_directives()`, cambiar las instrucciones por:

```
Formato de respuesta:
Pensamiento: (razona qué necesitas para responder)
Acción: (ninguna | buscar_memoria | calcular | aprender)
Datos: (argumentos si aplica)
Respuesta: (tu respuesta al usuario)
```

---

## 2. Toolformer / Tool Calling

**Papers**: 
- [*Toolformer: Language Models Can Teach Themselves to Use Tools*](https://arxiv.org/abs/2302.04761) — Schick et al., 2023
- [*Gorilla: Large Language Model Connected with Massive APIs*](https://arxiv.org/abs/2305.15334) — Patil et al., 2023

### Idea principal

El modelo se fine-tunea para generar tokens especiales que invocan APIs:

```
La fotosíntesis es el proceso de 
[TOOL_CALL: buscar_memoria("fotosíntesis") → "convertir luz en energía"]
convertir luz en energía química.
```

### Para Nexus

Fine-tuning con LoRA de Qwen 0.5B para que aprenda tu formato específico:
- `[[accion:buscar_memoria(query)]]` 
- `[[accion:calcular(expresion)]]`
- `[[accion:aprender(hecho)]]`

**Requisitos**: 
- ~4GB de RAM para fine-tuning LoRA de 0.5B
- Dataset pequeño (~100 ejemplos de tool use)
- ~1 hora de entrenamiento

---

## 3. MemGPT (Virtual Context Management)

**Paper**: [*"MemGPT: Towards LLMs as Operating Systems"*](https://arxiv.org/abs/2310.08560) — Packer et al., 2023

### Idea principal

El LLM gestiona su propia memoria como un SO: contexto principal (RAM), memoria archivística (disco). El modelo decide cuándo leer y escribir.

### Para Nexus

Ya tienes la infraestructura (memoria semántica y episódica). Falta que el **modelo mismo decida** cuándo consultar memoria:

```
Pensamiento: El usuario preguntó algo que no sé.
             Debo buscar en mi memoria semántica.
Acción: buscar_memoria("tema")
```

Actualmente el sistema decide por él (ruteo híbrido). La evolución es que Qwen decida autónomamente.

---

## 4. DSPy (Optimización de Prompts)

**Paper**: [*"DSPy: Compiling Declarative Language Model Calls"*](https://arxiv.org/abs/2310.03714) — Khattab et al., 2023

### Idea principal

En lugar de escribir prompts a mano, defines el **comportamiento** y DSPy optimiza el prompt automáticamente para tu modelo específico.

### Para Nexus

Usar DSPy para optimizar el prompt de Qwen 0.5B:
- ¿Qué instrucciones entiende mejor?
- ¿Qué formato de ReAct funciona?
- ¿Cuántos ejemplos necesita?

---

## 5. Structured Generation

**Librerías**: 
- [Outlines](https://github.com/outlines-dev/outlines)
- [Guidance](https://github.com/guidance-ai/guidance)
- [LMQL](https://lmql.ai/)

### Idea principal

Forzar al modelo a generar solo dentro de un formato específico (JSON, tool calls, regex). Para modelos pequeños esto es crítico porque evita que "se salgan del formato".

### Para Nexus

```python
# Esquema para la respuesta de Qwen
esquema = {
    "tipo": "busqueda | respuesta | calculo",
    "contenido": "string",
    "confianza": 0.0 a 1.0
}
```

Con structured generation, Qwen 0.5B solo puede generar JSON válido con este esquema.

---

## 6. Self-Consistency y Chain-of-Thought

**Paper**: [*"Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"*](https://arxiv.org/abs/2201.11903) — Wei et al., 2022

**Paper**: [*"Self-Consistency Improves Chain of Thought Reasoning"*](https://arxiv.org/abs/2203.11171) — Wang et al., 2022

### Idea principal

El modelo genera múltiples respuestas y elige la más consistente. Para modelos pequeños, esto mejora precisión aunque sea más lento.

### Para Nexus

Generar 2-3 respuestas con Qwen y elegir la más frecuente. Implementación simple: llamar a `generate()` 2 veces y comparar.

---

## 7. Aprendizaje por Refuerzo con Memoria

### Idea principal

- El sistema genera respuesta
- Usuario reacciona (explícito o implícito)
- Respuestas exitosas → se guardan en memoria procedural
- Respuestas fallidas → se descartan o se marcan

### Para Nexus

Ya tienes `reinforce_from_feedback()`. La evolución es:
- Respuestas que el usuario ignora → baja confianza
- Respuestas que el usuario repite/pregunta de nuevo → sube confianza
- Detección de frustración (usuario pregunta lo mismo dos veces)

---

## Roadmap de Implementación

| Prioridad | Técnica | Esfuerzo | Impacto | Estado |
|---|---|---|---|---|
| 1 | **ReAct en prompt** | Bajo | Alto | Pendiente |
| 2 | **Structured generation** (Guidance) | Medio | Alto | Pendiente |
| 3 | **Auto-memoria** (modelo decide) | Medio | Medio | Pendiente |
| 4 | **Fine-tuning LoRA** | Medio | Muy alto | Investigación |
| 5 | **Self-consistency** | Bajo | Medio | Pendiente |
| 6 | **DSPy optimization** | Medio | Medio | Pendiente |
