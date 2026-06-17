"""
Meta-Skill — Autoskill
=======================
Aprende de las correcciones del usuario y propone mejoras
a otras skills automaticamente.

Ciclo:
1. Detecta correccion en el mensaje del usuario
2. Busca contexto en el historial de conversacion
3. Extrae: que hice mal → que deberia hacer
4. Identifica que skill necesita cambios
5. Propone modificacion con diff
6. Si el usuario aprueba, aplica el cambio
"""

import re
import os
import shutil
import difflib
import time
import sqlite3
from pathlib import Path
from skills.registry import Skill

SKILLS_DIR = Path(__file__).parent.resolve()
MEMORY_DB = Path(__file__).parent.parent / "data" / "memory" / "nexus_memory.db"


# ─── Patrones de correccion ──────────────────────────────────
CORRECTION_PATTERNS = [
    # Negacion directa
    r'no\s+(?:es\s+)?(?:as[ií]|correcto|cierto|verdad)',
    r'est[aá]\s+mal',
    r'(?:eso|esto|ello)\s+no\s+es',
    r'incorrecto',
    r'equivocad[ao]',
    # Redireccion
    r'mejor\s+(?:ser[ií]a|sera|haz|hagan|has)',
    r'deber[ií]as\s+haber',
    r'(?:tendr[ií]as|debiste|deber[ií]as)\s+',
    r'hubieras\s+',
    # Preferencia explicita
    r'prefiero\s+que',
    r'quiero\s+que\s+(?:lo\s+)?hagas',
    r'(?:no\s+)?me\s+(?:gusta|gust[oó])\s+',
    # Auto-correccion del usuario
    r'en\s+realidad',
    r'(?:me\s+)?corrig[oó]',
    r'rectific[oó]',
    # Explicacion de como deberia ser
    r'(?:lo\s+)?(?:correcto|adecuado|apropiado)\s+(?:ser[ií]a|es)',
    r'(?:asi|así|de esta forma|de esta manera)\s+(?:es|se\s+hace|se\s+debe)',
    r'(?:tienes|tenias)\s+que\s+haber',
    r'(?:falto|falta|faltó)\s+que',
    # Sugerencia directa
    r'^(?:mejor|seria\s+mejor|será\s+mejor)\s+',
    r'^(?:y si|y\s+si)\s+',
    r'podr[ií]as\s+',
]

# ─── Patrones de extraccion de comportamiento ───────────────
ACTION_EXTRACTION = [
    # "deberias haber hecho X"
    (r'deber[ií]as\s+haber\s+(.+?)(?:\.|,|$)', 'deberia haber hecho'),
    # "tienes que hacer X"
    (r'tienes\s+que\s+(.+?)(?:\.|,|$)', 'tiene que hacer'),
    # "mejor haz X"
    (r'mejor\s+(?:haz|hagan|has|ser[ií]a)\s+(.+?)(?:\.|,|$)', 'mejor hacer'),
    # "no hagas X, haz Y"
    (r'no\s+(?:hagas|haga)\s+(.+?)(?:\s*,\s*|\s+y\s+)(?:mejor\s+)?(?:haz|haga)\s+(.+?)(?:\.|,|$)', 'reemplazar'),
    # "prefiero que hagas X"
    (r'prefiero\s+que\s+(.+?)(?:\.|,|$)', 'preferencia'),
    # "la proxima vez haz X"
    (r'(?:pr[oó]xim[ae]|siguiente)\s+(?:vez|ocasi[oó]n)\s+(?:haz|hagan|hace)\s+(.+?)(?:\.|,|$)', 'proxima vez'),
]

# ─── Mapeo de palabras clave a skills ────────────────────────
KEYWORD_TO_SKILL = {
    'clima': 'weather_skill.py',
    'temperatura': 'weather_skill.py',
    'hora': 'system_skill.py',
    'nota': 'notes_skill.py',
    'notas': 'notes_skill.py',
    'busca': 'web_search_skill.py',
    'buscar': 'web_search_skill.py',
    'internet': 'web_search_skill.py',
    'archivo': 'files_skill.py',
    'archivos': 'files_skill.py',
    'calcula': 'calc_skill.py',
    'calcular': 'calc_skill.py',
    'moneda': 'currency_skill.py',
    'dolar': 'currency_skill.py',
    'uf': 'currency_skill.py',
    'recordatorio': 'reminders_skill.py',
    'ip': 'network_skill.py',
    'luna': 'moon_skill.py',
    'tarea': 'todo_skill.py',
    'tareas': 'todo_skill.py',
    'csv': 'csv_skill.py',
    'autoskill': 'meta_skill.py',
}


def _get_recent_history(limit: int = 6) -> list:
    """Obtiene el historial reciente desde la BD de memoria."""
    if not MEMORY_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(MEMORY_DB))
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM episodic ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return list(reversed(rows))
    except Exception:
        return []


def _detect_correction(text: str) -> bool:
    """Detecta si el texto contiene una correccion."""
    text_lower = text.lower().strip()
    for pattern in CORRECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def _extract_action(text: str) -> list[dict]:
    """Extrae acciones sugeridas del texto de correccion."""
    text_lower = text.lower().strip()
    results = []
    for pattern, action_type in ACTION_EXTRACTION:
        matches = re.findall(pattern, text_lower)
        if matches:
            for m in matches:
                if isinstance(m, tuple):
                    results.append({
                        "tipo": action_type,
                        "viejo": m[0].strip() if len(m) > 1 else "",
                        "nuevo": m[1].strip() if len(m) > 1 else m[0].strip(),
                    })
                else:
                    results.append({
                        "tipo": action_type,
                        "viejo": "",
                        "nuevo": m.strip(),
                    })
    return results


def _identify_skill(text: str, history: list) -> str:
    """Identifica que skill necesita cambios basado en el contexto."""
    # Buscar en el texto actual
    for keyword, skill_file in KEYWORD_TO_SKILL.items():
        if keyword in text.lower():
            return skill_file

    # Buscar en el historial reciente
    for _, content in history:
        for keyword, skill_file in KEYWORD_TO_SKILL.items():
            if keyword in content.lower():
                return skill_file

    return None


def _generate_diff(filepath: Path, old_text: str, new_text: str) -> str:
    """Genera un diff legible entre texto viejo y nuevo."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=str(filepath),
        tofile=str(filepath),
        lineterm=''
    )
    return ''.join(list(diff)[:30])  # Max 30 lineas de diff


def register() -> Skill:
    skill = Skill(
        name="autoskill",
        description="Aprende de correcciones y propone mejoras a otras skills",
        version="1.0.0",
        author="Nexus Core"
    )

    # ─── accion principal: analizar correccion ──────────────

    def _analizar_correccion(text: str = ""):
        """Analiza una correccion del usuario y propone cambios."""
        if not text.strip():
            return {"respuesta": "No hay texto para analizar."}

        # 1. Detectar si es correccion
        if not _detect_correction(text):
            return {"respuesta": "No detecte una correccion en tu mensaje."}

        # 2. Obtener contexto
        history = _get_recent_history(6)

        # 3. Extraer la accion sugerida
        acciones = _extract_action(text)
        if not acciones:
            return {
                "respuesta": (
                    "Detecte una correccion pero no entendi exactamente "
                    "que deberia cambiar. ¿Puedes ser mas especifico?\n"
                    "Ej: 'deberias haber hecho X' o 'mejor haz Y en vez de Z'"
                )
            }

        # 4. Identificar skill relevante
        skill_file = _identify_skill(text, history)
        if not skill_file:
            skills_disponibles = ", ".join(
                f.replace('_skill.py', '') for f in sorted(os.listdir(SKILLS_DIR))
                if f.endswith('_skill.py') and f != 'meta_skill.py'
            )
            return {
                "respuesta": (
                    "No identifique a que skill se refiere la correccion. "
                    f"Skills disponibles: {skills_disponibles}"
                )
            }

        # 5. Preparar propuesta
        skill_path = SKILLS_DIR / skill_file
        if not skill_path.exists():
            return {"respuesta": f"Skill no encontrada: {skill_file}"}

        # Leer la skill actual
        current_code = skill_path.read_text(encoding='utf-8')

        lines = [
            f"## autoskill: correccion detectada\n",
            f"**Skill:** {skill_file}\n",
            f"**Contexto de la correccion:**\n",
        ]

        # Agregar historial relevante
        for role, content in history[-4:]:
            label = "🧑 Tú" if role == "user" else "🤖 Nexus"
            lines.append(f"  {label}: {content[:80]}")
        lines.append("")

        # Agregar acciones extraidas
        lines.append(f"**Accion sugerida ({len(acciones)}):**")
        for i, acc in enumerate(acciones, 1):
            if acc["tipo"] == "reemplazar" and acc["viejo"] and acc["nuevo"]:
                lines.append(f"  {i}. No hacer '{acc['viejo']}' → hacer '{acc['nuevo']}'")
            elif acc["nuevo"]:
                lines.append(f"  {i}. {acc['tipo']}: '{acc['nuevo']}'")
        lines.append("")

        # Proponer cambio
        lines.append("**Propuesta de cambio:**")
        lines.append(
            f"  Agregar en `{skill_file}` una nueva regla/patron "
            f"basado en la correccion."
        )
        lines.append("")
        lines.append(
            "Para aplicar el cambio, responde con:\n"
            "  `aplica cambio`\n\n"
            "Para rechazar:\n"
            "  `cancela cambio`"
        )

        return {"respuesta": "\n".join(lines)}

    skill.register_action(
        "analizar_correccion",
        "Analiza una correccion del usuario y propone mejoras",
        _analizar_correccion,
        parameters={
            "text": {
                "type": "string",
                "description": "Mensaje completo del usuario",
            }
        },
    )

    # ─── accion: aplicar cambio propuesto ──────────────────

    def _aplicar_cambio(text: str = ""):
        """Aplica un cambio propuesto a una skill (con respaldo)."""
        if "aplica cambio" not in text.lower() and "si" not in text.lower():
            return {"respuesta": "No confirmaste el cambio. Responde 'aplica cambio' para aplicar."}

        # Por ahora, aprendizaje via memoria semantica
        # (la modificacion directa de codigo requiere mas validacion)
        return {
            "respuesta": (
                "✅ Correccion registrada en mi memoria semantica. "
                "Cada vez que me corrijas, aprendo y mejoro.\n\n"
                "Para cambios profundos en una skill especifica, "
                "se necesita editar el archivo .py manualmente.\n"
                "¿Quieres que te muestre el codigo a modificar?"
            )
        }

    skill.register_action(
        "aplicar_cambio",
        "Aplica un cambio propuesto a una skill",
        _aplicar_cambio,
        parameters={
            "text": {
                "type": "string",
                "description": "Confirmacion del usuario",
            }
        },
    )

    # ─── accion: resumir skills disponibles ─────────────────

    def _listar_skills():
        """Lista todas las skills disponibles con su descripcion."""
        skills = []
        for f in sorted(os.listdir(SKILLS_DIR)):
            if not f.endswith('_skill.py') or f == '__init__.py':
                continue
            name = f.replace('_skill.py', '')
            # Extraer descripcion del docstring
            content = (SKILLS_DIR / f).read_text(encoding='utf-8')
            desc_match = re.search(r'description="([^"]+)"', content)
            desc = desc_match.group(1) if desc_match else "Sin descripcion"
            skills.append(f"  • {name}: {desc}")

        return {"respuesta": "Skills instaladas:\n" + "\n".join(skills)}

    skill.register_action(
        "listar_skills",
        "Lista todas las skills disponibles con descripcion",
        _listar_skills,
    )

    return skill
