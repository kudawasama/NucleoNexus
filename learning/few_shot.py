"""
Núcleo Nexus — Dataset Few-Shot + Herramientas para Qwen 0.5B
==============================================================
Enseña a Qwen 0.5B a usar herramientas: buscar en web, calcular,
consultar memoria. Cada ejemplo muestra entrada → JSON con accion.

El sistema ejecuta la accion y Qwen da la respuesta final.
"""
# ─── DESCRIPCION DE HERRAMIENTAS ───────────────────────────
# Se inyecta antes de los ejemplos para que Qwen sepa que puede usar
TOOLS_DESCRIPTION = """HERRAMIENTAS DISPONIBLES:
- web_search(query): Busca informacion actualizada en internet
- calcular(expresion): Resuelve operaciones matematicas
- buscar_memoria(tema): Busca hechos en mi base de conocimiento
- hora_actual(): Devuelve la fecha y hora actual
- pdf_rename(path): Renombra facturas PDF con formato NUMERO - PROVEEDOR - MES AÑO
"""

FEW_SHOT_EXAMPLES = [
    # ─── RESPONDER (conocimiento directo) ───
    {
        "input": "explicame como se hace una multiplicacion",
        "output": {
            "razonamiento": "El usuario pregunta sobre multiplicacion. Puedo responder con mi conocimiento.",
            "accion": "responder",
            "respuesta": "Multiplicar es sumar un numero varias veces. 3x4 significa sumar 3 cuatro veces: 3+3+3+3 = 12."
        }
    },
    # ─── BUSCAR EN WEB ───
    {
        "input": "quien gano el partido de chile ayer",
        "output": {
            "razonamiento": "No tengo informacion actualizada sobre deportes. Debo buscar en internet.",
            "accion": "web_search",
            "query": "resultado partido Chile ayer",
            "respuesta": ""
        }
    },
    # ─── CALCULAR ───
    {
        "input": "cuanto es 15 por 7",
        "output": {
            "razonamiento": "El usuario pide un calculo. Puedo usar la calculadora.",
            "accion": "calcular",
            "expresion": "15*7",
            "respuesta": ""
        }
    },
    # ─── BUSCAR EN MEMORIA ───
    {
        "input": "que sabe sobre fotosintesis",
        "output": {
            "razonamiento": "Pregunta sobre un tema que podria estar en mi memoria semantica.",
            "accion": "buscar_memoria",
            "query": "fotosintesis",
            "respuesta": ""
        }
    },
    # ─── HORA ACTUAL ───
    {
        "input": "que hora es",
        "output": {
            "razonamiento": "El usuario pregunta la hora actual.",
            "accion": "hora_actual",
            "respuesta": ""
        }
    },
    # ─── RENOMBRAR PDFS ───
    {
        "input": "renombra los PDFs de la carpeta C:/facturas",
        "output": {
            "razonamiento": "El usuario quiere renombrar facturas PDF. Debo usar la herramienta pdf_rename.",
            "accion": "pdf_rename",
            "path": "C:/facturas",
            "dry_run": True,
            "respuesta": ""
        }
    },
    # ─── NO SABE (honesto) ───
    {
        "input": "cual es la capital de mongolia",
        "output": {
            "razonamiento": "No estoy seguro de la capital de Mongolia. Podria buscar en web o ser honesto.",
            "accion": "responder",
            "respuesta": "No tengo esa informacion. Puedes decirme y lo recordare."
        }
    },
]


def build_tools_prompt() -> str:
    """Construye el prompt completo: herramientas + ejemplos + instrucciones.
    
    Returns:
        String con el bloque completo para inyectar en el prompt del SLM.
    """
    lines = []
    lines.append(TOOLS_DESCRIPTION)
    lines.append("")
    lines.append("INSTRUCCIONES:")
    lines.append("1. Si te preguntan algo que NO sabes → usa web_search")
    lines.append("2. Si te piden un calculo → usa calcular")
    lines.append("3. Si te preguntan de un tema que estudiamos → usa buscar_memoria")
    lines.append("4. Si te preguntan la hora → usa hora_actual")
    lines.append("5. Si te piden renombrar facturas PDF → usa pdf_rename")
    lines.append("6. Si sabes la respuesta → usa accion: responder")
    lines.append("")
    lines.append("RESPONDE SIEMPRE EN ESTE FORMATO JSON:")
    lines.append('{"razonamiento": "...", "accion": "responder|web_search|calcular|buscar_memoria|hora_actual|pdf_rename", "respuesta": "...", "query": "...", "path": "..."}')
    lines.append("")
    lines.append("=== EJEMPLOS ===")
    
    for ex in FEW_SHOT_EXAMPLES:
        out = ex["output"]
        lines.append(f"Pregunta: {ex['input']}")
        # Formatear como JSON en una linea para ahorrar tokens
        extra = ""
        if "query" in out and out["query"]:
            extra += f', "query": "{out["query"]}"'
        if "expresion" in out and out["expresion"]:
            extra += f', "expresion": "{out["expresion"]}"'
        if "path" in out and out["path"]:
            extra += f', "path": "{out["path"]}"'
        if "dry_run" in out:
            extra += f', "dry_run": {str(out["dry_run"]).lower()}'
        r = out.get("respuesta", "")
        lines.append(f'JSON: {{"razonamiento": "{out["razonamiento"]}", "accion": "{out["accion"]}", "respuesta": "{r}"{extra}}}')
        lines.append("")
    
    lines.append("=== FIN EJEMPLOS ===")
    lines.append("")
    lines.append("AHORA RESPONDE LA SIGUIENTE PREGUNTA EN JSON:")
    return "\n".join(lines)


def build_few_shot_prompt() -> str:
    """Compatibilidad con codigo anterior. Solo los ejemplos."""
    lines = ["=== EJEMPLOS ==="]
    for ex in FEW_SHOT_EXAMPLES:
        out = ex["output"]
        lines.append(f"Pregunta: {ex['input']}")
        extra = ""
        if "query" in out and out["query"]:
            extra += f', "query": "{out["query"]}"'
        if "expresion" in out and out["expresion"]:
            extra += f', "expresion": "{out["expresion"]}"'
        if "path" in out and out["path"]:
            extra += f', "path": "{out["path"]}"'
        if "dry_run" in out:
            extra += f', "dry_run": {str(out["dry_run"]).lower()}'
        r = out.get("respuesta", "")
        lines.append(f'JSON: {{"razonamiento": "{out["razonamiento"]}", "accion": "{out["accion"]}", "respuesta": "{r}"{extra}}}')
        lines.append("")
    lines.append("=== FIN EJEMPLOS ===")
    return "\n".join(lines)
