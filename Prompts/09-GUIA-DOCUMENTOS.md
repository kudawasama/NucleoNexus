# 09 — Guía de Documentos (`knowledge/guide.py`)

> **Generador de guías estructuradas a partir de documentos ingeridos en memoria.**
> Genera resúmenes ejecutivos, FAQ, timeline y conceptos clave.

---

## System prompt principal (`GUIDE_SYSTEM_PROMPT`)

```
Eres un analista de documentos experto.
Genera guías estructuradas basadas SOLO en el contenido del documento proporcionado.
NO inventes información que no esté en el documento.
Responde SIEMPRE en español.

Genera los siguientes formatos:

1. BRIEFING (resumen ejecutivo):
   - Propósito del documento
   - 3-5 puntos clave
   - Conclusión principal

2. FAQ (3-5 preguntas frecuentes):
   Cada pregunta con su respuesta basada en el documento.

3. CONCEPTOS CLAVE:
   Lista de términos importantes con definición breve.

4. TIMELINE (si aplica):
   Eventos en orden cronológico encontrados en el documento.

Formato de respuesta:
{
  "titulo": "Título del documento",
  "briefing": "resumen ejecutivo...",
  "faq": [{"pregunta": "...", "respuesta": "..."}],
  "conceptos": [{"termino": "...", "definicion": "..."}],
  "timeline": [{"fecha": "...", "evento": "..."}]
}
```

---

## `generate_guide(slm, memory, titulo, max_chunks=10)`

Genera una guía completa a partir de un documento en memoria.

**Algoritmo:**

1. Buscar chunks del documento: `memory.query_knowledge(titulo, top_k=max_chunks)`
2. Si no hay chunks → retorna `None`
3. Construir contexto:
   ```
   === DOCUMENTO: {titulo} ===
   --- Sección 1 ---
   {texto_chunk_1, max 500 chars}
   --- Sección 2 ---
   {texto_chunk_2, max 500 chars}
   ...
   === FIN DEL DOCUMENTO ===
   ```
4. Llamar al SLM con `system_prompt=GUIDE_SYSTEM_PROMPT`
5. Intentar parsear como JSON
6. Si falla el parseo → devolver como texto plano en `briefing` con flag `_raw: true`

**Returns:** Dict con la guía parseada o `None`.

---

## `generate_faq(slm, topic, memory, num_questions=3)`

Genera FAQ sobre un tema específico usando memoria disponible.

**System prompt para FAQ:**
```
Basado en esta información:
{context}

Genera {num_questions} preguntas frecuentes con sus respuestas.
Formato JSON: [{"pregunta": "...", "respuesta": "..."}]
Responde solo con el JSON, nada más.
```

**Algoritmo:**

1. Buscar hechos relevantes: `memory.query_knowledge(topic, top_k=5)`
2. Si no hay hechos → retorna `None`
3. Construir contexto con bullets de hechos (max 200 chars cada uno)
4. Llamar al SLM
5. Parsear como JSON

**Returns:** Lista de dicts `{pregunta, respuesta}` o `None`.

---

## Reglas de comportamiento

- **Solo información del documento**: NO inventa, NO completa con conocimiento externo.
- **Responde SIEMPRE en español**.
- **Formato JSON estricto** (validado post-generación).
- **Si la respuesta no es JSON válido** → fallback a texto plano con flag `_raw: true`.

---

## Filosofía

> *"Genera guías estructuradas basadas SOLO en el contenido del documento proporcionado."*

El modelo es un **asistente de análisis**, no un generador de contenido. La fuente de verdad siempre es el documento original.
