"""
Skill Builtin — Tools (Hermes Agent-style)
===========================================
Tools: web_search, read_file, write_file, search_files, run_command, python_eval, browse_website
Cada tool se auto-registra como accion en el ActionRegistry de Nexus.
"""

import json
import logging
import re as _re
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from skills.registry import Skill

logger = logging.getLogger("nexus.skills.tools")

# ─── Base del proyecto (para rutas seguras) ───────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def is_safe_path(path_str: str) -> bool:
    """Verifica si la ruta especificada está dentro de PROJECT_ROOT."""
    try:
        target = Path(path_str)
        if not target.is_absolute():
            target = PROJECT_ROOT / target
        target = target.resolve()
        return str(target).startswith(str(PROJECT_ROOT))
    except Exception:
        return False


def is_safe_command(command: str) -> bool:
    """Verifica si un comando es seguro (no intenta salir de PROJECT_ROOT)."""
    # 1. Bloquear retroceso de directorios (..)
    if ".." in command:
        return False
        
    # 2. Buscar posibles rutas absolutas en el comando
    # Ej: C:\Windows, /etc/passwd, C:/Users/somebody (que no sea PROJECT_ROOT)
    import re as _re
    abs_paths = _re.findall(r'(?:[a-zA-Z]:[\\/][^ \t\r\n\f\v"]+|/[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.\/]+)', command)
    for path in abs_paths:
        try:
            resolved = Path(path).resolve()
            if not str(resolved).startswith(str(PROJECT_ROOT)):
                return False
        except Exception:
            return False
            
    return True


# ======================================================================
#  FUNCIONES AUXILIARES (module-level, usadas por las closures)
# ======================================================================

def _clean_search_query(query: str) -> str:
    """Limpia una query de busqueda: quita stop words.
    Preserva mayusculas para acronimos (RAG, LLM, API, etc.)."""
    stop_words = {
        "sobre", "acerca", "respecto",
        "la", "el", "los", "las", "un", "una", "unos", "unas",
        "de", "del", "en", "por", "para", "con", "sin", "entre",
        "que", "cual", "cuales", "como", "cuando", "donde",
        "the", "a", "an", "of", "in", "on", "at", "by", "for",
        "with", "from", "to", "and", "or", "is", "are", "was",
        "about", "what", "which", "how", "where", "when",
        "todo", "toda", "todos", "todas", "muy", "mas", "más",
        "informacion", "información",
    }
    words = query.strip().split()
    cleaned = [w for w in words if w.lower() not in stop_words]
    return " ".join(cleaned) if cleaned else query.strip()


# Cache de resultados para evitar rate limiting
_SEARCH_CACHE = {}

def _web_search_html(clean_query: str, original_query: str = "", max_results: int = 5) -> dict:
    """Wikipedia API + GitHub fallback con cache."""
    cache_key = f"wiki:{clean_query}:{original_query}"
    if cache_key in _SEARCH_CACHE:
        return _SEARCH_CACHE[cache_key]

    try:
        wiki_query = clean_query if clean_query else original_query
        url = (
            "https://en.wikipedia.org/w/api.php"
            "?action=query&list=search&srsearch="
            f"{urllib.parse.quote(wiki_query)}"
            "&format=json&srlimit=5&utf8=1"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "NexusAI/1.0 (local research assistant)"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())

        results = data.get("query", {}).get("search", [])

        # Detectar acronimos en la query
        acronyms = [w for w in wiki_query.split() if w.isupper() and len(w) >= 2]

        def _has_acronym(res_list, acr_list):
            if not acr_list:
                return True
            import re as _ar
            for r in res_list[:5]:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                # Primero busca en el TITULO
                for acr in acr_list:
                    if _ar.search(r'\b' + acr + r'\b', title):
                        return True
                # Si no esta en el titulo, busca en el snippet CON contexto tech
                for acr in acr_list:
                    if _ar.search(r'\b' + acr + r'\b', snippet):
                        # Verificar contexto tecnologico
                        text = (title + " " + snippet).lower()
                        if any(t in text for t in
                            ["ai", "llm", "model", "retrieval", "generation",
                             "computer", "computing", "algorithm", "science",
                             "neural", "deep learning", "machine learning",
                             "data", "search", "vector", "embedding",
                             "language model", "nlp", "transformer",
                             "knowledge", "semantic", "index", "database"]):
                            return True
            return False

        # ─── Si hay acronimos, reordenar: primero los resultados que los contengan
        # en contexto tecnologico, luego el resto
        if acronyms:
            def _relevance_score(r):
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                text = (title + " " + snippet).lower()
                score = 0
                # +2 si el titulo contiene el acronimo como palabra
                for acr in acronyms:
                    if _re.search(r'\b' + acr + r'\b', title):
                        score += 2
                    if _re.search(r'\b' + acr + r'\b', snippet):
                        score += 1
                # +1 por cada termino tecnologico
                for t in ["retrieval", "generation", "computer", "computing",
                          "algorithm", "neural", "vector", "database",
                          "machine learning", "artificial intelligence",
                          "nlp", "transformer", "embedding", "semantic"]:
                    if t in text:
                        score += 1
                return score
            
            results.sort(key=_relevance_score, reverse=True)

        # Si no hay resultados o son malos, probar alternativas
        if not results:
            alt_queries = []
            if acronyms:
                for acr in acronyms[:1]:  # Solo la primera alternativa mas relevante
                    alt_queries.append(f"{acr} computer science")
            if len(wiki_query.split()) <= 2 and not alt_queries:
                alt_queries.append(f"{wiki_query} concept")

            for aq in alt_queries[:2]:
                try:
                    aurl = (
                        "https://en.wikipedia.org/w/api.php"
                        "?action=query&list=search&srsearch="
                        f"{urllib.parse.quote(aq)}&format=json&srlimit=5&utf8=1"
                    )
                    areq = urllib.request.Request(aurl, headers={"User-Agent": "NexusAI/1.0"})
                    with urllib.request.urlopen(areq, timeout=6) as aresp:
                        alt_data = json.loads(aresp.read().decode())
                    alt_res = alt_data.get("query", {}).get("search", [])
                    if alt_res and (not acronyms or _has_acronym(alt_res, acronyms)):
                        results, wiki_query = alt_res, aq
                        break
                except Exception:
                    continue

        # ─── FASE 2: DuckDuckGo HTML (busqueda web general) ───
        # Esto SI indexa la web general, no solo Wikipedia.
        # Wikipedia API a veces devuelve resultados irrelevantes
        # (ej: 'fotosintesis' devuelve peliculas mexicanas)
        # por eso siempre intentamos DDG ademas
        ddg_results = []
        try:
            import re as _ddg_re
            import html as _ddg_html
            from urllib.parse import unquote

            ddg_html_url = "https://html.duckduckgo.com/html/"
            data_obj = urllib.parse.urlencode({"q": clean_query or original_query}).encode()
            req = urllib.request.Request(
                ddg_html_url, data=data_obj,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                html_content = resp.read().decode("utf-8", errors="ignore")

            # Regex simple: cada resultado es un <a class="result__a" href="...">title</a>
            # seguido de un <td class="result__snippet">snippet</td>
            # Capturamos con re.DOTALL para que el snippet incluya saltos de linea
            pattern = _ddg_re.compile(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'class="result__snippet"[^>]*>(.*?)</(?:td|div|a)',
                _ddg_re.DOTALL
            )
            for match in pattern.finditer(html_content):
                url = match.group(1)
                # Limpiar URL de DuckDuckGo
                if "/l/?uddg=" in url:
                    um = _ddg_re.search(r"uddg=([^&]+)", url)
                    if um:
                        url = unquote(um.group(1))
                # Limpiar title y snippet (quitar tags HTML)
                title = _ddg_re.sub(r"<[^>]+>", "", match.group(2)).strip()
                snippet = _ddg_re.sub(r"<[^>]+>", "", match.group(3)).strip()
                title = _ddg_html.unescape(title)
                snippet = _ddg_html.unescape(snippet)
                # Quitar espacios multiples
                title = _ddg_re.sub(r"\s+", " ", title).strip()
                snippet = _ddg_re.sub(r"\s+", " ", snippet).strip()
                if title and url:
                    ddg_results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": url,
                    })
        except Exception as e:
            pass

        # Combinar: Wikipedia primero (es mas confiable) + DDG (web general)
        combined = []
        seen_urls = set()
        # Wikipedia primero
        for r in results[:max_results]:
            url = r.get("url", "")
            if url and url not in seen_urls:
                combined.append({
                    "title": r.get("title", ""),
                    "snippet": re.sub(r"<[^>]+>", "", r.get("snippet", "")).strip(),
                    "url": url,
                    "fuente": "Wikipedia",
                })
                seen_urls.add(url)
        # DDG para llenar el resto
        for r in ddg_results[:max_results]:
            url = r.get("url", "")
            if url and url not in seen_urls and len(combined) < max_results:
                combined.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": url,
                    "fuente": "DuckDuckGo",
                })
                seen_urls.add(url)

        if combined:
            out = []
            for r in combined[:max_results]:
                title = r["title"][:120]
                snippet = r["snippet"][:200]
                url = r["url"]
                fuente = r["fuente"]
                out.append(f"• {title} — {snippet} ({url}) [{fuente}]")
            result = {
                "resultados": out[:max_results],
                "total": len(out),
                "consulta": clean_query or original_query,
                "fuente": "Wikipedia+DuckDuckGo" if any(r["fuente"] == "DuckDuckGo" for r in combined) else "Wikipedia",
            }
            _SEARCH_CACHE[cache_key] = result
            return result

        # Si llegamos aqui, no se encontro nada
        result = {"resultados": [], "mensaje": f"No encontre resultados para '{original_query or clean_query}'"}
        _SEARCH_CACHE[cache_key] = result
        return result
    except Exception as e:
        err = {"error": f"Error en busqueda: {e}"}
        _SEARCH_CACHE[cache_key] = err
        return err


# ======================================================================
#  REGISTRO DE LA SKILL
# ======================================================================

def register() -> Skill:
    skill = Skill(
        name="tools",
        description="Herramientas: busqueda web, archivos, comandos, Python",
        version="1.0.0",
        author="Nexus + Hermes Agent",
    )

    # ─── 1. web_search ───────────────────────────────────────────────
    def _web_search(query: str = "", max_results: int = 5):
        if not query:
            return {"error": "No especificaste que buscar. Ej: 'busca noticias de IA'"}
        clean_query = _clean_search_query(query)
        try:
            ddg_url = (
                f"https://api.duckduckgo.com/?q={urllib.parse.quote(clean_query)}"
                f"&format=json&no_html=1&skip_disambig=1"
            )
            req = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode())

            results = []
            abstract = data.get("AbstractText", "")
            source = data.get("AbstractSource", "")
            response_type = data.get("Type", "")
            if abstract:
                results.append(f"[{source}] {abstract}")

            for topic in data.get("RelatedTopics", [])[:max_results]:
                if "Text" in topic:
                    url_t = topic.get("FirstURL", "")
                    results.append(f"• {topic['Text']} ({url_t})" if url_t else f"• {topic['Text']}")
                elif "Topics" in topic:
                    for sub in topic["Topics"][:3]:
                        if "Text" in sub:
                            results.append(f"• {sub['Text']}")

            # Si el query tiene acronimos, verificar que los resultados los contengan
            # como termino tecnico (no solo en pagina de desambiguacion)
            ddg_type = data.get("Type", "")
            ddg_acronyms = [w for w in clean_query.split() if w.isupper() and len(w) >= 2]
            if ddg_acronyms and (ddg_type == "D" or not results):
                # Type D = desambiguacion → buscar en Wikipedia con contexto
                results = []
            if not results:
                return _web_search_html(clean_query, query, max_results)

            return {"resultados": results[:max_results], "total": len(results), "consulta": clean_query}
        except urllib.error.URLError:
            return {"error": "Sin conexion a internet. No puedo buscar en la web."}
        except Exception as e:
            return {"error": f"Error en busqueda web: {e}"}

    skill.register_action(
        name="web_search",
        description="Busca informacion en la web. Usa Wikipedia + DuckDuckGo HTML (web general). GitHub NO se usa (no es relevante para aprendizaje).",
        handler=_web_search,
        parameters={
            "query": {"type": "string", "description": "Termino de busqueda"},
            "max_results": {"type": "integer", "description": "Maximo de resultados (1-10)", "default": 5},
        },
    )

    # ─── 2. read_file ───────────────────────────────────────────────
    def _read_file(path: str = "", max_lines: int = 50,
                   from_line: int = 0, search: str = ""):
        """Lee un archivo del proyecto.

        Args:
            path: Ruta al archivo
            max_lines: Cantidad maxima de lineas a devolver (default 50)
            from_line: Desde que linea empezar (0-indexed, default 0)
            search: Si se especifica, busca esta cadena y devuelve
                    las lineas alrededor (10 antes + N despues)
        """
        if not path:
            return {"error": "Especifica la ruta del archivo. Ej: 'README.md'"}
        try:
            target = Path(path)
            if not target.is_absolute():
                target = PROJECT_ROOT / target
            target = target.resolve()
            if not str(target).startswith(str(PROJECT_ROOT)):
                return {"error": f"No puedo leer archivos fuera del proyecto: {target}"}
            if not target.exists():
                return {"error": f"Archivo no encontrado: {path}"}
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            # Si se busca una cadena, encontrar la linea y mostrar contexto
            search_line = None
            if search:
                for i, line in enumerate(lines):
                    if search in line:
                        search_line = i + 1  # 1-indexed para el usuario
                        # Mostrar 5 lineas antes + 30 despues
                        start = max(0, i - 5)
                        end = min(len(lines), i + 30)
                        return {
                            "archivo": str(target.relative_to(PROJECT_ROOT)),
                            "total_lineas": len(lines),
                            "search_match_linea": search_line,
                            "lineas": lines[start:end],
                            "rango": f"lineas {start + 1}-{end}",
                            "truncado": end < len(lines),
                        }

            # Modo normal: devolver lineas desde from_line
            start_idx = max(0, from_line)
            end_idx = min(len(lines), start_idx + max_lines)
            return {
                "archivo": str(target.relative_to(PROJECT_ROOT)),
                "total_lineas": len(lines),
                "lineas": lines[start_idx:end_idx],
                "rango": f"lineas {start_idx + 1}-{end_idx}",
                "truncado": end_idx < len(lines),
            }
        except Exception as e:
            return {"error": f"Error leyendo archivo: {e}"}

    skill.register_action(
        name="read_file",
        description="Lee el contenido de un archivo de texto.",
        handler=_read_file,
        parameters={
            "path": {"type": "string", "description": "Ruta del archivo (ej: 'docs/README.md')"},
            "max_lines": {"type": "integer", "description": "Maximo de lineas a mostrar", "default": 50},
        },
    )

    # ─── 3. write_file ──────────────────────────────────────────────
    def _write_file(path: str = "", content: str = ""):
        if not path:
            return {"error": "Especifica la ruta del archivo"}
        if not content:
            return {"error": "Especifica el contenido a escribir"}
        try:
            target = Path(path)
            if not target.is_absolute():
                target = PROJECT_ROOT / target
            target = target.resolve()
            if not str(target).startswith(str(PROJECT_ROOT)):
                return {"error": f"No puedo escribir fuera del proyecto: {target}"}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            size = len(content.encode("utf-8"))
            return {"archivo": str(target.relative_to(PROJECT_ROOT)), "bytes": size, "lineas": len(content.splitlines()), "mensaje": f"Archivo escrito ({size} bytes)"}
        except Exception as e:
            return {"error": f"Error escribiendo archivo: {e}"}

    skill.register_action(
        name="write_file",
        description="Crea o sobreescribe un archivo con contenido nuevo.",
        handler=_write_file,
        parameters={
            "path": {"type": "string", "description": "Ruta del archivo"},
            "content": {"type": "string", "description": "Contenido completo del archivo"},
        },
    )

    # ─── 4. search_files ────────────────────────────────────────────
    def _search_files(pattern: str = "", file_pattern: str = "*", path: str = "."):
        if not pattern:
            return {"error": "Especifica el texto a buscar"}
        try:
            search_path = Path(path)
            if not search_path.is_absolute():
                search_path = PROJECT_ROOT / search_path
            search_path = search_path.resolve()
            if not str(search_path).startswith(str(PROJECT_ROOT)):
                return {"error": f"No puedo buscar archivos fuera del proyecto: {search_path}"}
            results, scanned = [], 0
            for fpath in sorted(search_path.rglob(file_pattern)):
                if not fpath.is_file():
                    continue
                scanned += 1
                try:
                    for i, line in enumerate(fpath.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if _re.search(pattern, line, _re.IGNORECASE):
                            results.append({"archivo": str(fpath.relative_to(PROJECT_ROOT)), "linea": i, "texto": line.strip()[:100]})
                            if len(results) >= 20:
                                break
                except Exception:
                    pass
                if len(results) >= 20:
                    break
            return {"resultados": results[:20], "total_encontrados": len(results), "archivos_escaneados": scanned, "patron": pattern}
        except Exception as e:
            return {"error": f"Error en busqueda: {e}"}

    skill.register_action(
        name="search_files",
        description="Busca texto o patrones en archivos del proyecto (como grep).",
        handler=_search_files,
        parameters={
            "pattern": {"type": "string", "description": "Texto o expresion regular a buscar"},
            "file_pattern": {"type": "string", "description": "Filtro de archivos (ej: '*.py')", "default": "*"},
            "path": {"type": "string", "description": "Directorio donde buscar", "default": "."},
        },
    )

    # ─── 5. run_command ─────────────────────────────────────────────
    def _run_command(command: str = "", timeout: int = 15):
        if not command:
            return {"error": "Especifica el comando a ejecutar"}
        if not is_safe_command(command):
            return {"error": f"Comando bloqueado por motivos de seguridad: {command}"}
            
        # Comprobar restricciones en modo API (F6.2)
        try:
            from config import INTERFACE
            api_enabled = INTERFACE.get("api", {}).get("enabled", False)
            allowed_cmds = INTERFACE.get("api", {}).get("allowed_commands", [])
        except Exception:
            api_enabled = False
            allowed_cmds = []

        if api_enabled:
            cmd_clean = command.strip()
            if not any(cmd_clean.startswith(allowed) for allowed in allowed_cmds):
                return {"error": f"Comando no permitido en modo API: {command}"}
        try:
            # Usar encoding latin-1 para evitar UnicodeDecodeError con
            # salida de comandos Windows (ej: 'dir' en cp850/cp1252)
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=False,  # bytes para evitar problemas de encoding
                timeout=timeout,
            )
            # Decodificar manualmente con fallback
            def _decode(b):
                if not b:
                    return ""
                for enc in ("utf-8", "cp1252", "latin-1"):
                    try:
                        return b.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return b.decode("utf-8", errors="replace")

            stdout = _decode(result.stdout).strip()
            stderr = _decode(result.stderr).strip()
            out = []
            if stdout:
                out.append("STDOUT:")
                out.extend(stdout.splitlines()[:30])
            if stderr:
                out.append("STDERR:")
                out.extend(stderr.splitlines()[:10])
            return {"comando": command, "salida": "\n".join(out) if out else "(sin salida)", "codigo_retorno": result.returncode}
        except subprocess.TimeoutExpired:
            return {"error": f"Timeout de {timeout}s", "comando": command}
        except Exception as e:
            return {"error": f"Error: {e}"}

    skill.register_action(
        name="run_command",
        description="Ejecuta un comando de shell y devuelve la salida.",
        handler=_run_command,
        parameters={
            "command": {"type": "string", "description": "Comando a ejecutar"},
            "timeout": {"type": "integer", "description": "Timeout en segundos", "default": 15},
        },
    )

    # ─── 6. python_eval ─────────────────────────────────────────────
    def _python_eval(expression: str = ""):
        if not expression:
            return {"error": "Especifica la expresion a evaluar"}
        try:
            import ast, operator as _op
            safe_ops = {ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul, ast.Div: _op.truediv,
                        ast.FloorDiv: _op.floordiv, ast.Pow: _op.pow, ast.Mod: _op.mod, ast.USub: _op.neg, ast.UAdd: _op.pos}

            def _eval(node):
                if isinstance(node, ast.Expression):
                    return _eval(node.body)
                if isinstance(node, ast.Constant):
                    return node.value
                if isinstance(node, ast.BinOp):
                    return safe_ops.get(type(node.op), lambda a, b: (_ for _ in ()).throw(ValueError(f"Op no permitido: {type(node.op).__name__}")))(_eval(node.left), _eval(node.right))
                if isinstance(node, ast.UnaryOp):
                    return safe_ops.get(type(node.op), lambda x: (_ for _ in ()).throw(ValueError(f"Op no permitido: {type(node.op).__name__}")))(_eval(node.operand))
                if isinstance(node, (ast.List, ast.Tuple)):
                    return type(node)(_eval(e) for e in node.elts)
                if isinstance(node, ast.Dict):
                    return {_eval(k): _eval(v) for k, v in zip(node.keys, node.values)}
                if isinstance(node, ast.Name) and node.id in ("True", "False", "None"):
                    return {"True": True, "False": False, "None": None}[node.id]
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("len", "str", "int", "float", "abs", "round", "min", "max", "sum", "list", "dict", "tuple", "set", "sorted", "reversed"):
                    return globals()["__builtins__"][node.func.id](*(_eval(a) for a in node.args))
                raise ValueError(f"Expresion no soportada: {type(node).__name__}")

            tree = ast.parse(expression, mode="eval")
            result = _eval(tree.body)
            return {"expresion": expression, "resultado": repr(result), "tipo": type(result).__name__}
        except SyntaxError:
            return {"error": f"Error de sintaxis en: {expression}"}
        except Exception as e:
            return {"error": f"Error: {e}"}

    skill.register_action(
        name="python_eval",
        description="Evalua una expresion Python con operaciones matematicas y funciones basicas.",
        handler=_python_eval,
        parameters={
            "expression": {"type": "string", "description": "Expresion Python a evaluar (ej: '2 + 2 * 3')"},
        },
    )

    # ─── 7. browse_website ──────────────────────────────────────────
    def _browse_website(url: str = ""):
        if not url:
            return {"error": "Especifica la URL. Ej: 'https://kudawa.com'"}
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Quitar scripts, styles, comments, nav, footer (no son contenido)
            html = _re.sub(r'<script\b[^>]*>.*?</script>', ' ', html,
                           flags=_re.IGNORECASE | _re.DOTALL)
            html = _re.sub(r'<style\b[^>]*>.*?</style>', ' ', html,
                           flags=_re.IGNORECASE | _re.DOTALL)
            html = _re.sub(r'<!--.*?-->', ' ', html, flags=_re.DOTALL)
            html = _re.sub(r'<nav\b[^>]*>.*?</nav>', ' ', html,
                           flags=_re.IGNORECASE | _re.DOTALL)
            html = _re.sub(r'<footer\b[^>]*>.*?</footer>', ' ', html,
                           flags=_re.IGNORECASE | _re.DOTALL)
            html = _re.sub(r'<header\b[^>]*>.*?</header>', ' ', html,
                           flags=_re.IGNORECASE | _re.DOTALL)

            # Title
            title_m = _re.search(r'<title[^>]*>(.*?)</title>', html, _re.IGNORECASE | _re.DOTALL)
            titulo = _re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else url

            # Extraer textos de parrafos, headings, listas, etc
            textos = _re.findall(
                r'<(?:p|h[1-6]|li|article|section)\b[^>]*>(.*?)</(?:p|h[1-6]|li|article|section)>',
                html, _re.IGNORECASE | _re.DOTALL
            )
            contenido = []
            for t in textos:
                # Quitar HTML interno
                clean = _re.sub(r"<[^>]+>", " ", t)
                clean = _re.sub(r'&[a-z]+;', ' ', clean)  # &nbsp; etc
                clean = _re.sub(r'&#\d+;', ' ', clean)   # &#1234;
                clean = _re.sub(r'\s+', ' ', clean).strip()
                if len(clean) > 30:  # Solo textos con substance
                    contenido.append(clean)

            # Si no hay parrafos, buscar divs con mucho texto
            if not contenido:
                body = _re.search(r'<body[^>]*>(.*?)</body>', html, _re.DOTALL)
                if body:
                    texto = _re.sub(r"<[^>]+>", " ", body.group(1))
                    texto = _re.sub(r'\s+', ' ', texto).strip()
                    if len(texto) > 30:
                        contenido = [texto[:2000]]

            return {
                "titulo": titulo,
                "contenido": "\n".join(contenido[:15]) if contenido else "(sin contenido visible)",
                "url": url,
                "total_parrafos": len(contenido),
            }
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError:
            return {"error": f"No se pudo conectar a {url}"}
        except Exception as e:
            return {"error": f"Error: {e}"}

    skill.register_action(
        name="browse_website",
        description="Obtiene el contenido textual de una pagina web a partir de una URL.",
        handler=_browse_website,
        parameters={
            "url": {"type": "string", "description": "URL completa (ej: 'https://kudawa.com')"},
        },
    )

    return skill
