# Prompts — Núcleo Nexus

> **Ronda documental de todas las instrucciones embebidas en el proyecto.**
> Cada archivo de esta carpeta documenta un componente: qué le dice al LLM, qué reglas sigue, qué filtros aplica, qué plantillas usa.
>
> **No incluye código** — solo las instrucciones (system prompts, few-shot examples, plantillas, reglas de filtrado, formatos de salida).

---

## Mapa general

| # | Archivo | Componente | Tipo de instrucción |
|---|---------|-----------|---------------------|
| 01 | [01-AGENTE-ORQUESTADOR.md](./01-AGENTE-ORQUESTADOR.md) | `cognition/agent.py` — `NexusAgent` | Orquestador multi-tool (investigate / explain / document / code_search) |
| 02 | [02-AGENTE-SLM.md](./02-AGENTE-SLM.md) | `cognition/slm.py` — `SLMBackend` | System prompt JSON para Qwen 0.5B (formato forzado) |
| 03 | [03-INYECCION-CONTEXTO.md](./03-INYECCION-CONTEXTO.md) | `cognition/context.py` — `ContextBuilder` | System prompt dinámico (personalidad + estado + memoria + skills) |
| 04 | [04-MOTOR-SIMBOLICO.md](./04-MOTOR-SIMBOLICO.md) | `cognition/symbolic.py` — `SymbolicEngine` | Reglas determinísticas + plantillas de respuesta (modo sin SLM) |
| 05 | [05-APRENDIZAJE-FEW-SHOT.md](./05-APRENDIZAJE-FEW-SHOT.md) | `learning/few_shot.py` | Dataset de entrenamiento (Qwen 0.5B → JSON con acción) |
| 06 | [06-APRENDIZAJE-EXTRACTOR.md](./06-APRENDIZAJE-EXTRACTOR.md) | `learning/extractor.py` + `learning/synonyms.py` | Patrones de extracción automática + expansión de queries |
| 07 | [07-MEMORIA.md](./07-MEMORIA.md) | `memory/semantic.py` + `episodic.py` + `procedural.py` + `embeddings.py` | Reglas de almacenamiento, recall, refuerzo |
| 08 | [08-SKILLS-SUBAGENTES.md](./08-SKILLS-SUBAGENTES.md) | `skills/builtins/*` (17 skills) | Capacidades expuestas como function-calling |
| 09 | [09-GUIA-DOCUMENTOS.md](./09-GUIA-DOCUMENTOS.md) | `knowledge/guide.py` | System prompt "analista de documentos" (briefing + FAQ + conceptos) |
| 10 | [10-ORQUESTADOR-PRINCIPAL.md](./10-ORQUESTADOR-PRINCIPAL.md) | `main.py` — `NexusCore.process` | Flujo principal: responder → aprender → recordar → sincronizar |
| 11 | [11-INTERFAZ-CLI.md](./11-INTERFAZ-CLI.md) | `interface/cli.py` + `nexus.py` | Comandos del usuario, ayuda, formato de salida |
| 12 | [12-ENGINE-STATE.md](./12-ENGINE-STATE.md) | `engine/state.py` + `engine/actions.py` | Contrato estado ↔ IA (la IA nunca calcula) |
| 13 | [13-TOOLS-AUXILIARES.md](./13-TOOLS-AUXILIARES.md) | `tools/pdf_renamer.py` + `utils/git_auto.py` | Reglas de renombrado de PDFs + sync git |
| 14 | [14-CONFIG-VERSION.md](./14-CONFIG-VERSION.md) | `config.py` + `version.py` | Configuración central + versionado semántico |
| 15 | [15-TESTS-FILOSOFIA.md](./15-TESTS-FILOSOFIA.md) | `tests/test_regression.py` | Garantías que el proyecto promete mantener |

---

## Flujo resumido

```
Usuario (CLI)
   │
   ▼
[11-INTERFAZ] detecta comando o input libre
   │
   ▼
[10-ORQUESTADOR] NexusCore.process()
   ├─→ [04-MOTOR-SIMBOLICO]  (intents rápidos, sin modelo)
   ├─→ [03-INYECCION-CONTEXTO]  (arma system prompt dinámico)
   ├─→ [02-AGENTE-SLM]  (formato JSON + Ollama call)
   └─→ [05-APRENDIZAJE-FEW-SHOT]  (instrucciones + ejemplos para Qwen 0.5B)
   │
   ▼
[08-SKILLS] ejecuta tools si el SLM lo pidió
   ├─→ [09-GUIA-DOCUMENTOS] si el usuario pidió una guía
   └─→ [13-TOOLS-AUXILIARES] si pidió renombrar PDFs
   │
   ▼
[07-MEMORIA] guarda recuerdo + extrae hechos + refuerza
[06-APRENDIZAJE] detecta feedback, expande con sinónimos
[12-ENGINE-STATE] actualiza fase, interacciones, confianza
[13-TOOLS-AUXILIARES] git auto commit + push
```

Para tareas complejas (investigar / explicar / documentar / buscar en código) el orquestador principal delega en **[01-AGENTE-ORQUESTADOR]** que encadena tools y sintetiza.

---

## Filosofía del proyecto (resumen ejecutivo)

> *"Inteligencia por arquitectura, no por tamaño"*

- **Qwen 0.5B + sistema = PRO** — el SLM pequeño es solo el núcleo; el resto (memoria, skills, ruteo) lo potencia.
- **Aprendizaje incremental** — el sistema NO pre-carga conocimiento; aprende de cada conversación.
- **Modo sin modelo** — el motor simbólico responde sin GPU, sin internet, sin SLM.
- **Function calling** — la IA orquesta; el código calcula.
- **Evolución por fases** — Proto → Básico → Intermedio → Avanzado → Pro (basado en número de interacciones).
