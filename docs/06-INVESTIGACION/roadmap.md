# Roadmap de Mejoras Futuras

Priorizadas por impacto vs esfuerzo.
Estado actualizado segun trabajo real (commits recientes).

## Fase 1: Proximo (Alto impacto, bajo esfuerzo)

### [1] Sinonimos + expansion de queries ✅
Diccionario de 60+ sinonimos integrado en query_knowledge.
"auto" ahora encuentra "coche", "medico" encuentra "doctor", etc.

**Archivos**: `learning/synonyms.py`, `memory/semantic.py`
**Estado**: ✅ Implementado (commit `bd7638d`)
**Esfuerzo**: Bajo (~1 hora)
**Impacto**: Alto

### [2] Extractor separa listas en items individuales ✅
El extractor detecta "X son A, B, C" y guarda A, B, C como hechos
individuales, no como texto crudo.

**Archivos**: `learning/extractor.py`
**Estado**: ✅ Implementado (commit `23a3036`)
**Esfuerzo**: Bajo (~30 min)
**Impacto**: Alto

### [3] Auto-aprendizaje desde web ✅
Cuando se hace una busqueda web exitosa, Nexus guarda los resultados
automaticamente en memoria semantica. Vision #4 implementada.

**Archivos**: `main.py`, `cognition/symbolic.py`, `interface/cli.py`
**Estado**: ✅ Implementado (commit `8811b0d`)
**Esfuerzo**: Bajo
**Impacto**: Muy alto

### [4] Comandos de aprendizaje sin SLM (capa rapida) ✅
Comandos directos: /buscar, /aprende, /aprende-web, /recuerda, /analiza,
/olvida, /limpiar-web. No dependen del SLM.

**Archivos**: `interface/cli.py`
**Estado**: ✅ Implementado (commit `084c66c`)
**Esfuerzo**: Bajo
**Impacto**: Alto

### [5] Web search con DuckDuckGo (no GitHub) ✅
Bug fix: GitHub ya no se usa como fallback. DDG HTML ahora
indexa la web general.

**Archivos**: `skills/builtins/tools_skill.py`
**Estado**: ✅ Implementado (commit `daed6df`)
**Esfuerzo**: Bajo
**Impacto**: Alto

### [6] ReAct en el prompt del SLM
Implementar el formato Pensamiento → Accion → Observacion → Respuesta en el prompt ligero del SLM. Esto estructura la salida de Qwen 0.5B y reduce alucinaciones.

**Archivo**: `cognition/context.py` — `_build_light_directives()`
**Esfuerzo**: Bajo (~30 min)
**Impacto**: Alto

### [7] Self-consistency (2 respuestas, elegir mejor) — PARCIAL
Para preguntas importantes, generar 2 respuestas con Qwen y elegir la más coherente.

> **Estado parcial**: Implementado para modo `slm` (commit `bd7638d`).
> Falta aplicar a modo `hybrid` y a las preguntas factuales.

**Archivo**: `main.py` — `_get_response()`
**Esfuerzo**: Bajo (~30 min)
**Impacto**: Medio

### [8] Auto-sintesis en motor simbolico
Cuando hay varios hechos relacionados al tema, sintetizar una
respuesta estructurada en vez de listarlos crudos.

**Ejemplo**: "Los planetas son: Mercurio, Venus, Tierra, Marte"
→ "Encontre 4 planetas: 1) Mercurio, 2) Venus, 3) Tierra, 4) Marte"

**Archivo**: `cognition/symbolic.py` — `_handle_conversation()`
**Esfuerzo**: Bajo (~1 hora)
**Impacto**: Medio

---

## Fase 2: Medio plazo (Alto impacto, esfuerzo medio)

### [9] Fine-tuning LoRA para tool calling
Fine-tunear Qwen 0.5B con LoRA para que aprenda a generar acciones estructuradas (`[[accion:...]]`) de forma nativa.

**Herramientas**: Unsloth, LoRA, dataset de ~100 ejemplos
**Esfuerzo**: Medio (~1-2 días)
**Impacto**: Transformacional

### [10] Structured generation con Guidance
Integrar Guidance o Outlines para forzar la salida del SLM a un formato JSON/acciones valido. Elimina respuestas mal formadas.

> **Estado actual**: Nexus ya usa JSON mode nativo de Ollama (`format: "json"` en la API),
> que es una implementacion parcial de structured generation. Para maxima garantia
> usar Guidance/Outlines.

**Dependencia**: `pip install outlines`
**Esfuerzo**: Medio (~1 dia)
**Impacto**: Alto

### [11] Auto-memoria (modelo decide leer/escribir)
Que el SLM decida autonomamente cuando buscar en memoria, que aprender, y cuando usar herramientas. Actualmente el sistema decide por el.

**Archivos**: `cognition/context.py`, `cognition/slm.py`
**Esfuerzo**: Medio (~1-2 dias)
**Impacto**: Alto

### [12] Comando /agent (encadenar tools automaticamente)
Comando que orquesta tools: web_search + read_file + learn en secuencia.

**Ejemplo**: `/agent investiga quantum computing`
1. web_search "quantum computing"
2. search_files "quantum" en archivos locales
3. read_file de los mas relevantes
4. learn todo en memoria
5. Sintetizar respuesta

**Archivos**: `skills/builtins/agent_skill.py` (nuevo)
**Esfuerzo**: Medio (~2 horas)
**Impacto**: Alto

---

## Fase 3: Largo plazo (Transformacional, esfuerzo alto)

### [13] DSPy optimization
Usar DSPy para optimizar automaticamente el prompt de Qwen 0.5B. Encontrar la combinacion exacta de instrucciones que mejor funciona.

**Dependencia**: `pip install dspy`
**Esfuerzo**: Alto (~1 semana)
**Impacto**: Alto

### [14] Memoria vectorial con embeddings
Reemplazar TF-IDF por embeddings semanticos usando `nomic-embed-text` (ya disponible en Ollama). Busqueda por significado, no solo palabras.

> **Estado actual**: TF-IDF + sinonimos (implementado). Embeddings es
> el siguiente nivel — verdadero semantic search.

**Dependencia**: `nomic-embed-text` en Ollama
**Esfuerzo**: Alto (~1 semana)
**Impacto**: Muy alto (resuelve el problema fundamental de busqueda)

### [15] Evaluacion automatica de respuestas
Sistema que evalua la calidad de cada respuesta y retroalimenta el prompt. Respuestas buenas → refuerzo. Respuestas malas → ajuste.

**Esfuerzo**: Alto (~1-2 semanas)
**Impacto**: Alto

---

## Metricas de Exito

| Metrica | Actual | Meta |
|---|---|---|
| Respuestas desde memoria (sin SLM) | ~50% | >70% |
| Tiempo promedio de respuesta | ~3s | <2s |
| Tasa de alucinacion en respuestas | Media | <10% |
| Hechos aprendidos por sesion | 2-5 | 3-5 |
| Tests de regresion | 50+ | 100+ |
| Comandos sin SLM | 13 | 15+ |
