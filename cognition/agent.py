"""
Núcleo Nexus — Agente que encadena tools
=========================================
Similar a Hermes Agent: el agente planifica y ejecuta una
secuencia de herramientas para responder una tarea compleja.

Diferencia con Hermes:
- Hermes: el LLM decide iterativamente
- Nexus: reglas deterministicas (rapido, no depende del SLM)

Flujo del agente:
1. PLAN: analizar la tarea, decidir que tools usar
2. EXECUTE: ejecutar las tools en secuencia
3. LEARN: guardar resultados utiles en memoria
4. SUMMARIZE: sintetizar una respuesta

Vision: 'Inteligencia por arquitectura, no por tamaño'
El agente hace lo que un LLM grande haria, pero sin SLM.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("nexus.cognition.agent")


@dataclass
class AgentStep:
    """Un paso ejecutado por el agente."""
    tool: str
    input: str
    output: str
    success: bool
    duration_ms: int = 0


@dataclass
class AgentResult:
    """Resultado completo de la ejecucion del agente."""
    task: str
    steps: list = field(default_factory=list)
    summary: str = ""
    facts_learned: int = 0
    success: bool = True
    error: str = ""


class NexusAgent:
    """Agente que orquesta tools en secuencia para tareas complejas.

    A diferencia del flujo normal (1 tool por turno), el agente
    puede ejecutar multiples tools en una sola pasada.

    Tipos de tareas que maneja:
    - "investiga X"     -> web_search + learn
    - "explica X"        -> web_search + browse_url + learn
    - "documenta X"      -> web_search + search_files + read_file
    - "busca en web y archivos" -> web_search + search_files
    """

    # Palabras clave para detectar tipo de tarea
    INVESTIGATE_KEYWORDS = [
        "investiga", "busca informacion", "aprende sobre",
        "que es", "que son", "definicion de", "informacion sobre",
    ]
    EXPLAIN_KEYWORDS = [
        "explica", "detalla", "describe", "como funciona",
        "cual es la diferencia", "por que",
    ]
    DOCUMENT_KEYWORDS = [
        "documenta", "docuementa", "crea documentacion",
        "genera reporte", "escribe informe",
    ]
    CODE_KEYWORDS = [
        "busca en codigo", "busca en archivos", "encuentra en el codigo",
        "donde esta", "como se usa",
    ]

    def __init__(self, nexus_core):
        """Inicializa con referencia a NexusCore para acceder a tools y memoria."""
        self.core = nexus_core
        self.actions = nexus_core.actions
        self.memory = nexus_core.memory

    def run(self, task: str) -> AgentResult:
        """Ejecuta el agente sobre una tarea.

        Args:
            task: Descripcion de lo que el usuario quiere

        Returns:
            AgentResult con los pasos ejecutados, resumen, etc
        """
        result = AgentResult(task=task)

        # 1. PLAN: detectar tipo de tarea
        task_type = self._detect_task_type(task)
        logger.info(f"Agent task type: {task_type}")

        # 2. EXECUTE: ejecutar el plan segun el tipo
        try:
            if task_type == "investigate":
                self._plan_investigate(task, result)
            elif task_type == "explain":
                self._plan_explain(task, result)
            elif task_type == "document":
                self._plan_document(task, result)
            elif task_type == "code_search":
                self._plan_code_search(task, result)
            else:
                # Default: investigar (web search)
                self._plan_investigate(task, result)
        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"Agent error: {e}")

        # 3. SUMMARIZE: generar resumen
        if result.success:
            result.summary = self._summarize(task, result.steps)

        return result

    def _detect_task_type(self, task: str) -> str:
        """Detecta el tipo de tarea basandose en palabras clave."""
        task_lower = task.lower()

        # Prioridad: code_search > document > explain > investigate
        for kw in self.CODE_KEYWORDS:
            if kw in task_lower:
                return "code_search"
        for kw in self.DOCUMENT_KEYWORDS:
            if kw in task_lower:
                return "document"
        for kw in self.EXPLAIN_KEYWORDS:
            if kw in task_lower:
                return "explain"
        for kw in self.INVESTIGATE_KEYWORDS:
            if kw in task_lower:
                return "investigate"

        # Default
        return "investigate"

    # ─── Plan: Investigar (web search + learn) ──────────────
    def _plan_investigate(self, task: str, result: AgentResult):
        """Plan: web_search + synthesize.

        1. web_search el tema
        2. synthesize una respuesta coherente con lo encontrado
        """
        # Extraer el tema del task (quitar el verbo "investiga")
        topic = self._extract_topic(task)
        if not topic:
            result.success = False
            result.error = "No pude entender el tema a investigar"
            return

        # Paso 1: web_search
        search_step = self._execute_tool("web_search", query=topic)
        result.steps.append(search_step)

        if not search_step.success:
            return

        # Paso 2: aprender de los resultados (auto-learning)
        try:
            # Los resultados vienen en search_step.output
            # Extraer items de la busqueda
            items = self._parse_search_results(search_step.output)
            if items:
                # Aprender cada item como hecho (sin filtros de GitHub)
                learned = 0
                for item in items[:3]:
                    if len(item) > 30 and "http" not in item[:50]:
                        # Filtrar items tipo "github.com/user/repo"
                        if "github.com/" in item and " — " in item:
                            continue
                        self.memory.learn_fact(
                            item,
                            category="aprendido_web",
                            confidence=0.5,
                            source="auto_web_agent",
                        )
                        learned += 1
                result.facts_learned = learned
        except Exception as e:
            logger.warning(f"Learn step error: {e}")

        # Paso 3: SYNTHESIZE - redactar una respuesta coherente
        synth_step = self._synthesize_answer(task, topic, result.steps)
        if synth_step:
            result.steps.append(synth_step)

    # ─── Plan: Explicar (web_search + browse_url) ──────────
    def _plan_explain(self, task: str, result: AgentResult):
        """Plan: web_search + browse + synthesize.

        1. web_search para encontrar URLs
        2. browse_website para obtener el contenido textual
        3. synthesize para redactar una respuesta coherente con todo
        """
        topic = self._extract_topic(task)
        if not topic:
            topic = task  # fallback

        # Paso 1: web_search
        search_step = self._execute_tool("web_search", query=topic)
        result.steps.append(search_step)

        if not search_step.success:
            return

        # Paso 2: extraer URLs de los resultados y visitar la primera
        urls = self._extract_urls_from_results(search_step.output)
        if urls:
            # Visitar la primera URL
            browse_step = self._execute_tool("browse_website", url=urls[0])
            result.steps.append(browse_step)

            # Aprender de la busqueda
            items = self._parse_search_results(search_step.output)
            if items:
                learned = 0
                for item in items[:3]:
                    if len(item) > 30 and "http" not in item[:50]:
                        if "github.com/" in item and " — " in item:
                            continue
                        self.memory.learn_fact(
                            item, category="aprendido_web",
                            confidence=0.5, source="auto_web_agent",
                        )
                        learned += 1
                result.facts_learned = learned

        # Paso 3: SYNTHESIZE - redactar una respuesta coherente
        # Toma todo lo recolectado y genera una explicacion
        synth_step = self._synthesize_answer(task, topic, result.steps)
        if synth_step:
            result.steps.append(synth_step)

    def _synthesize_answer(self, task: str, topic: str, prior_steps: list) -> 'AgentStep | None':
        """Sintetiza una respuesta coherente usando el SLM.

        Toma los outputs de los pasos anteriores (web_search, browse_website)
        y los pasa al SLM con un prompt que le pide redactar una explicacion.

        Si el SLM no esta disponible, usa el motor simbolico como fallback.
        """
        import time
        start = time.time()

        # Recolectar contenido de los pasos anteriores
        context_text = ""
        sources = []
        for step in prior_steps:
            if not step.success:
                continue
            output = step.output
            # Para web_search: extraer items (•, [Wikipedia], etc)
            if "web_search" in step.tool and ("'resultados':" in output or '"resultados":' in output):
                # Match items de 50+ chars (incluye •, [Wikipedia], etc)
                items = re.findall(r"['\"]([^'\"]{50,})['\"]", output)
                if items:
                    # Filtrar y rankear items por relevancia al topic
                    topic_words = set(re.findall(r'\b[a-záéíóúñ]{3,}\b', topic.lower()))
                    ranked = []
                    for item in items:
                        clean = item.lstrip('•').strip()
                        # Quitar la URL entre parentesis
                        url_in_item = re.search(r'\((https?://[^\)]+)\)', clean)
                        if url_in_item:
                            sources.append(url_in_item.group(1))
                        clean_no_url = re.sub(r'\s*\([^)]+\)\s*', ' ', clean).strip()
                        # Contar matches con topic
                        item_words = set(re.findall(r'\b[a-záéíóúñ]{3,}\b', clean.lower()))
                        relevance = len(topic_words & item_words)
                        ranked.append((relevance, clean_no_url))
                    # Ordenar por relevancia descendente
                    ranked.sort(key=lambda x: x[0], reverse=True)
                    # Tomar los top 3
                    for relevance, clean in ranked[:3]:
                        if clean and len(clean) > 20:
                            context_text += f"- {clean[:200]}\n"
            # Para browse_website: extraer contenido
            elif "browse_website" in step.tool:
                m = re.search(r"'contenido':\s*'([^']{50,2000})'", output)
                if not m:
                    m = re.search(r'"contenido":\s*"([^"]{50,2000})"', output)
                if m:
                    context_text += f"\nContenido de la web:\n{m.group(1)[:1500]}\n"

        if not context_text:
            return None

        # Intentar usar el SLM
        synthesized = ""
        try:
            slm = getattr(self.core, 'slm', None)
            if slm and getattr(slm, 'loaded', False):
                system_prompt = (
                    "Eres Nexus, asistente inteligente. Tu tarea es redactar una "
                    "respuesta clara y coherente en espanol basada en la informacion "
                    "proporcionada. NO inventes datos. Si la informacion es insuficiente, "
                    "dilo. Incluye los puntos principales, no mas de 200 palabras."
                )
                user_msg = (
                    f"Pregunta del usuario: {task}\n\n"
                    f"Informacion encontrada:\n{context_text}\n\n"
                    f"Redacta una respuesta clara y util en espanol:"
                )
                slm_result = slm.generate(user_msg, system_prompt=system_prompt)
                # El SLM puede devolver un dict {response: ...} o un string directo
                if slm_result is None:
                    synthesized = ""
                elif isinstance(slm_result, str):
                    synthesized = slm_result
                elif isinstance(slm_result, dict):
                    raw = slm_result.get("response", "")
                    if isinstance(raw, str):
                        # Si el SLM devolvio JSON, parsearlo
                        try:
                            import json as _json
                            parsed = _json.loads(raw)
                            if isinstance(parsed, dict):
                                synthesized = parsed.get("respuesta", raw)
                            else:
                                synthesized = raw
                        except Exception:
                            synthesized = raw
                    else:
                        synthesized = str(raw)
                else:
                    synthesized = str(slm_result)
        except Exception as e:
            logger.warning(f"SLM synthesize fallo: {e}")

        # Fallback: si el SLM no esta o fallo, generar respuesta basica
        if not synthesized:
            synthesized = self._synthesize_fallback(topic, context_text, sources)

        duration = int((time.time() - start) * 1000)
        return AgentStep(
            tool="synthesize",
            input=task,
            output=synthesized[:2000],
            success=bool(synthesized),
            duration_ms=duration,
        )

    def _synthesize_fallback(self, topic: str, context_text: str, sources: list) -> str:
        """Fallback cuando el SLM no esta disponible: arma respuesta con extractos.

        Sin SLM, la respuesta es basica pero util:
        - Titulo
        - Extractos relevantes
        - Fuentes
        """
        lines = [f"# {topic}\n"]
        # Tomar las primeras 3 lineas de contexto
        context_lines = [
            line for line in context_text.split("\n")
            if line.strip() and not line.startswith("Contenido de la web:")
        ][:3]
        for line in context_lines:
            clean = line.lstrip("- ").strip()
            if len(clean) > 30:
                lines.append(f"- {clean[:200]}")

        if sources:
            lines.append("\nFuentes:")
            for src in sources[:3]:
                lines.append(f"  - {src}")

        return "\n".join(lines)

    # ─── Plan: Documentar (web_search + search_files) ─────
    def _plan_document(self, task: str, result: AgentResult):
        """Plan: web_search el tema, buscar archivos locales relacionados."""
        topic = self._extract_topic(task)
        if not topic:
            topic = task

        # Paso 1: web_search
        search_step = self._execute_tool("web_search", query=topic)
        result.steps.append(search_step)

        if not search_step.success:
            return

        # Paso 2: search_files local
        search_local = self._execute_tool("search_files", pattern=topic)
        result.steps.append(search_local)

        # Aprender
        items = self._parse_search_results(search_step.output)
        if items:
            learned = 0
            for item in items[:3]:
                if len(item) > 30 and "http" not in item[:50]:
                    if "github.com/" in item and " — " in item:
                        continue
                    self.memory.learn_fact(
                        item, category="aprendido_web",
                        confidence=0.5, source="auto_web_agent",
                    )
                    learned += 1
            result.facts_learned = learned

    # ─── Plan: Buscar en codigo (search_files + read_file) ───
    def _plan_code_search(self, task: str, result: AgentResult):
        """Plan: buscar archivos locales que coincidan con el tema.

        Para 'busca en codigo la funcion X':
        1. Detectar el nombre exacto de la funcion
        2. Buscar el archivo .py que la define (no menciones, no .pyc)
        3. Leer el archivo encontrado
        """
        # Detectar si se busca una funcion/metodo/clase especifica
        func_name = self._extract_function_name(task)
        if not func_name:
            # Si no se detecta funcion, usar el topic completo
            topic = self._extract_topic(task)
        else:
            topic = func_name

        if not topic:
            topic = task

        # Paso 1: buscar el archivo .py que define la funcion
        # Primero intentar con el patron 'def FUNCION' para encontrar el archivo exacto
        if func_name:
            # Buscar la DEFINICION: 'def nombre_funcion' o 'class NombreClase'
            search_pattern = f"def {func_name}"
            search_step = self._execute_tool("search_files", pattern=search_pattern)
            result.steps.append(search_step)
            if not search_step.success or not self._parse_file_results(search_step.output):
                # Si no se encontro la definicion, buscar por nombre de archivo
                search_pattern = func_name
                search_step = self._execute_tool("search_files", pattern=search_pattern)
                result.steps.append(search_step)
        else:
            search_step = self._execute_tool("search_files", pattern=topic)
            result.steps.append(search_step)

        if not search_step.success:
            return

        # Paso 2: leer el archivo .py encontrado en el contexto de la funcion
        files = self._parse_file_results(search_step.output)
        py_files = [f for f in files if f.endswith('.py')
                    and '__pycache__' not in f
                    and '.history' not in f]
        if py_files:
            # Si tenemos func_name, usar search= para ir directo a la definicion
            if func_name:
                read_step = self._execute_tool(
                    "read_file", path=py_files[0],
                    search=f"def {func_name}", max_lines=40,
                )
            else:
                read_step = self._execute_tool(
                    "read_file", path=py_files[0], max_lines=50
                )
            result.steps.append(read_step)
        elif files:
            read_step = self._execute_tool(
                "read_file", path=files[0], max_lines=50
            )
            result.steps.append(read_step)

    def _extract_function_name(self, task: str) -> str:
        """Detecta el nombre de una funcion/clase en el task.

        'busca en codigo la funcion query_knowledge' -> 'query_knowledge'
        'encuentra la clase NexusCore' -> 'NexusCore'
        'donde esta def run' -> 'run'
        """
        import re as _re
        task_lower = task.lower()

        # Patron 1: 'la funcion X' / 'la funcion X()' / 'la funcion X.'
        m = _re.search(r'(?:la\s+)?funci[oó]n\s+([a-z_][a-z0-9_]*)', task_lower)
        if m:
            return m.group(1)

        # Patron 2: 'el metodo X' / 'el metodo X()'
        m = _re.search(r'(?:el\s+)?m[ée]todo\s+([a-z_][a-z0-9_]*)', task_lower)
        if m:
            return m.group(1)

        # Patron 3: 'la clase X' / 'la clase NexusCore'
        m = _re.search(r'(?:la\s+)?clase\s+([A-Z][a-zA-Z0-9_]*)', task_lower)
        if m:
            return m.group(1)

        # Patron 4: 'donde esta X' / 'donde esta el X'
        m = _re.search(r'd[oó]nde\s+est[aá]\s+(?:el\s+|la\s+)?([a-zA-Z_][a-zA-Z0-9_]*)', task_lower)
        if m:
            return m.group(1)

        return ""

    # ─── Helpers ──────────────────────────────────────────

    def _extract_topic(self, task: str) -> str:
        """Extrae el tema principal de un task.

        'investiga sobre fotosintesis' -> 'fotosintesis'
        'explica como funciona X' -> 'X' (despues de 'como funciona')
        'explica que son los bitcoin' -> 'bitcoin' (limpia mas)
        'que es la fotosintesis' -> 'fotosintesis'
        'como funciona blockchain' -> 'blockchain'
        """
        topic = task.lower().strip()

        # Aplicar prefijos secuencialmente hasta que no cambie
        prefixes_to_remove = [
            r"^investiga\s+(?:sobre |acerca de )?",
            r"^busca\s+(?:informacion\s+)?(?:sobre |acerca de )?",
            r"^explica\s+",
            r"^describe\s+",
            r"^documenta\s+",
            r"^que\s+(?:es|son)\s+",
            r"^como\s+(?:funciona\s+)?",
            r"^donde\s+esta\s+",
            r"^por\s+que\s+",
            r"^aprende\s+(?:sobre )?",
        ]
        max_iter = 5
        for _ in range(max_iter):
            prev = topic
            for p in prefixes_to_remove:
                topic = re.sub(p, "", topic, flags=re.IGNORECASE)
            # Limpiar stopwords iniciales en cada iteracion
            stop_leading = re.compile(
                r"^(?:el|la|los|las|un|una|unos|unas|de|del|al)\s+",
                re.IGNORECASE
            )
            while stop_leading.match(topic):
                topic = stop_leading.sub("", topic).strip()
            if topic == prev:
                break

        return topic.rstrip("?!.")

    def _execute_tool(self, tool: str, **kwargs) -> AgentStep:
        """Ejecuta una tool via ActionRegistry."""
        import time
        start = time.time()
        try:
            result = self.actions.execute(tool, **kwargs)
            duration = int((time.time() - start) * 1000)
            success = result.get("success", False)
            output = str(result.get("result", result.get("error", "")))
            return AgentStep(
                tool=tool,
                input=str(kwargs),
                output=output[:2000],  # Limitar output
                success=success,
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return AgentStep(
                tool=tool,
                input=str(kwargs),
                output=f"Error: {e}",
                success=False,
                duration_ms=duration,
            )

    def _parse_search_results(self, output: str) -> list:
        """Extrae items de busqueda del output string.

        El output puede ser:
        - Un string con "• item1\n• item2" (formato CLI)
        - Un string con un dict: "{'resultados': ['• item1', '• item2']}"
        - O con comillas dobles: '{"resultados": ["• item1", "• item2"]}'
        - Cualquier combinacion
        """
        items = []

        # Intentar parsear como dict (puede ser un Python dict stringificado)
        # Acepta tanto comillas simples como dobles
        try:
            # Buscar patron de lista de strings
            match = re.search(
                r"['\"]resultados['\"]:\s*\[(.*?)\](?=\s*$|\s*[,\}])",
                output, re.DOTALL
            )
            if match:
                list_content = match.group(1)
                # Extraer cada string de la lista (con •, [Wikipedia], etc)
                # Acepta comillas simples y dobles
                for item_match in re.finditer(
                    r"['\"]([^'\"]{30,})['\"]",
                    list_content
                ):
                    item = item_match.group(1)
                    # Limpiar el item
                    if item.startswith("•"):
                        item = item[1:].strip()
                    items.append(item)
                if items:
                    return items[:5]
        except Exception:
            pass

        # Fallback: buscar lineas que empiecen con •
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("•"):
                items.append(line[1:].strip())

        return items[:5]

    def _extract_urls_from_results(self, output: str) -> list:
        """Extrae URLs utiles del output de busqueda, filtrando las problematicas.

        Filtra:
        - duckduckgo.com (redirects, /html, etc)
        - github.com (generalmente no tiene contenido para explicar)
        - wikipedia.org/wiki (Wikipedia ya da snippets buenos, el browse no aporta)
        - URLs con patrones 'login', 'redirect', 'javascript'
        - URLs con paths /api/, /track, /share
        """
        urls = []
        for match in re.finditer(r"\((https?://[^\)]+)\)", output):
            url = match.group(1)
            if self._is_url_valuable(url):
                urls.append(url)
        return urls[:3]

    def _is_url_valuable(self, url: str) -> bool:
        """Determina si una URL vale la pena visitarla (no es redirect/login/etc)."""
        url_lower = url.lower()

        # Patrones problematicos
        bad_patterns = [
            # DuckDuckGo: redirect, html version, changelog
            "duckduckgo.com/html",
            "duckduckgo.com/changelog",
            "duckduckgo.com/?",
            "duckduckgo.com/",
            # Wikipedia: mejor usar el snippet de busqueda
            "wikipedia.org/wiki/",
            # GitHub: a veces no tiene readme accesible
            # (mantener por si hay /blob/ explicativos)
            # Redes sociales y login
            "facebook.com/",
            "twitter.com/",
            "instagram.com/",
            "linkedin.com/",
            # Patrones de redirect/javascript
            "/redirect",
            "redirect=",
            "javascript:",
            "login.php",
            "login?",
            "signin?",
            # API endpoints
            "/api/",
            ".json",
            ".xml",
            # Patrones de tracking
            "utm_",
            "/track",
            "/share?",
        ]

        for pattern in bad_patterns:
            if pattern in url_lower:
                return False

        # Si llega aqui, la URL es valiosa
        return True

    def _parse_file_results(self, output: str) -> list:
        """Extrae paths de archivos del output de search_files.

        El output puede ser:
        - Un string con lineas "archivo.py: linea X" o "ruta/al/archivo"
        - Un dict: "{'resultados': [{'archivo': 'memory\\\\semantic.py', ...}]}"
        - O con comillas dobles
        """
        import re as _re
        files = []

        # Intentar parsear como dict (formato search_files)
        match = _re.search(
            r"['\"]resultados['\"]:\s*\[(.*?)\](?=\s*$|\s*[,\}])",
            output, _re.DOTALL
        )
        if match:
            list_content = match.group(1)
            # Extraer cada item {'archivo': 'path', 'linea': N, 'texto': '...'}
            for item_match in _re.finditer(
                r"['\"]archivo['\"]:\s*['\"]([^'\"]+)['\"]",
                list_content
            ):
                files.append(item_match.group(1))
            if files:
                return files[:5]

        # Fallback: buscar lineas con formato "archivo.py:" o "ruta/al/archivo"
        for line in output.split("\n"):
            line = line.strip()
            if line and not line.startswith("=") and not line.startswith("{"):
                match = _re.match(r"^([^\s:]+\.[a-z]+)", line)
                if match:
                    files.append(match.group(1))

        return files[:5]

    def _summarize(self, task: str, steps: list) -> str:
        """Genera un resumen estructurado de los pasos ejecutados."""
        lines = [f"\nResultados de la investigacion:\n"]

        successful = [s for s in steps if s.success]
        failed = [s for s in steps if not s.success]

        for i, step in enumerate(steps, 1):
            status = "✓" if step.success else "✗"
            lines.append(f"{status} Paso {i}: {step.tool} ({step.duration_ms}ms)")
            # Mostrar preview del output
            preview = step.output.split("\n")[0][:120]
            if preview:
                lines.append(f"   → {preview}")

        if successful:
            lines.append(f"\nResumen: {len(successful)}/{len(steps)} pasos exitosos.")
        if failed:
            lines.append(f"Errores: {len(failed)} pasos fallaron.")

        return "\n".join(lines)
