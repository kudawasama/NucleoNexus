# Nucleo Nexus — Documentación del Proyecto

**Visión**: Hacer que un LLM pequeño (Qwen 2.5 0.5B) se comporte como un modelo PRO mediante arquitectura de sistema, no por tamaño de modelo.

## Estructura de la documentación

| Carpeta | Contenido |
|---|---|
| [01-VISION](01-VISION/) | Filosofía del proyecto, objetivos, principios |
| [02-ARQUITECTURA](02-ARQUITECTURA/) | Diseño del sistema, flujos, modos de operación |
| [03-MEMORIA](03-MEMORIA/) | Sistema de memoria: episódica, semántica, procedural |
| [04-COGNICION](04-COGNICION/) | Capa cognitiva: motor simbólico, contexto, SLM |
| [05-APRENDIZAJE](05-APRENDIZAJE/) | Aprendizaje automático, extractor, conocimiento inicial |
| [06-INVESTIGACION](06-INVESTIGACION/) | Investigación de técnicas (ReAct, Toolformer, MemGPT...) |
| [07-SKILLS](07-SKILLS/) | Sistema de skills y acciones |
| [08-CONFIGURACION](08-CONFIGURACION/) | Configuración del sistema |
| [09-DESARROLLO](09-DESARROLLO/) | Guías de desarrollo y contribución |

## Estado actual del proyecto

- ✅ Ruteo híbrido (simbólico + SLM)
- ✅ Memoria persistente con SQLite + TF-IDF
- ✅ Búsqueda semántica con filtrado de stop words
- ✅ Conocimiento inicial desde archivos JSON
- ✅ Extractor automático de hechos (aprendizaje)
- ✅ Backend Ollama (qwen2.5:0.5b)
- ✅ Reforzamiento por feedback del usuario
- 📝 ReAct en prompt del SLM (pendiente)
- 📝 Fine-tuning LoRA para tool calling (investigación)
- 📝 Structured generation con Guidance/Outlines (pendiente)
