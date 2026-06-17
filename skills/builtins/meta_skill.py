"""
Meta-Skill — Autoskill
=======================
Sistema de auto-mejora: detecta correcciones, extrae patrones,
edita codigo de otras skills con respaldo y diff.

Ciclo completo:
1. Detecta correccion en la conversacion
2. Extrae: que patron cambiar → por que reemplazarlo
3. Identifica la skill y el punto exacto de edicion
4. Genera el nuevo codigo con un template
5. Muestra diff antes de aplicar
6. Crea backup + aplica cambio
7. Verifica sintaxis post-cambio
"""

import re
import os
import shutil
import difflib
import time
import sqlite3
import ast
import tempfile
from pathlib import Path
from skills.registry import Skill

SKILLS_DIR = Path(__file__).parent.resolve()
BACKUP_DIR = SKILLS_DIR / ".backups"
MEMORY_DB = Path(__file__).parent.parent / "data" / "memory" / "nexus_memory.db"

# Crear directorio de backups
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ─── Templates de codigo para auto-mejora ────────────────────
CODE_TEMPLATES = {
    "nuevo_patron": """
    # [autoskill] {nombre}
    # Aprendido: {fecha}
    # Contexto: {contexto}
    r'{patron}': {handler},
""",
    "nueva_funcion": """
    def _{nombre}(self, text: str, memories: list, facts: list) -> str:
        \"\"\"{descripcion}\"\"\"
        {cuerpo}
        return "{respuesta}"
""",
    "nueva_regla_procedural": (
        "# Regla aprendida por autoskill\n"
        "# Cuando el usuario dice '{disparador}', "
        "Nexus debe responder: '{respuesta}'\n"
    ),
}


# ─── Deteccion de correcciones ───────────────────────────────
CORRECTION_PATTERNS = [
    r'no\s+(?:es\s+)?(?:as[ií]|correcto|cierto|verdad)',
    r'est[aá]\s+mal',
    r'(?:eso|esto|ello)\s+no\s+es',
    r'incorrecto',
    r'equivocad[ao]',
    r'mejor\s+(?:ser[ií]a|sera|haz|hagan|has)',
    r'deber[ií]as\s+haber',
    r'(?:tendr[ií]as|debiste|deber[ií]as)\s+',
    r'hubieras\s+',
    r'prefiero\s+que',
    r'quiero\s+que\s+(?:lo\s+)?hagas',
    r'(?:no\s+)?me\s+(?:gusta|gust[oó])\s+',
    r'en\s+realidad',
    r'(?:me\s+)?corrig[oó]',
    r'rectific[oó]',
    r'(?:lo\s+)?(?:correcto|adecuado|apropiado)\s+(?:ser[ií]a|es)',
    r'(?:asi|así|de esta forma|de esta manera)\s+(?:es|se\s+hace|se\s+debe)',
    r'(?:tienes|tenias)\s+que\s+haber',
    r'(?:falto|falta|falt[oó])\s+que',
    r'^(?:mejor|seria\s+mejor|ser[aá]\s+mejor)\s+',
    r'^(?:y si|y\s+si)\s+',
    r'podr[ií]as\s+',
]

ACTION_EXTRACTION = [
    (r'de[vb]er[ií]as?\s+haber\s+(.+?)(?:\.|,|$)', 'deberia haber hecho'),
    (r'(?:de[vb]er[ií]as?|tendr[ií]as?)\s+(?:haber\s+)?(.+?)(?:\.|,|$)', 'deberia hacer'),
    (r'tienes\s+que\s+(.+?)(?:\.|,|$)', 'tiene que hacer'),
    (r'mejor\s+(?:haz|hagan|has|ser[ií]a|ser[aá])\s+(.+?)(?:\.|,|$)', 'mejor hacer'),
    (r'no\s+(?:hagas|haga|de[vb]er[ií]as?)\s+(.+?)(?:\s*,\s*|\s+y\s+)(?:mejor\s+)?(?:haz|haga|hacer)\s+(.+?)(?:\.|,|$)', 'reemplazar'),
    (r'prefiero\s+que\s+(.+?)(?:\.|,|$)', 'preferencia'),
    (r'(?:pr[oó]xim[ae]|siguiente)\s+(?:vez|ocasi[oó]n)\s+(?:haz|hagan|hace|pregunta|consulta|busca|dime|di|muestra|ens[eé]ñame|avisa|dame)\s+(.+?)(?:\.|,|$)', 'proxima vez'),
    # Fallback: capturar cualquier frase despues de "que" en correcciones
    (r'(?:que\s+)?(?:de[vb]er[ií]as?|tendr[ií]as?)\s+(.+?)(?:\.|,|$)', 'accion correctiva'),
]

KEYWORD_TO_SKILL = {
    'clima': 'weather_skill.py', 'temperatura': 'weather_skill.py',
    'hora': 'system_skill.py',
    'nota': 'notes_skill.py', 'notas': 'notes_skill.py',
    'busca': 'web_search_skill.py', 'buscar': 'web_search_skill.py', 'internet': 'web_search_skill.py',
    'archivo': 'files_skill.py', 'archivos': 'files_skill.py',
    'calcula': 'calc_skill.py', 'calcular': 'calc_skill.py',
    'moneda': 'currency_skill.py', 'dolar': 'currency_skill.py', 'uf': 'currency_skill.py',
    'recordatorio': 'reminders_skill.py',
    'ip': 'network_skill.py',
    'luna': 'moon_skill.py',
    'tarea': 'todo_skill.py', 'tareas': 'todo_skill.py',
    'csv': 'csv_skill.py',
    'autoskill': 'meta_skill.py',
}


# ─── Funciones auxiliares ────────────────────────────────────

def _get_recent_history(limit: int = 6) -> list:
    if not MEMORY_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(MEMORY_DB))
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM episodic ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return list(reversed(rows))
    except Exception:
        return []


def _detect_correction(text: str) -> bool:
    text_lower = text.lower().strip()
    for pattern in CORRECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def _extract_action(text: str) -> list[dict]:
    text_lower = text.lower().strip()
    results = []
    for pattern, action_type in ACTION_EXTRACTION:
        matches = re.findall(pattern, text_lower)
        if matches:
            for m in matches:
                if isinstance(m, tuple):
                    results.append({"tipo": action_type, "viejo": m[0].strip() if len(m) > 1 else "", "nuevo": m[1].strip() if len(m) > 1 else m[0].strip()})
                else:
                    results.append({"tipo": action_type, "viejo": "", "nuevo": m.strip()})
    # Si no se extrajo nada con los patrones finos, extraer keywords
    if not results:
        words = re.findall(r'\b([a-záéíóúñ]{4,})\b', text_lower)
        # Buscar patron "X en vez de Y" o "X no Y"
        en_vez = re.search(r'(.+?)\s+(?:en vez de|en lugar de|y no)\s+(.+)', text_lower)
        if en_vez:
            results.append({"tipo": "reemplazar", "viejo": en_vez.group(2).strip(), "nuevo": en_vez.group(1).strip()})
    return results


def _identify_skill(text: str, history: list) -> tuple[str, str]:
    """Retorna (skill_file, keyword_encontrada)."""
    for keyword, skill_file in KEYWORD_TO_SKILL.items():
        if keyword in text.lower():
            return skill_file, keyword
    for _, content in history:
        for keyword, skill_file in KEYWORD_TO_SKILL.items():
            if keyword in content.lower():
                return skill_file, keyword
    return None, None


def _generar_diff(filepath: Path, old_text: str, new_text: str) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=str(filepath), tofile=str(filepath), lineterm='')
    return ''.join(list(diff)[:40])


def _verificar_sintaxis(code: str) -> tuple[bool, str]:
    """Verifica que el codigo Python sea sintacticamente valido."""
    try:
        ast.parse(code)
        return True, "Sintaxis OK"
    except SyntaxError as e:
        return False, f"Error de sintaxis: {e}"


def _crear_backup(filepath: Path) -> Path:
    """Crea un backup del archivo antes de modificarlo."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filepath.stem}_{timestamp}{filepath.suffix}"
    backup_path = BACKUP_DIR / backup_name
    shutil.copy2(str(filepath), str(backup_path))
    return backup_path


def _aplicar_edicion(filepath: Path, old: str, new: str) -> dict:
    """Aplica una edicion a un archivo con respaldo y verificacion."""
    # 1. Backup
    backup = _crear_backup(filepath)

    # 2. Verificar sintaxis del nuevo codigo
    valido, msg = _verificar_sintaxis(new)
    if not valido:
        return {"success": False, "error": msg}

    # 3. Generar diff
    diff = _generar_diff(filepath, old, new)

    # 4. Aplicar
    filepath.write_text(new, encoding='utf-8')

    return {
        "success": True,
        "backup": str(backup),
        "diff": diff,
        "bytes_escritos": len(new),
    }


def _generar_codigo_correccion(skill_file: str, acciones: list[dict], history: list) -> tuple[str, str]:
    """Genera codigo correctivo para insertar en la skill.
    Retorna: (old_string, new_string) para hacer un patch en el archivo.
    """
    skill_path = SKILLS_DIR / skill_file
    if not skill_path.exists():
        return None, None

    current = skill_path.read_text(encoding='utf-8')

    # Buscar el docstring de la skill para insertar nuevas reglas ahi
    # o buscar el final del archivo para agregar comentarios
    changes = []
    fecha = time.strftime("%Y-%m-%d %H:%M")

    for acc in acciones:
        if acc["tipo"] == "reemplazar" and acc["viejo"] and acc["nuevo"]:
            # Generar regla: no hacer X, hacer Y
            regla = (
                f"\n# [autoskill {fecha}] Correccion: "
                f"'{acc['viejo']}' -> '{acc['nuevo']}'"
            )
            changes.append(regla)
        elif acc["nuevo"]:
            regla = (
                f"\n# [autoskill {fecha}] Aprendido: "
                f"{acc['tipo']}: '{acc['nuevo']}'"
            )
            changes.append(regla)

    if not changes:
        return None, None

    # Agregar las reglas al final del archivo (antes del __main__ si existe)
    # Buscar un punto seguro para insertar
    insert_points = [
        r'\nif\s+__name__\s*==\s*["\']__main__["\']',
        r'\n# ───',
        r'\nregister\(\)',
    ]

    new_content = current
    inserted = False

    for point in insert_points:
        match = re.search(point, new_content)
        if match:
            pos = match.start()
            new_content = new_content[:pos] + "\n".join(changes) + "\n" + new_content[pos:]
            inserted = True
            break

    if not inserted:
        # Insertar al final
        new_content = current.rstrip() + "\n" + "\n".join(changes) + "\n"

    return current, new_content


# ─── Registro de la skill ────────────────────────────────────

def register() -> Skill:
    skill = Skill(name="autoskill", description="Auto-mejora: aprende de correcciones y edita codigo de otras skills", version="2.0.0", author="Nexus Core")

    # ═══════════════════════════════════════════════
    # 1. ANALIZAR CORRECCION
    # ═══════════════════════════════════════════════

    def _analizar_correccion(text: str = ""):
        if not text.strip():
            return {"respuesta": "No hay texto para analizar."}
        if not _detect_correction(text):
            return {"respuesta": "No detecte una correccion en tu mensaje."}

        history = _get_recent_history(6)
        acciones = _extract_action(text)

        if not acciones:
            return {"respuesta": "Detecte una correccion pero no entendi exactamente que cambiar. ¿Puedes ser mas especifico?"}

        skill_file, keyword = _identify_skill(text, history)
        if not skill_file:
            disponibles = ", ".join(f.replace('_skill.py', '') for f in sorted(os.listdir(SKILLS_DIR)) if f.endswith('_skill.py'))
            return {"respuesta": f"No identifique a que skill pertenece. Skills: {disponibles}"}

        skill_path = SKILLS_DIR / skill_file
        if not skill_path.exists():
            return {"respuesta": f"Skill no encontrada: {skill_file}"}

        # Generar codigo propuesto
        old_code, new_code = _generar_codigo_correccion(skill_file, acciones, history)
        diff_text = ""
        if old_code and new_code:
            diff_text = _generar_diff(skill_path, old_code, new_code)

        lines = [
            "## autoskill: correccion detectada",
            f"**Skill:** {skill_file}",
            f"**Palabra clave:** {keyword or '?'}",
            "",
            "**Contexto:**",
        ]
        for role, content in history[-4:]:
            label = "🧑 Tu" if role == "user" else "🤖 Nexus"
            lines.append(f"  {label}: {content[:80]}")
        lines.append("")
        lines.append(f"**Accion sugerida ({len(acciones)}):**")
        for i, acc in enumerate(acciones, 1):
            if acc["tipo"] == "reemplazar" and acc["viejo"] and acc["nuevo"]:
                lines.append(f"  {i}. No hacer '{acc['viejo']}' → hacer '{acc['nuevo']}'")
            elif acc["nuevo"]:
                lines.append(f"  {i}. {acc['tipo']}: '{acc['nuevo']}'")
        lines.append("")

        if diff_text:
            lines.append("**Diff propuesto:**")
            lines.append(f"```diff\n{diff_text}\n```")
        lines.append("")
        lines.append(
            "**Opciones:**\n"
            "  • `aplica cambio` — aplicar la edicion con backup\n"
            "  • `guarda patron` — solo guardar en memoria procedural\n"
            "  • `cancela` — descartar"
        )

        return {"respuesta": "\n".join(lines)}

    skill.register_action("analizar_correccion", "Analiza una correccion y propone cambios de codigo", _analizar_correccion,
        parameters={"text": {"type": "string", "description": "Mensaje completo del usuario"}})

    # ═══════════════════════════════════════════════
    # 2. APLICAR CAMBIO (edita el archivo .py real)
    # ═══════════════════════════════════════════════

    def _aplicar_cambio(text: str = ""):
        """Aplica el cambio editando realmente el archivo .py."""
        if "aplica cambio" not in text.lower() and "si aplica" not in text.lower():
            return {"respuesta": "No confirmaste. Responde 'aplica cambio' para editar el codigo."}

        # Re-analizar la ultima correccion del historial
        history = _get_recent_history(8)
        user_msgs = [c for r, c in history if r == 'user']
        if not user_msgs:
            return {"respuesta": "No hay correcciones recientes en el historial."}

        # Buscar el ultimo mensaje que contenga una correccion
        last_correction = None
        for msg in reversed(user_msgs):
            if _detect_correction(msg):
                last_correction = msg
                break

        if not last_correction:
            return {"respuesta": "No encontre una correccion reciente para aplicar."}

        acciones = _extract_action(last_correction)
        if not acciones:
            return {"respuesta": "No pude extraer acciones de la ultima correccion."}

        skill_file, _ = _identify_skill(last_correction, history)
        if not skill_file:
            return {"respuesta": "No identifique que skill editar."}

        skill_path = SKILLS_DIR / skill_file

        # Generar y aplicar cambio
        old_code, new_code = _generar_codigo_correccion(skill_file, acciones, history)
        if not old_code or not new_code:
            return {"respuesta": "No se pudo generar codigo de correccion."}

        # Guardar en memoria procedural tambien (aprendizaje inmediato)
        for acc in acciones:
            nombre = f"autoskill_{acc['tipo']}_{int(time.time())}"
            response_text = acc.get("nuevo", "procesado segun correccion")
            # No podemos acceder a self.memory desde aqui, pero podemos
            # registrar en un archivo de log de lecciones aprendidas
            lecciones_path = SKILLS_DIR.parent / "data" / "lessons_learned.txt"
            lecciones_path.parent.mkdir(parents=True, exist_ok=True)
            with open(lecciones_path, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M')} | {skill_file} | {acc['tipo']}: '{acc.get('nuevo', '')}'\n")

        # Aplicar edicion
        resultado = _aplicar_edicion(skill_path, old_code, new_code)
        if not resultado.get("success"):
            return {"respuesta": f"Error al aplicar cambio: {resultado.get('error')}"}

        return {
            "respuesta": (
                f"✅ Cambio aplicado a `{skill_file}`\n\n"
                f"**Backup:** `{resultado['backup']}`\n"
                f"**Diff:**\n```diff\n{resultado['diff'][:500]}\n```\n\n"
                f"Leccion guardada en memoria procedural. "
                f"Puedes revertir con: restaura backup {resultado['backup']}"
            )
        }

    skill.register_action("aplicar_cambio", "Aplica la edicion de codigo propuesta a la skill", _aplicar_cambio,
        parameters={"text": {"type": "string", "description": "Confirmacion del usuario"}})

    # ═══════════════════════════════════════════════
    # 3. GUARDAR PATRON (solo en memoria procedural)
    # ═══════════════════════════════════════════════

    def _guardar_patron(text: str = ""):
        """Guarda la correccion como patron procedural sin editar codigo."""
        if "guarda patron" not in text.lower() and "guarda" not in text.lower():
            return {"respuesta": "Para guardar el patron, responde 'guarda patron'."}

        history = _get_recent_history(8)
        user_msgs = [c for r, c in history if r == 'user']
        last_correction = None
        for msg in reversed(user_msgs):
            if _detect_correction(msg):
                last_correction = msg
                break

        if not last_correction:
            return {"respuesta": "No encontre una correccion para guardar."}

        acciones = _extract_action(last_correction)
        lecciones_path = SKILLS_DIR.parent / "data" / "lessons_learned.txt"
        lecciones_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(lecciones_path, "a", encoding="utf-8") as f:
            for acc in acciones:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M')} | procedural | {acc['tipo']}: '{acc.get('nuevo', '')}'\n")
                count += 1

        return {"respuesta": f"✅ {count} patron(es) guardados en memoria procedural. Se usaran en futuras interacciones."}

    skill.register_action("guardar_patron", "Guarda la correccion como patron procedural", _guardar_patron,
        parameters={"text": {"type": "string"}})

    # ═══════════════════════════════════════════════
    # 4. LISTAR LECCIONES APRENDIDAS
    # ═══════════════════════════════════════════════

    def _lecciones():
        """Muestra las lecciones aprendidas por autoskill."""
        lecciones_path = SKILLS_DIR.parent / "data" / "lessons_learned.txt"
        if not lecciones_path.exists():
            return {"respuesta": "Aun no hay lecciones aprendidas. Cuando me corrijas, las registro aqui."}
        lines = lecciones_path.read_text(encoding="utf-8").strip().split("\n")
        if not lines:
            return {"respuesta": "Archivo de lecciones vacio."}
        # Mostrar las ultimas 15
        recent = lines[-15:]
        return {"respuesta": "Lecciones aprendidas:\n" + "\n".join(recent)}

    skill.register_action("lecciones", "Muestra las lecciones aprendidas por autoskill", _lecciones)

    # ═══════════════════════════════════════════════
    # 5. LISTAR SKILLS
    # ═══════════════════════════════════════════════

    def _listar_skills():
        skills = []
        for f in sorted(os.listdir(SKILLS_DIR)):
            if not f.endswith('_skill.py') or f == '__init__.py':
                continue
            name = f.replace('_skill.py', '')
            content = (SKILLS_DIR / f).read_text(encoding='utf-8')
            desc_match = re.search(r'description="([^"]+)"', content)
            desc = desc_match.group(1) if desc_match else "Sin descripcion"
            skills.append(f"  * {name}: {desc}")
        return {"respuesta": "Skills instaladas:\n" + "\n".join(skills)}

    skill.register_action("listar_skills", "Lista todas las skills disponibles", _listar_skills)

    return skill
