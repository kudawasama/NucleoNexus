# 04 — Motor Simbólico (`cognition/symbolic.py`)

> **SymbolicEngine** — Motor de IA puramente simbólico. No necesita GPU, no necesita modelo.
> Modo de arranque — cuando no hay SLM cargado, Nexus piensa así.

---

## Capacidades

- Reconocimiento de intenciones por palabras clave
- Respuestas desde frases plantilla que mejoran con la fase
- Búsqueda en memoria semántica para responder con hechos
- Aprendizaje: extrae patrones de las preguntas del usuario

---

## Comandos reconocidos (patrones regex)

| Intención | Patrones que la disparan |
|-----------|--------------------------|
| **Saludo** | `hola`, `buenos dias`, `buenas tardes`, `buenas`, `que tal`, `cómo estás` |
| **Presentación** | `quien eres`, `que eres`, `qué eres`, `presentate`, `capacidades`, `que puedes hacer`, `qué puedes hacer`, `que sabes hacer` |
| **Estado del sistema** | `como estas`, `que tal estas`, `como te va`, `como andas` |
| **Fase / Progreso** | `en que fase`, `que fase`, `fase actual`, `progreso`, `evolucion`, `evolución` |
| **Confianza** | `confianza`, `nivel de confianza`, `que tan confiable` |
| **Personalidad** | `personalidad`, `tu tono`, `que personalidad`, `cambia tu tono`, `tono a friendly`, `personalidad más creativa` |
| **Ayuda / Comandos** | `ayuda`, `help`, `comandos`, `que puedo hacer`, `como te uso` |
| **Memoria** | `que recuerdas`, `mis recuerdos`, `que te dije`, `historial` |
| **Aprender** | `aprende que`, `recuerda que`, `te enseno`, `anota que` |
| **Reset** | `reset`, `reiniciar`, `borrar todo` |
| **Cambiar fase** | `cambia a fase X` |
| **Llamar skill** | `[[accion:nombre(param)]]` |

---

## Plantilla: Presentación

```
Soy **Nucleo Nexus**, un sistema de IA en evolucion progresiva.

· Fase actual: {phase}
· Backend: {backend}
· Skills cargadas: {skills_count}

**Mis capacidades actuales:**
  • Aprendizaje incremental — aprendo de cada interaccion
  • Memoria persistente — recuerdo lo que me ensenas
  • Deteccion de intenciones — entiendo saludos, preguntas, comandos
  • Evolucion por fases — mejoro con el uso (Proto -> Pro)
  • Personalidad ajustable — cambio mi tono y estilo
  • Skills modulares — puedo ejecutar funciones
  • SLM-Ready — cuando actives un modelo local, pienso mejor

Puedes ensenarme cosas con: 'aprende que [algo]'
Ver mi progreso con: /fase
Ver mi estado con: /status
Cambiar mi personalidad con: /personalidad
```

---

## Plantilla: Estado de fase (con barra de progreso)

```
📊 **Fase actual: {phase}**
Interacciones: {n}
Progreso: [{████████░░░░░░░░░░░░]
Próxima fase: {next_phase}
Interacciones restantes: {remaining}

Cada conversación me acerca a la siguiente fase. ¡Sigue
interactuando para verme evolucionar!
```

### Umbrales de fase

| Fase | Trigger | Comportamiento |
|------|---------|----------------|
| **Proto** | inicial | Frases cortas, aprende patrones básicos |
| **Básico** | > 10 interacciones | Usa skills, muestra personalidad |
| **Intermedio** | > 50 | Razonamiento multicapa |
| **Avanzado** | > 200 | Análisis profundo, aprendizaje autodirigido |
| **Pro** | > 500 | Operación autónoma, creatividad plena |

---

## Plantilla: Personalidad

```
Mi personalidad actual:
  · Tono: {tone}
  · Formalidad: {formality:.0%}
  · Curiosidad: {curiosity:.0%}
  · Creatividad: {creativity:.0%}

Puedes cambiarla con 'cambia tu tono a friendly' o
'personalidad más creativa'.
```

### Tonos soportados

`analytical` (default), `friendly`, `playful`, `professional`.

---

## Plantilla: Confianza

```
Mi nivel de confianza actual: {confidence:.1%}
[████████░░░░░░░░░░░░]
Interacciones: {n}

La confianza sube con cada interacción exitosa.
Al llegar a 100%... algo especial podría pasar.
```

---

## Plantilla: Ayuda

```
Comandos disponibles:
  · Hola / Buenos días — Saludo
  · ¿Quién eres? — Presentación
  · ¿Cómo estás? — Estado del sistema
  · ¿En qué fase estás? — Progreso de evolución
  · Aprende que... — Enseñarme algo nuevo
  · Personalidad — Ajustar mi tono
  · ¿Qué sabes de X? — Consultar mi memoria
  · Reset — Reiniciar mi estado
  · [[accion:nombre(param)]] — Llamar una skill directamente

Sugerencia: mientras más hables conmigo, más inteligente me vuelvo.
```

---

## Plantilla: Memoria (recuerdos recientes)

```
📝 **Mis recuerdos recientes:**

🧑 Tú: ...
🤖 Nexus: ...
🧑 Tú: ...
🤖 Nexus: ...
🧑 Tú: ...
```

> Top 5 últimos, en orden cronológico inverso, truncados a 80 chars.

---

## Plantilla: Reset (confirmación)

```
¿Estás seguro de que quieres reiniciarme? Perdería todo lo aprendido.
Si es así, escribe: 'confirmo reset'
```

> No resetea automáticamente. Requiere confirmación explícita.

---

## Plantilla: Memoria vacía

```
Aún no tengo recuerdos. Háblame para que empiece a recordar.
```

---

## Síntesis de items de búsqueda

Cuando el motor simbólico responde con resultados de búsqueda o memoria, los formatea como:

```
He encontrado información relevante:

1. Primer item encontrado
2. Segundo item encontrado
3. Tercer item encontrado

(Si hay más, indica que hay N resultados adicionales)
```

> Items: top 5, máximo 200 chars cada uno.

---

## Filosofía

> *"Motor de IA puramente simbólico. No necesita GPU, no necesita modelo."*

Usa:
- Pattern matching para respuestas inmediatas
- TF-IDF + memoria para respuestas contextuales
- Reglas extraídas de interacciones previas
- Sistema de confianza para mejorar con el tiempo
