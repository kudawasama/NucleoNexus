"""
Skill Builtin — Tools (Hermes Agent-style)
===========================================
Tools: web_search, read_file, write_file, search_files, run_command, python_eval
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


def register() -> Skill:
    """Registra y devuelve la skill de herramientas tipo Hermes Agent."""
    skill = Skill(
        name="tools",
        description="Herramientas: busqueda web, archivos, comandos, Python",
        version="1.0.0",
        author="Nexus + Hermes Agent",
    )

    # ═══════════════════════════════════════════════════════════
    #  1. web_search — busca en la web via DuckDuckGo
    # ═══════════════════════════════════════════════════════════
    def _web_search(query: str = "", max_results: int = 5):
        """Busca en la web usando DuckDuckGo (gratuito, sin API key).

        Args:
            query: Termino de busqueda
            max_results: Max. resultados a devolver (default 5)
        """
        if not query:
            return {"error": "No especificaste que buscar. Ej: 'busca noticias de IA'"}
        try:
            url = (
                f"https://api.duckduckgo.com/"
                f"?q={urllib.parse.quote(query)}"
                f"&format=json&no_html=1&skip_disambig=1"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            results = []
            # Respuesta directa (Abstract)
            abstract = data.get("AbstractText", "")
            source = data.get("AbstractSource", "")
            if abstract:
                results.append(f"[{source}] {abstract}")

            # Temas relacionados
            topics = data.get("RelatedTopics", [])
            for topic in topics[:max_results]:
                if "Text" in topic:
                    text = topic["Text"]
                    url_t = topic.get("FirstURL", "")
                    if url_t:
                        results.append(f"• {text} ({url_t})")
                    else:
                        results.append(f"• {text}")
                elif "Topics" in topic:
                    for sub in topic["Topics"][:3]:
                        if "Text" in sub:
                            results.append(f"• {sub['Text']}")

            if not results:
                return {
                    "resultados": [],
                    "mensaje": f"No encontre resultados para '{query}'",
                }

            return {
                "resultados": results[:max_results],
                "total": len(results),
                "consulta": query,
            }
        except urllib.error.URLError:
            return {"error": "Sin conexion a internet. No puedo buscar en la web."}
        except Exception as e:
            return {"error": f"Error en busqueda web: {e}"}

    skill.register_action(
        name="web_search",
        description="Busca informacion en la web. Usa DuckDuckGo (gratis, sin API key).",
        handler=_web_search,
        parameters={
            "query": {
                "type": "string",
                "description": "Termino de busqueda (ej: 'noticias IA 2025')",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximo de resultados (1-10)",
                "default": 5,
            },
        },
    )

    # ═══════════════════════════════════════════════════════════
    #  2. read_file — lee el contenido de un archivo
    # ═══════════════════════════════════════════════════════════
    def _read_file(path: str = "", max_lines: int = 50):
        """Lee un archivo de texto.

        Args:
            path: Ruta al archivo (relativa al proyecto o absoluta)
            max_lines: Max. lineas a leer (default 50)
        """
        if not path:
            return {"error": "Especifica la ruta del archivo. Ej: 'README.md'"}
        try:
            target = Path(path)
            if not target.is_absolute():
                target = PROJECT_ROOT / target
            target = target.resolve()

            # Seguridad: no salir del proyecto
            if not str(target).startswith(str(PROJECT_ROOT)):
                return {"error": f"No puedo leer archivos fuera del proyecto: {target}"}

            if not target.exists():
                return {"error": f"Archivo no encontrado: {path}"}
            if not target.is_file():
                return {"error": f"No es un archivo: {path}"}

            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total = len(lines)
            muestra = lines[:max_lines]

            return {
                "archivo": str(target.relative_to(PROJECT_ROOT)),
                "total_lineas": total,
                "lineas": muestra,
                "truncado": total > max_lines,
            }
        except Exception as e:
            return {"error": f"Error leyendo archivo: {e}"}

    skill.register_action(
        name="read_file",
        description="Lee el contenido de un archivo de texto.",
        handler=_read_file,
        parameters={
            "path": {
                "type": "string",
                "description": "Ruta del archivo (ej: 'docs/README.md' o 'config.py')",
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximo de lineas a mostrar (default 50)",
                "default": 50,
            },
        },
    )

    # ═══════════════════════════════════════════════════════════
    #  3. write_file — escribe o sobreescribe un archivo
    # ═══════════════════════════════════════════════════════════
    def _write_file(path: str = "", content: str = ""):
        """Crea o sobreescribe un archivo con el contenido dado.

        Args:
            path: Ruta del archivo a crear/escribir
            content: Contenido a escribir
        """
        if not path:
            return {"error": "Especifica la ruta del archivo"}
        if not content:
            return {"error": "Especifica el contenido a escribir"}
        try:
            target = Path(path)
            if not target.is_absolute():
                target = PROJECT_ROOT / target
            target = target.resolve()

            # Seguridad: no salir del proyecto
            if not str(target).startswith(str(PROJECT_ROOT)):
                return {"error": f"No puedo escribir fuera del proyecto: {target}"}

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            size = len(content.encode("utf-8"))
            return {
                "archivo": str(target.relative_to(PROJECT_ROOT)),
                "bytes": size,
                "lineas": len(content.splitlines()),
                "mensaje": f"Archivo escrito correctamente ({size} bytes)",
            }
        except Exception as e:
            return {"error": f"Error escribiendo archivo: {e}"}

    skill.register_action(
        name="write_file",
        description="Crea o sobreescribe un archivo con contenido nuevo.",
        handler=_write_file,
        parameters={
            "path": {
                "type": "string",
                "description": "Ruta del archivo (ej: 'notas.txt' o 'src/script.py')",
            },
            "content": {
                "type": "string",
                "description": "Contenido completo del archivo",
            },
        },
    )

    # ═══════════════════════════════════════════════════════════
    #  4. search_files — busca texto en archivos del proyecto
    # ═══════════════════════════════════════════════════════════
    def _search_files(pattern: str = "", file_pattern: str = "*", path: str = "."):
        """Busca un patron de texto en archivos del proyecto (grep-like).

        Args:
            pattern: Texto o regex a buscar
            file_pattern: Patron de archivo (ej: '*.py', '*.md')
            path: Directorio donde buscar
        """
        if not pattern:
            return {"error": "Especifica el texto a buscar"}
        try:
            search_path = Path(path)
            if not search_path.is_absolute():
                search_path = PROJECT_ROOT / search_path
            search_path = search_path.resolve()

            if not search_path.exists():
                return {"error": f"Directorio no encontrado: {path}"}

            results = []
            files_scanned = 0

            for fpath in sorted(search_path.rglob(file_pattern)):
                if not fpath.is_file():
                    continue
                files_scanned += 1
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                    lines = text.splitlines()
                    for i, line in enumerate(lines, 1):
                        if _re.search(pattern, line, _re.IGNORECASE):
                            rel = fpath.relative_to(PROJECT_ROOT)
                            context = line.strip()[:100]
                            results.append({
                                "archivo": str(rel),
                                "linea": i,
                                "texto": context,
                            })
                            if len(results) >= 20:
                                break
                except Exception:
                    pass
                if len(results) >= 20:
                    break

            return {
                "resultados": results[:20],
                "total_encontrados": len(results),
                "archivos_escaneados": files_scanned,
                "patron": pattern,
            }
        except Exception as e:
            return {"error": f"Error en busqueda: {e}"}

    skill.register_action(
        name="search_files",
        description="Busca texto o patrones en archivos del proyecto (como grep).",
        handler=_search_files,
        parameters={
            "pattern": {
                "type": "string",
                "description": "Texto o expresion regular a buscar",
            },
            "file_pattern": {
                "type": "string",
                "description": "Filtro de archivos (ej: '*.py', '*.md', '*')",
                "default": "*",
            },
            "path": {
                "type": "string",
                "description": "Directorio donde buscar (default: '.')",
                "default": ".",
            },
        },
    )

    # ═══════════════════════════════════════════════════════════
    #  5. run_command — ejecuta un comando de shell
    # ═══════════════════════════════════════════════════════════
    def _run_command(command: str = "", timeout: int = 15):
        """Ejecuta un comando de shell y devuelve la salida.

        Args:
            command: Comando a ejecutar (shell, bash en Windows)
            timeout: Timeout en segundos (default 15)
        """
        if not command:
            return {"error": "Especifica el comando a ejecutar"}
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = []
            if result.stdout:
                lines = result.stdout.strip().splitlines()
                output.append("STDOUT:")
                output.extend(lines[:30])  # Max 30 lines
            if result.stderr:
                lines = result.stderr.strip().splitlines()
                output.append("STDERR:")
                output.extend(lines[:10])  # Max 10 lines stderr
            if not output:
                output = ["(sin salida)"]

            return {
                "comando": command,
                "salida": "\n".join(output),
                "codigo_retorno": result.returncode,
                "truncado": len(result.stdout.splitlines()) > 30
                            or len(result.stderr.splitlines()) > 10,
            }
        except subprocess.TimeoutExpired:
            return {
                "error": f"Comando agoto el timeout de {timeout}s",
                "comando": command,
            }
        except Exception as e:
            return {"error": f"Error ejecutando comando: {e}"}

    skill.register_action(
        name="run_command",
        description="Ejecuta un comando de shell y devuelve la salida.",
        handler=_run_command,
        parameters={
            "command": {
                "type": "string",
                "description": "Comando a ejecutar (ej: 'ls -la', 'git log --oneline -5')",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout maximo en segundos (default 15)",
                "default": 15,
            },
        },
    )

    # ═══════════════════════════════════════════════════════════
    #  6. python_eval — evalua una expresion Python
    # ═══════════════════════════════════════════════════════════
    def _python_eval(expression: str = ""):
        """Evalua una expresion Python y devuelve el resultado.

        Segura: solo permite expresiones literales (ast.literal_eval).
        Para operaciones matematicas usa eval() en un entorno restringido.

        Args:
            expression: Expresion Python a evaluar
        """
        if not expression:
            return {"error": "Especifica la expresion a evaluar"}
        try:
            # Operaciones matematicas seguras
            import ast
            import operator as _op

            # Whitelist de operadores
            safe_ops = {
                ast.Add: _op.add,
                ast.Sub: _op.sub,
                ast.Mult: _op.mul,
                ast.Div: _op.truediv,
                ast.FloorDiv: _op.floordiv,
                ast.Pow: _op.pow,
                ast.Mod: _op.mod,
                ast.USub: _op.neg,
                ast.UAdd: _op.pos,
            }

            def _safe_eval(node):
                if isinstance(node, ast.Expression):
                    return _safe_eval(node.body)
                elif isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    op_func = safe_ops.get(type(node.op))
                    if op_func is None:
                        raise ValueError(f"Operador no permitido: {type(node.op).__name__}")
                    return op_func(_safe_eval(node.left), _safe_eval(node.right))
                elif isinstance(node, ast.UnaryOp):
                    op_func = safe_ops.get(type(node.op))
                    if op_func is None:
                        raise ValueError(f"Operador no permitido: {type(node.op).__name__}")
                    return op_func(_safe_eval(node.operand))
                elif isinstance(node, ast.List):
                    return [_safe_eval(el) for el in node.elts]
                elif isinstance(node, ast.Dict):
                    return {_safe_eval(k): _safe_eval(v) for k, v in zip(node.keys, node.values)}
                elif isinstance(node, ast.Tuple):
                    return tuple(_safe_eval(el) for el in node.elts)
                elif isinstance(node, ast.Name) and node.id in ("True", "False", "None"):
                    return {"True": True, "False": False, "None": None}[node.id]
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in ("len", "str", "int", "float", "abs", "round", "min", "max", "sum", "list", "dict", "tuple", "set", "sorted", "reversed"):
                        args = [_safe_eval(a) for a in node.args]
                        kwargs = {k.arg: _safe_eval(k.value) for k in node.keywords}
                        return globals()["__builtins__"][node.func.id](*args, **kwargs)
                    raise ValueError(f"Funcion no permitida: {node.func.id}")
                else:
                    raise ValueError(f"Expresion no soportada: {type(node).__name__}")

            tree = ast.parse(expression, mode="eval")
            result = _safe_eval(tree.body)

            return {
                "expresion": expression,
                "resultado": repr(result),
                "tipo": type(result).__name__,
            }
        except SyntaxError:
            return {"error": f"Error de sintaxis en: {expression}"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Error evaluando expresion: {e}"}

    skill.register_action(
        name="python_eval",
        description="Evalua una expresion Python con operaciones matematicas y funciones basicas.",
        handler=_python_eval,
        parameters={
            "expression": {
                "type": "string",
                "description": "Expresion Python a evaluar (ej: '2 + 2 * 3', 'len([1,2,3])')",
            },
        },
    )

    return skill
