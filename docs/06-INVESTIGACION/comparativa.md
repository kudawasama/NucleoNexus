# Comparativa de Técnicas y Plan de Mejora

## Resumen Ejecutivo

| Técnica | Funciona en 0.5B? | Conclusión |
|---------|-------------------|------------|
| **ReAct Prompt** | ❌ No sigue el formato | Requiere modelo ≥3B o Structured Generation |
| **Memoria + Contexto** | ✅ Sí, mejora respuestas | Implementado y funcionando |
| **Ruteo Híbrido** | ✅ Sí, evita alucinaciones | Implementado y funcionando |
| **Parser de acciones** | 🟡 Ocasionalmente | Mantener como bonus |
| **Structured Generation** | ✅ Sí, forzaría formato | Pendiente (próximo paso) |
| **Fine-tuning LoRA** | ✅ Sí, ideal para tool use | Futuro |

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
| **1°** | Structured Generation (Guidance) | Medio | Muy alto |
| **2°** | Fine-tuning LoRA | Medio | Transformacional |
| **3°** | Memoria vectorial (embeddings) | Medio | Alto |
| **4°** | Self-consistency | Bajo | Medio |

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
