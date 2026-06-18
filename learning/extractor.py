"""
Núcleo Nexus — Extractor Automático de Conocimiento v2
=======================================================
Extrae hechos de CADA interacción para que Qwen 0.5B
se vuelva PRO conversación tras conversación.

A diferencia de v1, este extractor es mucho más agresivo:
aprende de todo: preguntas, respuestas, afirmaciones, negaciones.
"""
import re
import logging

logger = logging.getLogger("nexus.learning.extractor")

# ─── VERBOS por categoría ──────────────────────────────────
# Cada entrada: (verbo_singular, verbo_plural)
VERBOS_SER = ["es", "son", "era", "eran", "fue", "fueron"]
VERBOS_TENER = ["tiene", "tienen", "posee", "poseen", "contiene", "contienen",
                "incluye", "incluyen", "alberga", "albergan"]
VERBOS_ACCION = ["hace", "hacen", "realiza", "realizan", "ejecuta", "ejecutan",
                 "crea", "crean", "genera", "generan", "produce", "producen",
                 "fabrica", "fabrican", "elabora", "elaboran"]
VERBOS_PROCESO = ["filtra", "filtran", "absorbe", "absorben", "transporta", "transportan",
                  "elimina", "eliminan", "expulsa", "expulsan", "bombea", "bombean",
                  "limpia", "limpian", "convierte", "convierten", "transforma", "transforman",
                  "separa", "separan", "recoge", "recogen", "distribuye", "distribuyen"]
VERBOS_NECESIDAD = ["necesita", "necesitan", "requiere", "requieren", "utiliza", "utilizan",
                    "usa", "usan", "ocupa", "ocupan", "depende", "dependen"]
VERBOS_FUNCION = ["funciona", "funcionan", "opera", "operan", "trabaja", "trabajan",
                  "ayuda", "ayudan", "permite", "permiten", "sirve", "sirven",
                  "contribuye", "contribuyen"]
VERBOS_UBICACION = ["esta", "esta", "estan", "está", "están", "queda", "quedan",
                     "se encuentra", "se encuentran", "se ubica", "se ubican"]

# Todos los verbos combinados para patrones
SER_PATTERN = "|".join(VERBOS_SER)
TENER_PATTERN = "|".join(VERBOS_TENER)
ACCION_PATTERN = "|".join(VERBOS_ACCION)
PROCESO_PATTERN = "|".join(VERBOS_PROCESO)
NECESIDAD_PATTERN = "|".join(VERBOS_NECESIDAD)
FUNCION_PATTERN = "|".join(VERBOS_FUNCION)
UBICACION_PATTERN = "|".join(VERBOS_UBICACION)

# ─── PATRONES DE EXTRACCIÓN ─────────────────────────────────
# Cada patrón captura: sujeto + verbo + objeto
# Más patrones = más hechos aprendidos por conversación

FACT_PATTERNS = [
    # X es/son Y (el núcleo es Y, etc)
    rf'(?:el|la|los|las|un|una)\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+)?)\s+(?:{SER_PATTERN})\s+(?:un|una|el|la|los|las)?\s*([a-záéíóúñü].{{3,100}})',
    
    # X tiene/contiene/incluye Y
    rf'(?:el|la|los|las)\s+([a-záéíóúñü]{{3,30}}(?:\s+[a-záéíóúñü]+){{0,3}})\s+(?:{TENER_PATTERN})\s+([a-záéíóúñü].{{3,100}})',
    
    # X hace/produce/crea Y
    rf'(?:el|la|los|las|un|una)\s+([a-záéíóúñü]{{3,30}}(?:\s+[a-záéíóúñü]+){{0,3}})\s+(?:{ACCION_PATTERN})\s+([a-záéíóúñü].{{3,100}})',
    
    # X filtra/transporta/convierte Y
    rf'(?:el|la|los|las|un|una)\s+([a-záéíóúñü]{{3,30}}(?:\s+[a-záéíóúñü]+){{0,3}})\s+(?:{PROCESO_PATTERN})\s+([a-záéíóúñü].{{3,100}})',
    
    # X necesita/requiere/utiliza Y
    rf'(?:el|la|los|las|un|una)\s+([a-záéíóúñü]{{3,30}}(?:\s+[a-záéíóúñü]+){{0,3}})\s+(?:{NECESIDAD_PATTERN})\s+([a-záéíóúñü].{{3,100}})',
    
    # X funciona/sirve/ayuda para Y
    rf'(?:el|la|los|las|un|una)\s+([a-záéíóúñü]{{3,30}}(?:\s+[a-záéíóúñü]+){{0,3}})\s+(?:{FUNCION_PATTERN})\s+(?:a|para|en|al)?\s+([a-záéíóúñü].{{3,100}})',
    
    # X está/queda/se encuentra en Y
    rf'(?:el|la|los|las|un|una)\s+([a-záéíóúñü]{{3,30}}(?:\s+[a-záéíóúñü]+){{0,3}})\s+(?:{UBICACION_PATTERN})\s+(?:en|dentro de|cerca de|al lado de)\s+([a-záéíóúñü].{{3,100}})',
    
    # X significa Y / X se refiere a Y
    r'([a-záéíóúñü]{3,30})\s+(?:significa|quiere decir|se refiere a|es lo mismo que)\s+([a-záéíóúñü].{3,100})',
    
    # X se usa para Y
    r'([a-záéíóúñü]{3,30})\s+se\s+(?:usa|utiliza|ocupa|aplica)\s+(?:para|en|como)\s+([a-záéíóúñü].{3,100})',
    
    # X está compuesto/formado por Y
    r'([a-záéíóúñü]{3,30}(?:\s+[a-záéíóúñü]+){0,3})\s+(?:está|esta)\s+(?:compuesto|compuesta|formado|formada|hecho|hecha)\s+(?:por|de)\s+([a-záéíóúñü].{3,100})',
    
    # X ocurre/sucede cuando Y
    r'([a-záéíóúñü]{3,30}(?:\s+[a-záéíóúñü]+){0,3})\s+(?:ocurre|sucede|pasa|ocurre|suceden|pasan)\s+cuando\s+([a-záéíóúñü].{3,100})',
]

# ─── FEEDBACK ───────────────────────────────────────────────
REINFORCE_WORDS = {"correcto", "exacto", "bien", "sí", "si", "cierto", "claro",
                   "bueno", "vale", "de acuerdo", "ok", "okay", "perfecto",
                   "excelente", "asi es", "tal cual", "justo"}
REJECT_WORDS = {"no", "incorrecto", "falso", "mal", "error", "mentira",
                "equivocado", "eso no es", "no es asi", "te equivocas"}


def extract_facts(text: str) -> list:
    """Extrae todos los hechos de un texto usando todos los patrones.
    
    Devuelve lista de strings con los hechos extraídos.
    """
    if not text or len(text) < 15:
        return []
    
    text_lower = text.lower().strip()
    facts = []
    
    for pattern in FACT_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            if isinstance(match, tuple):
                fact = " ".join(match)
            else:
                fact = match
            # Limpiar
            fact = fact.strip().strip(".,;:!¿?¡")
            words = fact.split()
            if len(words) >= 2 and len(fact) > 10:
                # Evitar duplicados cercanos
                if not any(fact in existing or existing in fact for existing in facts):
                    facts.append(fact)
    
    return facts


def learn_from_all(text: str, memory, source: str = "auto") -> int:
    """Aprende de CUALQUIER texto: preguntas, respuestas, afirmaciones.
    
    Args:
        text: Texto del cual extraer hechos
        memory: Instancia de NexusMemory
        source: Origen (usuario, respuesta, correccion)
        
    Returns:
        Cantidad de hechos aprendidos
    """
    facts = extract_facts(text)
    learned = 0
    for fact in facts:
        # Confianza base baja (0.2) - sube con repeticion
        memory.learn_fact(fact, category="aprendizaje", confidence=0.2, source=source)
        learned += 1
    return learned


def detect_feedback(text: str) -> str:
    """Detecta si el usuario esta dando feedback positivo o negativo.
    
    Returns:
        "reforzar" | "rechazar" | "ninguno"
    """
    text_lower = text.lower().strip()
    is_reject = any(w in text_lower for w in REJECT_WORDS)
    is_reinforce = any(w in text_lower for w in REINFORCE_WORDS)
    
    if is_reject:
        return "rechazar"
    if is_reinforce:
        return "reforzar"
    return "ninguno"


def handle_feedback(text: str, memory) -> bool:
    """Procesa feedback del usuario: refuerza o rechaza hechos recientes.
    
    Returns:
        True si se realizó alguna acción
    """
    action = detect_feedback(text)
    if action == "ninguno":
        return False
    
    if action == "reforzar":
        # Reforzar los 5 hechos más recientes de la categoría aprendizaje
        recent = memory.get_facts_by_category("aprendizaje")
        if recent:
            for fact in recent[:5]:
                memory.learn_fact(fact["fact"], category="aprendizaje",
                                confidence=0.15, source="refuerzo")
            logger.debug(f"Reforzados {min(5, len(recent))} hechos")
            return True
    
    if action == "rechazar":
        # Los hechos NO se borran, solo bajan su confianza
        # En futura versión: marcar como rechazados
        logger.debug("Feedback negativo detectado")
        return True
    
    return False
