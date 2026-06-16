# Sistema de Aprendizaje

Nexus aprende de cada interacción. El aprendizaje es automático y progresivo: cada conversación lo vuelve más inteligente.

## Fuentes de Aprendizaje

```
Usuario escribe algo
  ↓
Motor genera respuesta
  ↓
Extractor analiza el texto del usuario
  ↓
¿Encontró un hecho? (ej: "el riñón filtra la sangre")
├── Sí → MemoriaSemántica.learn_fact(confianza: 0.2)
└── No → se ignora (no todo lo que dice el usuario son hechos)

¿Usuario confirmó? (ej: "correcto", "sí", "exacto")
├── Sí → Refuerza hechos recientes (confianza sube)
└── No → nada
```

---

## Extractor Automático (`learning/extractor.py`)

Extrae hechos del texto del usuario usando patrones regex en español.

### Patrones de extracción

| Patrón | Ejemplo | Captura |
|---|---|---|
| `X es/son Y` | "el sol es una estrella" | "sol estrella" |
| `X significa Y` | "fotosíntesis significa convertir luz" | "fotosíntesis convertir luz" |
| `X se usa para Y` | "el láser se usa para cortar" | "láser cortar" |
| `X tiene/contiene Y` | "el sistema solar contiene planetas" | "sistema solar planetas" |
| `X está compuesto por Y` | "el agua está compuesta por H2O" | "agua H2O" |
| `X ocurre cuando Y` | "la lluvia ocurre cuando se condensa" | "lluvia se condensa" |
| `X hace/realiza Y` | "el corazón realiza bombeo" | "corazón bombeo" |
| `X produce/genera Y` | "las plantas producen oxígeno" | "plantas oxígeno" |
| `X filtra/transporta Y` | "el riñón filtra la sangre" | "riñón sangre" |
| `X necesita Y para Z` | "el cuerpo necesita vitaminas para funcionar" | "cuerpo vitaminas funcionar" |
| `X ayuda/permite Y` | "la vitamina C ayuda a la defensa" | "vitamina C defensa" |
| `X funciona mediante Y` | "el motor funciona mediante combustión" | "motor combustión" |

### Verbos soportados (plural y singular)

- **Acción**: hace, hacen, realiza, realizan, ejecuta, ejecutan
- **Producción**: produce, producen, genera, generan, crea, crean, convierte, convierten, transforma, transforman, fabrica, fabrican
- **Biológicos**: filtra, filtran, absorbe, absorben, transporta, transportan, elimina, eliminan, expulsa, expulsan, bombea, bombean, limpia, limpian
- **Necesidad**: necesita, necesitan, requiere, requieren, utiliza, utilizan, usa, usan, ocupa, ocupan
- **Ayuda**: ayuda, ayudan, permite, permiten, contribuye, contribuyen, sirve, sirven
- **Funcionamiento**: funciona, funcionan, opera, operan, trabaja, trabajan

---

## Reforzamiento por Feedback

El usuario puede reforzar hechos recientes con palabras de confirmación:

**Palabras de refuerzo**: correcto, exacto, bien, sí, si, cierto, claro, bueno, vale, de acuerdo, ok, okay, perfecto

Cuando el usuario dice "correcto", los 3 hechos más recientes de la categoría "aprendizaje" se refuerzan (confidence +0.1).

---

## Conocimiento Inicial

Para que el sistema no arranque "en blanco", se cargan hechos desde archivos JSON en `data/knowledge/`.

**Proceso** (`knowledge/loader.py`):
1. Escanea `data/knowledge/*.json`
2. Para cada archivo, carga los hechos en memoria semántica
3. Asigna `confidence=0.5` y `source="knowledge_base"`

**Crear nuevo conocimiento**:
```json
[
  {
    "fact": "La capital de Chile es Santiago",
    "category": "geografia",
    "source": "knowledge_base"
  }
]
```

---

## Flujo Completo de Aprendizaje

```
Usuario: "el riñón filtra la sangre"
  ↓
Motor simbólico responde genéricamente
  ↓
extract_facts_from_text("el riñón filtra la sangre")
  → encuentra: "riñón sangre" (patrón: X filtra Y)
  → learn_fact("riñón sangre", categoria="aprendizaje", confidence=0.2)
  ↓
[Próxima vez] Usuario: "¿qué hace el riñón?"
  → query_knowledge("qué hace el riñón")
  → términos significativos: ["riñón"]
  → encuentra: "riñón sangre" (score: 1.0)
  → Responde: "Según lo que he aprendido: riñón sangre..."
```

---

## Limitaciones Actuales

1. **Los hechos extraídos no son perfectos**: a veces incluyen palabras extra ("la", "por", "a")
2. **El extractor solo captura ciertos patrones gramaticales**: frases con otros verbos no se capturan
3. **No se aprende de respuestas del SLM**: porque Qwen 0.5B a veces da respuestas incorrectas
4. **No hay verificación de hechos**: el sistema confía en que lo que el usuario dice es correcto
