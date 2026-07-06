Análisis y Plan de Mejora — NucleoNexus
He leído la documentación completa (carpetas 01-VISION a 09-DESARROLLO), README.md, main.py, config.py, version.py, requirements.txt y tests/. Aquí va el diagnóstico y el plan.

1. Visión y arquitectura (contexto)
NucleoNexus propone "inteligencia por arquitectura, no por tamaño de modelo": un SLM local (qwen2.5:0.5b documentado / hermes3:3b en código) + memoria persistente (SQLite + TF-IDF) + motor simbólico + skills, enrutamiento híbrido y aprendizaje incremental. La tesis es sólida y los pilares están bien definidos.
2. Análisis de debilidades (priorizadas)
🔴 Crítico — Corrección y consistencia

# Problema

C1 Deriva documentación ↔ código
C2 Backend "OpenCode" no documentado
C3 Calculadora rota para expresiones reales
C4 Auto-commits contaminan el historial
C5 version.py asume rama master
🟠 Alto — Diseño / mantenibilidad

# Problema

H1 main.py = 1124 líneas monolítico
H2 Self-consistency débil
H3 Doble mecanismo de invocación de acciones
H4 pdf_rename hardcodeado en core
H5 Embeddings como BLOB JSON UTF-8
H6 Magia numérica dispersa sin tests
🟡 Medio — Funcionalidad / roadmap

# Problema

M1 ReAct contradictorio
M2 Extractor frágil
M3 No aprende de respuestas del SLM
M4 Búsqueda semántica TF-IDF + sinónimos
M5 Memoria episódica: política FIFO simple
M6 run_command regex detección vs ejecución desincronizado
M7 Tests = un único fichero 38 KB
🟢 Bajo — Seguridad / robustez

# Problema

L1 run_command ejecuta shell arbitrario (aceptable en CLI mono-usuario; riesgo si se activa API).
L2 read_file/browse_url/search_files sin path-allowlist.
L3 auto_commit_push podría commitear secretos a repo público si se configura mal.
L4 requirements.txt declara cero deps, pero modo SLM usa requests (vía import dinámico). Instalación limpia falla en modo SLM.
3. Plan de mejora (fases)
Fase 0 — Higiene (Completado)
- [x] F0.1 Sincronizar docs ↔ config.py: Decidir modelo por defecto, corregir vector_dim a 768, documentar intents y OpenCode.
- [x] F0.2 requirements.txt: Declarar requests como opcional extra.
- [x] F0.3 version.py: Soportar rama main además de master.
- [x] F0.4 auto_commit_push: Cambiar a batch/condicional con mensaje con contador.
- [x] F0.5 Mover pdf_rename a skills/builtins/pdf_skill.py.
- [x] F0.6 Reparar calculadora con un ast-parser seguro, con test.

Fase 1 — Refactor de main.py (Completado)
- [x] F1.1 Extraer router.py (_get_response + heurísticas híbridas).
- [x] F1.2 Extraer tool_intents.py (_handle_tool_intent y parámetros regex).
- [x] F1.3 Extraer web_learning.py (_learn_from_web_search).
- [x] F1.4 Extraer react.py (_strip_react, _clean_react_response, _execute_react_actions).
- [x] F1.5 Unificar el mecanismo de invocación: JSON estructurado principal y [[accion:...]] para simbólico.

Fase 2 — Calidad, confianza y Deduplicación Semántica (En progreso)
- [x] F2A Deduplicación Semántica asíncrona de hechos (similitud coseno >= 88%, consolidación de confianza).
- [ ] F2.1 Centralizar umbrales mágicos en config.py (THRESHOLDS = {dedup: 0.88, reinforce: 0.1, consolidate: 0.8, decay: 0.99...}).
- [ ] F2.2 Tests de regresión por componente: dividir test_regression.py en test_memory/, test_cognition/, test_routing/, etc.
- [ ] F2.3 Self-consistency real: votación por similitud de embeddings entre N respuestas en vez de "más larga gana".
- [ ] F2.4 Decidir y documentar status de ReAct (eliminar _strip_react si no es necesario para hermes3).

Fase 3 — Mejora del aprendizaje e Interfaz CLI (En progreso)
- [x] F3.UI Rediseño completo de la interfaz CLI usando prompt_toolkit (menú interactivo, autocompletado con Tabular y barra de estado).
- [x] F3.Lock Concurrencia robusta en SQLite mediante Locks en llamadas de base de datos.
- [ ] F3.1 Extractor: ampliar verbos, post-procesado de stop-words en hechos.
- [ ] F3.2 Verificación ligera de hechos: pedir confirmación si contradice hechos con confianza > 0.8.
- [ ] F3.3 Aprendizaje selectivo desde respuestas del SLM cuando sea fiable.
- [ ] F3.4 Memoria episódica: compresión periódica de recuerdos antiguos en resúmenes semánticos.

Fase 4 — Memoria semántica vectorial
- [ ] F4.1 Reemplazar TF-IDF por embeddings nomic-embed-text en query_knowledge.
- [ ] F4.2 Migrar BLOB JSON -> BLOB binario float32 (ahorro ~75% de espacio).
- [ ] F4.3 Añadir índice ANN ligero (sqlite-vec o hnswlib) para escalar más allá de 5,000 facts.

Fase 5 — Roadmap estratégico
- [ ] F5.1 ReAct en el prompt del SLM (solo modelos >= 3B).
- [ ] F5.2 Auto-memory: que el SLM decida buscar/aprender hechos vía JSON (MemGPT-style).
- [ ] F5.3 Extender el comando /agent.
- [ ] F5.4 LoRA fine-tuning de Qwen 0.5B para tool calling.
- [ ] F5.5 Structured generation con Outlines/Guidance como complemento a Ollama.
- [ ] F5.6 DSPy para auto-optimización de prompts.

Fase 6 — Seguridad y robustez (transversal)
- [ ] F6.1 run_command, read_file, search_files con path-allowlist configurable; bloquear fuera del workspace por defecto.
- [ ] F6.2 Cuando api.enabled=true, deshabilitar run_command salvo allowlist explícita.
- [ ] F6.3 auto_commit_push con --exclude de patrones sensibles (.env, *.key) y pre-commit hook de secretos.
- [ ] F6.4 Auditoría de path-traversal en browse_url/read_file.

4. Métricas objetivo (alineadas con roadmap.md)
Métrica
Respuestas desde memoria (sin SLM)
Latencia media
Tasa de alucinación
Tests de regresión
main.py líneas
Commits auto mensuales
Cobertura embeddings
2. Recomendación inmediata
Empieza por Fase 0 (1–2 días): arreglar docs↔config, calculadora, auto-commits y version.py es de bajo riesgo y alto valor visible. Después Fase 1 (refactor de main.py) desbloquea todo lo demás. Si quieres, puedo ejecutar ya la Fase 0 completa.
