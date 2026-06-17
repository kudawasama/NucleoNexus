"""
Skill — Busqueda Web
=====================
Busca en internet usando DuckDuckGo Lite (sin API key).
Requiere: pip install requests (opcional, si no esta instalado falla graceful)
"""

import urllib.request
import urllib.parse
import re
import json
from skills.registry import Skill


def register() -> Skill:
    skill = Skill(name="websearch", description="Busca informacion en internet", version="1.0.0")

    def _buscar_web(query: str = ""):
        if not query.strip():
            return {"respuesta": "Que quieres buscar? Ej: busca receta de pizza"}

        try:
            url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Extraer resultados del HTML de DuckDuckGo Lite
            results = []
            for match in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>', html, re.DOTALL):
                url_result = match.group(1)
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                if title and url_result:
                    results.append(f"• {title}\n  {url_result[:80]}")

            if not results:
                # Fallback: extraer cualquier enlace relevante
                for match in re.finditer(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
                    url_result = match.group(1)
                    title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                    if title and url_result and "duckduckgo" not in url_result:
                        results.append(f"• {title}\n  {url_result[:80]}")

            if results:
                return {"respuesta": f"Resultados para '{query}':\n" + "\n".join(results[:5])}
            else:
                return {"respuesta": f"No encontre resultados para '{query}'. Intenta con otras palabras."}

        except Exception as e:
            return {"respuesta": f"Error en la busqueda: {e}. Sin conexion a internet?"}

    skill.register_action("buscar_web", "Busca informacion en internet", _buscar_web,
        parameters={"query": {"type": "string", "description": "Que buscar"}})

    return skill
