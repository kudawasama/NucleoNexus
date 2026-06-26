# 05 — Aprendizaje Few-Shot (`learning/few_shot.py`)

> **Dataset de entrenamiento + instrucciones para Qwen 0.5B.**
> Enseña al SLM pequeño a usar herramientas: cada ejemplo muestra entrada → JSON con acción.

---

## Descripción de herramientas (`TOOLS_DESCRIPTION`)

```
HERRAMIENTAS DISPONIBLES:
- web_search(query): Busca informacion actualizada en internet
- calcular(expresion): Resuelve operaciones matematicas
- buscar_memoria(tema): Busca hechos en mi base de conocimiento
- hora_actual(): Devuelve la fecha y hora actual
- pdf_rename(path): Renombra facturas PDF con formato NUMERO - PROVEEDOR - MES AÑO
```

---

## Instrucciones (inyectadas antes de los ejemplos)

```
INSTRUCCIONES:
1. Si te preguntan algo que NO sabes → usa web_search
2. Si te piden un calculo → usa calcular
3. Si te preguntan de un tema que estudiamos → usa buscar_memoria
4. Si te preguntan la hora → usa hora_actual
5. Si te piden renombrar facturas PDF → usa pdf_rename
6. Si sabes la respuesta → usa accion: responder

RESPONDE SIEMPRE EN ESTE FORMATO JSON:
{"razonamiento": "...", "accion": "responder|web_search|calcular|buscar_memoria|hora_actual|pdf_rename", "respuesta": "...", "query": "...", "path": "..."}

=== EJEMPLOS ===
```

---

## Esquema JSON esperado

```json
{
  "razonamiento": "...",
  "accion": "responder|web_search|calcular|buscar_memoria|hora_actual|pdf_rename",
  "respuesta": "...",
  "query": "...",            // solo si accion=web_search o buscar_memoria
  "expresion": "...",        // solo si accion=calcular
  "path": "...",             // solo si accion=pdf_rename
  "dry_run": true|false      // solo si accion=pdf_rename
}
```

---

## Ejemplo 1 — Responder (conocimiento directo)

```
Pregunta: explicame como se hace una multiplicacion
JSON: {"razonamiento": "El usuario pregunta sobre multiplicacion. Puedo responder con mi conocimiento.", "accion": "responder", "respuesta": "Multiplicar es sumar un numero varias veces. 3x4 significa sumar 3 cuatro veces: 3+3+3+3 = 12."}
```

---

## Ejemplo 2 — Buscar en web

```
Pregunta: quien gano el partido de chile ayer
JSON: {"razonamiento": "No tengo informacion actualizada sobre deportes. Debo buscar en internet.", "accion": "web_search", "query": "resultado partido Chile ayer", "respuesta": ""}
```

---

## Ejemplo 3 — Calcular

```
Pregunta: cuanto es 15 por 7
JSON: {"razonamiento": "El usuario pide un calculo. Puedo usar la calculadora.", "accion": "calcular", "expresion": "15*7", "respuesta": ""}
```

---

## Ejemplo 4 — Buscar en memoria

```
Pregunta: que sabe sobre fotosintesis
JSON: {"razonamiento": "Pregunta sobre un tema que podria estar en mi memoria semantica.", "accion": "buscar_memoria", "query": "fotosintesis", "respuesta": ""}
```

---

## Ejemplo 5 — Hora actual

```
Pregunta: que hora es
JSON: {"razonamiento": "El usuario pregunta la hora actual.", "accion": "hora_actual", "respuesta": ""}
```

---

## Ejemplo 6 — Renombrar PDFs

```
Pregunta: renombra los PDFs de la carpeta C:/facturas
JSON: {"razonamiento": "El usuario quiere renombrar facturas PDF. Debo usar la herramienta pdf_rename.", "accion": "pdf_rename", "path": "C:/facturas", "dry_run": true, "respuesta": ""}
```

---

## Ejemplo 7 — No sabe (ser honesto)

```
Pregunta: cual es la capital de mongolia
JSON: {"razonamiento": "No estoy seguro de la capital de Mongolia. Podria buscar en web o ser honesto.", "accion": "responder", "respuesta": "No tengo esa informacion. Puedes decirme y lo recordare."}
```

---

## Prompt final (cierre)

```
=== FIN EJEMPLOS ===

AHORA RESPONDE LA SIGUIENTE PREGUNTA EN JSON:
```

---

## Funciones de construcción

### `build_tools_prompt()`

Devuelve el bloque completo:
```
TOOLS_DESCRIPTION + "" + INSTRUCCIONES + "" + ESQUEMA + "=== EJEMPLOS ===" + ejemplos formateados + "=== FIN EJEMPLOS ===" + "AHORA RESPONDE..."
```

### `build_few_shot_prompt()`

Solo los ejemplos (compatibilidad con código anterior).

---

## Filosofía

> *"Enseña a Qwen 0.5B a usar herramientas: buscar en web, calcular, consultar memoria."*
> *"El sistema ejecuta la accion y Qwen da la respuesta final."*

Cada ejemplo sigue el patrón:
1. **Pregunta natural** del usuario
2. **Razonamiento** corto (por qué elige esa acción)
3. **Acción** en formato JSON estricto
4. **Respuesta** (vacía si delegará al sistema, llena si responde directo)
