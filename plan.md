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
Fase 0 — Higiene (1–2 días, alta relación costo/beneficio)

- F0.1 Sincronizar docs ↔ config.py: decidir modelo por defecto y reflejarlo; corregir vector_dim a 768; documentar fast_intents completos y el backend OpenCode.
- F0.2 requirements.txt: declarar requests como opcional extra (pip install nexus[slm]).
- F0.3 version.py: soportar rama main además de master (leer dinámicamente git symbolic-ref HEAD).
- F0.4 auto_commit_push: cambiar a batch/condicional (cada N interacciones o solo cuando se modifique estado real), con mensaje con contador bien formado.
- F0.5 Mover pdf_rename a skills/builtins/pdf_skill.py.
- F0.6 Reparar calculadora con un ast-parser seguro o simpleeval (soporta precedencia y paréntesis), con test.
Fase 1 — Refactor de main.py (3–5 días)
- F1.1 Extraer router.py (_get_response + heurísticas híbridas).
- F1.2 Extraer tool_intents.py (_handle_tool_intent y parámetros regex).
- F1.3 Extraer web_learning.py (_learn_from_web_search).
- F1.4 Extraer react.py (_strip_react, _clean_react_response,_execute_react_actions).
- F1.5 Unificar el mecanismo de invocación: conservar JSON estructurado como vía principal, dejar [[accion:..]] exclusivamente para el motor simbólico plano.
- Meta: main.py ≤ 300 líneas, NexusCore solo orquesta.
Fase 2 — Calidad y confianza (3–5 días)
- F2.1 Centralizar umbrales mágicos en config.py (THRESHOLDS = {dedup: 0.88, reinforce: 0.1, consolidate: 0.8, decay: 0.99, floor: 0.25, score: 0.15, confidence: {...}}).
- F2.2 Tests de regresión por componente: dividir test_regression.py en test_memory/, test_cognition/, test_routing/, test_extractor/, test_tools/. Añadir tests sobre los thresholds.
- F2.3 Self-consistency real: votación por similitud de embeddings entre N respuestas (usa nomic-embed-text ya disponible) en vez de "más larga gana".
- F2.4 Decidir y documentar status de ReAct: si hermes3:3b lo sigue, habilitarlo solo para modelos ≥3B; si no, eliminar _strip_react para reducir código muerto.
Fase 3 — Mejora del aprendizaje (1–2 semanas)
- F3.1 Extractor: ampliar verbos, post-procesado de stop-words en el hecho extraído (limpieza con la misma stop_words usada en búsqueda).
- F3.2 Verificación ligera de hechos: contraste contra facts existentes (si uno nuevo contradice uno con confidence>0.8, pedir confirmación al usuario en vez de aprender ciego).
- F3.3 Permitir aprendizaje selectivo desde respuestas del SLM cuando el modelo sea ≥3B (hermes3 ya es fiable): nivel de confianza $0.15$ y solo si la respuesta contiene un hecho estructurado detectable.
- F3.4 Memoria episódica: compresión periódica — al alcanzar el 80% del límite, consolidar los más antiguos vía resumen semántico en un fact "episodio agrupado".
Fase 4 — Memoria semántica向量ial (1–2 semanas, impacto muy alto)
- F4.1 Reemplazar TF-IDF por embeddings nomic-embed-text en query_knowledge (lo ya anunciado en roadmap.md #14). Conservar TF-IDF solo como fallback sin-Ollama.
- F4.2 Migrar BLOB JSON → BLOB binario float32 (reduce memoria ~75% y acelera cosine).
- F4.3 Añadir índice ANN ligero (hnswlib o sqlite-vec) para escalar más allá de 5.000 facts.
Fase 5 — Roadmap estratégico (medio-largo plazo)
- F5.1 ReAct en el prompt del SLM (solo modelos ≥3B) — roadmap #6, ~30 min.
- F5.2 Auto-memory: que el SLM decida buscar_memoria/learn_fact vía JSON (MemGPT-style). Requiere F4.
- F5.3 /agent command — encadenamiento web_search + read_file + learn (roadmap #12).
- F5.4 LoRA fine-tuning de Qwen 0.5B para tool calling (unsloth, ~100 ejemplos) — "transformational".
- F5.5 Structured generation con Outlines/Guidance como complemento al JSON mode de Ollama.
- F5.6 DSPy para auto-optimización de prompts (experimento aislado; evaluar antes de adoptar).
Fase 6 — Seguridad y robustez (transversal)
- F6.1 run_command, read_file, search_files con path-allowlist configurable; bloquear fuera del workspace por defecto.
- F6.2 Cuando api.enabled=true, deshabilitar run_command salvo allowlist explícita.
- F6.3 auto_commit_push con --exclude de patrones sensibles (.env, *.key) y pre-commit hook de secretos.
- F6.4 Auditoría de path-traversal en browse_url/read_file.

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
