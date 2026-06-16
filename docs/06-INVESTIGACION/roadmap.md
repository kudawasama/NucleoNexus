# Roadmap de Mejoras Futuras

Priorizadas por impacto vs esfuerzo.

## Fase 1: Próximo (Alto impacto, bajo esfuerzo)

### [1] ReAct en el prompt del SLM
Implementar el formato Pensamiento → Acción → Observación → Respuesta en el prompt ligero del SLM. Esto estructura la salida de Qwen 0.5B y reduce alucinaciones.

**Archivo**: `cognition/context.py` — `_build_light_directives()`
**Esfuerzo**: Bajo (~30 min)
**Impacto**: Alto

### [2] Self-consistency para respuestas críticas
Para preguntas importantes, generar 2 respuestas con Qwen y elegir la más coherente. Simple de implementar y mejora precisión.

**Archivo**: `cognition/slm.py` — nuevo método `generate_with_consistency()`
**Esfuerzo**: Bajo (~1 hora)

### [3] Más patrones de extracción
Agregar más verbos y patrones al extractor para capturar más tipos de frases.

**Archivo**: `learning/extractor.py`
**Esfuerzo**: Bajo (~30 min)

---

## Fase 2: Medio plazo (Alto impacto, esfuerzo medio)

### [4] Fine-tuning LoRA para tool calling
Fine-tunear Qwen 0.5B con LoRA para que aprenda a generar acciones estructuradas (`[[accion:...]]`) de forma nativa.

**Herramientas**: Unsloth, LoRA, dataset de ~100 ejemplos
**Esfuerzo**: Medio (~1-2 días)

### [5] Structured generation con Guidance
Integrar Guidance o Outlines para forzar la salida del SLM a un formato JSON/acciones válido. Elimina respuestas mal formadas.

**Dependencia**: `pip install outlines`
**Esfuerzo**: Medio (~1 día)

### [6] Auto-memoria (modelo decide leer/escribir)
Que el SLM decida autónomamente cuándo buscar en memoria, qué aprender, y cuándo usar herramientas. Actualmente el sistema decide por él.

**Archivos**: `cognition/context.py`, `cognition/slm.py`
**Esfuerzo**: Medio (~1-2 días)

---

## Fase 3: Largo plazo (Transformacional, esfuerzo alto)

### [7] DSPy optimization
Usar DSPy para optimizar automáticamente el prompt de Qwen 0.5B. Encontrar la combinación exacta de instrucciones que mejor funciona.

**Dependencia**: `pip install dspy`
**Esfuerzo**: Alto (~1 semana)

### [8] Memoria vectorial con embeddings
Reemplazar TF-IDF por embeddings semánticos usando `nomic-embed-text` (ya disponible en Ollama). Búsqueda por significado, no solo palabras.

**Dependencia**: `nomic-embed-text` en Ollama
**Esfuerzo**: Alto (~1 semana)

### [9] Evaluación automática de respuestas
Sistema que evalúa la calidad de cada respuesta y retroalimenta el prompt. Respuestas buenas → refuerzo. Respuestas malas → ajuste.

**Esfuerzo**: Alto (~1-2 semanas)

---

## Métricas de Éxito

| Métrica | Actual | Meta |
|---|---|---|
| Respuestas desde memoria (sin SLM) | ~40% | >70% |
| Tiempo promedio de respuesta | ~5s | <2s |
| Tasa de alucinación en respuestas | Alta | <10% |
| Hechos aprendidos por sesión | 0-1 | 3-5 |
