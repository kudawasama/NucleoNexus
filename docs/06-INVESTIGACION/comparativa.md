# Comparativa de Técnicas y Plan de Mejora

## Resumen Ejecutivo

| Técnica | Funciona en 0.5B? | Conclusión |
|---------|-------------------|------------|
| **ReAct Prompt** | ❌ No sigue el formato | Requiere modelo ≥3B o Structured Generation |
| **Memoria + Contexto** | ✅ Sí, mejora respuestas | Implementado y funcionando |
| **Ruteo Híbrido** | ✅ Sí, evita alucinaciones | Implementado y funcionando |
| **Parser de acciones** | 🟡 Ocasionalmente | Mantener como bonus |
| **Structured Generation** | ✅ Sí, JSON mode Ollama | ✅ Implementado (commit `dd0bae1`) |
| **Fine-tuning LoRA** | ✅ Sí, ideal para tool use | Pendiente |
| **Tools vía Intent** | ✅ Sí, regex directa | ✅ Implementado (commit `0c0e601`) |

## Resultados de la Investigación

### ReAct (Reasoning + Acting)
**Problema**: Qwen 0.5B no sigue el formato estructurado "Pienso: ... Respuesta: ..." incluso con ejemplos explícitos.

**Causa**: Los modelos de 0.5B tienen capacidad limitada para seguir instrucciones de formato. La atención del modelo se dispersa con prompts largos.

**Solución**: No forzar formato. En su lugar:
- Inyectar contexto de memoria relevante (funciona)
- Prompt simple y directo (funciona)
- Parser de acciones `[[accion:...]]` como bonus si el modelo las genera naturalmente

### Structured Generation (Guidance)
**Viable para 0.5B**: Sí. A nivel de generación de tokens, Guidance fuerza el formato. El modelo no puede desviarse.

**Implementación**: `pip install outlines` + parchar `SLMBackend.generate()` para usar generación guiada.

### Fine-tuning LoRA
**Recomendado**: Sí, para Qwen 0.5B un LoRA de tool calling es viable y transformacional.

**Dataset necesario**: ~100 pares de ejemplo (instrucción → acción + respuesta).

## Plan de Implementación Priorizado

| Prioridad | Técnica | Esfuerzo | Impacto |
|---|---|---|---|
| **✅ Hecho** | Ruteo híbrido | Bajo | Muy alto |
| **✅ Hecho** | Memoria + contexto | Bajo | Muy alto |
| **✅ Hecho** | Extractor automático | Bajo | Alto |
| **✅ Hecho** | Structured Generation (JSON mode Ollama) | Medio | Muy alto |
| **✅ Hecho** | Tools vía intent directo (regex) | Medio | Alto |
| **✅ Hecho** | Sinónimos + expansión queries | Bajo | Alto |
| **✅ Hecho** | Auto-aprendizaje desde web | Bajo | Muy alto |
| **Pendiente** | Fine-tuning LoRA para tool calling | Medio | Transformacional |
| **Pendiente** | Memoria vectorial (embeddings) | Medio | Alto |
| **Parcial** | Self-consistency | Bajo | Medio |
| **Pendiente** | DSPy optimization | Alto | Alto |

### Próximo Paso Inmediato: Structured Generation

La técnica de mayor impacto disponible ahora es **forzar el formato de salida** con una librería como Guidance o Outlines. Esto:

1. Permite que Qwen 0.5B genere tool calls de forma confiable
2. Elimina respuestas mal formadas
3. No requiere fine-tuning
4. Funciona a nivel de token, no de prompt

```python
# Con Outlines, forzar formato:
esquema = {
    "accion": "buscar_memoria | calcular | responder",
    "argumentos": "string",
    "respuesta": "string"
}
# Qwen 0.5B solo puede generar JSON válido con este esquema
```
