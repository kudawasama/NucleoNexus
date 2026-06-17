"""
Núcleo Nexus — Extractor Automático de Conocimiento
====================================================
Extrae hechos aprendibles de las conversaciones y los almacena
en la memoria semántica para uso futuro.
"""
import re
import logging

logger = logging.getLogger("nexus.learning.extractor")

# Patrones de hechos declarativos en español
# Vision #4: el sistema aprende de cada interacción.
# Doc 05-APRENDIZAJE lista los patrones gramaticales soportados.
# Cada patron tiene el grupo (X, Y, ...) - la primera captura es el sujeto.
FACT_PATTERNS = [
    # "X es/son Y" - declaracion simple
    r'\b([a-záéíóúñü]{2,}(?:\s+[a-záéíóúñü]{2,}){0,4})\s+(?:es|son|son:)\s+([^.;]{3,150})',
    # "X son/son: A, B, C" - LISTA de cosas
    r'((?:los|las|los\s+\w+|\w+s)\s+son:?)\s+([^.;]+\.)',
    # "X significa Y"
    r'\b([a-záéíóúñü]{2,30})\s+(?:significa|quiere decir)\s+([^.;]{3,80})',
    # "X se usa para Y"
    r'\b([a-záéíóúñü]{2,30})\s+se\s+(?:usa|utiliza)\s+(?:para|en)\s+([^.;]{3,80})',
    # "X tiene/contiene Y"
    r'\b(?:(?:el|la|los|las)\s+)?([a-záéíóúñü]{2,30}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:tiene|contiene|incluye)\s+([^.;]{3,80})',
    # "X está compuesto por Y"
    r'\b([a-záéíóúñü]{2,30}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:está|esta)\s+(?:compuesto|formado|hecho)\s+(?:por|de)\s+([^.;]{3,80})',
    # "X descubrió/inventó Y"
    r'\b([a-záéíóúñü]{2,30})\s+(?:descubrió|inventó|creó|escribió)\s+([^.;]{3,80})',
    # "X hace/realiza Y"
    r'\b(?:(?:el|la|los|las|un|una)\s+)?([a-záéíóúñü]{2,20}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:hace|realiza|ejecuta)\s+((?:\w+\s+){1,4}\w+)',
    # "X produce/genera Y"
    r'\b(?:(?:el|la|los|las|un|una)\s+)?([a-záéíóúñü]{2,20}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:produce|genera|crea|convierte|transforma)\s+((?:\w+\s+){1,4}\w+)',

    r'\b(?:(?:el|la|los|las|un|una)\s+)?([a-záéíóúñü]{2,20}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:filtra|filtran|absorbe|absorben|transporta|transportan|elimina|eliminan|expulsa|expulsan|bombea|bombean|limpia|limpian)\s+((?:[a-záéíóúñü]{2,}\s+){1,4}[a-záéíóñü]{2,})',
    # "X necesita/requiere Y para Z"
    r'\b(?:(?:el|la|los|las|un|una)\s+)?([a-záéíóúñü]{2,30}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:necesita|necesitan|requiere|requieren|utiliza|utilizan|usa|usan|ocupa|ocupan)\s+([a-záéíóúñü].{3,50})\s+(?:para|en)\s+([a-záéíóúñü].{3,60})',
    # "X ayuda/permite/contribuye a Y"
    r'\b(?:(?:el|la|los|las|un|una)\s+)?([a-záéíóúñü]{2,30}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:ayuda|ayudan|permite|permiten|contribuye|contribuyen|sirve|sirven)\s+(?:a|para|en|al)?\s*([a-záéíóúñü].{3,80})',
    # "X funciona mediante/gracias a/con Y"
    r'\b(?:(?:el|la|los|las|un|una)\s+)?([a-záéíóúñü]{2,30}(?:\s+[a-záéíóúñü]{2,}){0,3})\s+(?:funciona|funcionan|opera|operan|trabaja|trabajan)\s+(?:mediante|gracias a|con|usando|utilizando)\s+(.+?)(?:\s+(?:para|en|de)\s+|\s*$)',
    # "X vive en Y" - ubicacion de personas
    r'\b([a-záéíóúñü]{2,30})\s+vive\s+en\s+([a-záéíóúñü].{3,80})',
    # "X es conocido por Y" / "X es famoso por Y"
    r'\b([a-záéíóúñü]{2,30})\s+(?:es conocido|es famosa|es famoso|se hizo famoso)\s+(?:por|como)\s+([a-záéíóúñü].{3,80})',
    # "X vive en Y" - ubicacion de personas (variante)
    r'\b([a-záéíóúñü]{2,30})\s+se\s+encuentra\s+en\s+([a-záéíóúñü].{3,80})',
]

# Palabras a ignorar al final de un hecho extraido (conectores, artículos sueltos)
FACT_SUFFIXES = {
    "y", "o", "e", "que", "porque", "ya que", "si", "aunque",
    "el", "la", "los", "las", "un", "una", "unos", "unas",
}

# Palabras de confirmación/reforzamiento
REINFORCE_WORDS = {"correcto", "exacto", "bien", "sí", "si", "cierto", "claro", 
                   "bueno", "vale", "de acuerdo", "ok", "okay", "perfecto"}

# Palabras de negación
NEGATE_WORDS = {"no", "incorrecto", "falso", "mal", "error", "mentira"}


def _clean_fact_groups(groups, original_text: str, pattern_idx: int = 0) -> str:
    """Limpia y une los grupos de un match de extractor.

    Para 2 grupos (X, Y): une como "X ... Y" (no pierde el verbo).
    Para 3 grupos (X, Y, Z): une como "X ... Y ... Z".
    """
    if not groups:
        return ""
    if isinstance(groups, str):
        return groups

    # Filtrar None y vacios
    parts = [g for g in groups if g]
    if not parts:
        return ""

    # Si hay 2 grupos, reconstruir contexto parcial del texto original
    # entre el primer grupo y el último grupo
    if len(parts) == 2:
        first, last = parts
        # Buscar la frase entre ellos en el texto
        try:
            first_end = original_text.find(first) + len(first)
            last_start = original_text.find(last, first_end)
            if last_start > first_end:
                middle = original_text[first_end:last_start].strip()
                # Eliminar espacios multiples
                middle = re.sub(r'\s+', ' ', middle)
                return f"{first} {middle} {last}".strip()
        except Exception:
            pass
        return f"{first} {last}"
    elif len(parts) == 3:
        # X verbo Y para Z -> unir manteniendo verbos clave
        return " ".join(parts)
    else:
        return " ".join(parts)


def extract_facts_from_text(text: str, min_words: int = 3) -> list[str]:
    """Extrae posibles hechos de un texto conversacional.

    Args:
        text: Texto del cual extraer hechos
        min_words: Mínimo de palabras para considerar un hecho

    Returns:
        Lista de hechos extraídos (limpios)
    """
    text_lower = text.lower().strip()
    facts = []

    for pattern in FACT_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            fact = _clean_fact_groups(match, text_lower)
            # Limpiar y validar
            fact = fact.strip().strip('.,;:!¿?¡')
            # Quitar palabras conectoras al final SOLO si son sueltas
            # (si la ultima palabra es 'e' precedida de 'y' → parte de una lista "X y E", no quitar)
            words = fact.split()
            while words and len(words) > 1 and words[-1].lower() in FACT_SUFFIXES:
                # No quitar "e" si la anterior es "y" (seria parte de "X y E")
                if words[-1].lower() == "e" and len(words) >= 2 and words[-2].lower() == "y":
                    break
                words.pop()
            fact = " ".join(words)
            fact_words = fact.split()
            if len(fact_words) >= min_words and len(fact) > 10:
                # Evitar duplicados obvios
                if not any(fact == existing[:len(fact)] for existing in facts):
                    facts.append(fact)

    # ─── Expansion: dividir listas en items individuales ───
    # "Los principios son: A, B, C" -> guardar A, B, C por separado
    # "Hay cinco fundamentos: A, B, C" -> tambien
    # "Incluyen A, B, C" -> tambien
    expanded = []
    for fact in facts:
        # Detectar patron "X son/son: A, B, C" o "X son A, B y C"
        list_match = re.match(
            r'^(.{5,80}?)\s+(?:son|es)\s*:?\s+(.+)$',
            fact
        )
        # Tambien: "Hay N X: A, B, C" o "Incluyen A, B, C"
        list_match2 = re.match(
            r'^(?:hay|incluye|incluyen|tienen|son|tiene)\s+(?:cinco|cuatro|tres|dos|\d+)?\s*([\w\s]{3,40}?)[:\s]+(.+)$',
            fact
        )
        items = None
        subject = None
        if list_match:
            subject = list_match.group(1).strip()
            list_text = list_match.group(2)
            items = re.split(r',\s*|\s+y\s+', list_text)
        elif list_match2:
            subject = list_match2.group(1).strip()
            list_text = list_match2.group(2)
            items = re.split(r',\s*|\s+y\s+', list_text)

        if items:
            # Limpiar items: quitar puntuacion y espacios
            # Filtro: longitud >= 2 (aceptar items cortos como "A, B" de tests)
            items = [it.strip().strip('.,;:') for it in items if it.strip() and len(it.strip()) >= 2]
            # Si tenemos 2+ items, expandir
            if len(items) >= 2:
                # Guardar el hecho completo tambien (para contexto)
                expanded.append(fact)
                # Guardar cada item por separado
                for item in items[:8]:  # max 8 items
                    item_fact = f"{subject} incluye: {item}"
                    if len(item_fact) > 15 and item_fact not in expanded:
                        expanded.append(item_fact)
            else:
                expanded.append(fact)
        else:
            expanded.append(fact)

    return expanded


def learn_from_user_input(text: str, memory) -> int:
    """Extrae y aprende hechos del input del usuario.
    
    Args:
        text: Texto del usuario
        memory: Instancia de NexusMemory
        
    Returns:
        Cantidad de hechos aprendidos
    """
    facts = extract_facts_from_text(text)
    learned = 0
    for fact in facts:
        # Confianza baja para aprendizaje automático (se refuerza con repetición)
        memory.learn_fact(fact, category="aprendizaje", confidence=0.2, source="auto_usuario")
        learned += 1

    if learned:
        logger.debug(f"Aprendidos {learned} hechos de entrada del usuario")
    return learned


def learn_from_response(response: str, memory) -> int:
    """Extrae y aprende hechos de la respuesta generada (SLM o simbólico).
    
    Las respuestas aprendidas tienen confianza baja, pero permiten
    que el sistema recuerde sus propias respuestas para futuras consultas.
    
    Args:
        response: Respuesta generada
        memory: Instancia de NexusMemory
        
    Returns:
        Cantidad de hechos aprendidos
    """
    facts = extract_facts_from_text(response)
    learned = 0
    for fact in facts:
        memory.learn_fact(fact, category="aprendizaje", confidence=0.15, source="auto_respuesta")
        learned += 1

    if learned:
        logger.debug(f"Aprendidos {learned} hechos de respuesta")
    return learned


def reinforce_from_feedback(text: str, memory) -> bool:
    """Refuerza hechos recientes si el usuario da feedback positivo.
    
    Args:
        text: Texto del usuario (feedback)
        memory: Instancia de NexusMemory
        
    Returns:
        True si se reforzó algún hecho
    """
    text_lower = text.lower().strip()
    
    # Detectar refuerzo
    is_reinforce = any(w in text_lower for w in REINFORCE_WORDS)
    is_negate = any(w in text_lower for w in NEGATE_WORDS)
    
    if is_reinforce and not is_negate:
        # Reforzar los hechos más recientes
        recent = memory.get_facts_by_category("aprendizaje")
        if recent:
            # Re-aprender para aumentar confianza
            for fact in recent[:3]:
                memory.learn_fact(
                    fact["fact"],
                    category="aprendizaje",
                    confidence=0.1,
                    source="refuerzo_usuario"
                )
            logger.debug(f"Reforzados {min(3, len(recent))} hechos por feedback positivo")
            return True
    
    return False
