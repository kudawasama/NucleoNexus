"""
Núcleo Nexus — Diccionario de Sinónimos
=========================================
Mapea palabras equivalentes para expandir queries y mejorar
la búsqueda en memoria semántica.

Cuando el usuario pregunta por "auto", también debe encontrar
hechos guardados como "coche", "carro", "vehículo".

Vision: 'Inteligencia por arquitectura, no por tamaño'
Con sinonimos el sistema entiende más sin necesitar embeddings.
"""

# ─── Diccionario principal ─────────────────────────────────────
# Formato: palabra_clave -> [sinonimos]
# Se busca bidireccionalmente: si la palabra esta en cualquier
# lista, se obtienen todos los sinonimos del grupo

SYNONYMS = {
    # Transporte
    "auto": ["coche", "carro", "vehículo", "automóvil", "auto"],
    "coche": ["auto", "carro", "vehículo", "automóvil", "coche"],
    "carro": ["auto", "coche", "vehículo", "carro"],
    "vehículo": ["auto", "coche", "carro", "vehículo"],

    # Personas
    "persona": ["individuo", "sujeto", "persona", "ser humano"],
    "chico": ["niño", "muchacho", "chico", "joven"],
    "chica": ["niña", "muchacha", "chica", "joven"],
    "niño": ["chico", "niño", "infante", "nene"],
    "niña": ["chica", "niña", "infanta", "nena"],

    # Profesiones
    "médico": ["doctor", "doctora", "médico", "médica", "facultativo", "facultativa"],
    "medico": ["doctor", "doctora", "médico", "médica", "facultativo", "facultativa", "medico"],
    "doctor": ["médico", "medico", "doctor", "doctora"],
    "doctora": ["médico", "medico", "doctor", "doctora"],
    "abogado": ["licenciado", "abogado", "letrado"],

    # Comida
    "comida": ["alimento", "comida", "nutrimento"],
    "almuerzo": ["comida", "almuerzo", "récipe"],
    "cena": ["comida", "cena"],

    # Vivienda
    "casa": ["hogar", "vivienda", "casa", "residencia"],
    "departamento": ["piso", "apartamento", "departamento"],

    # Tecnologia
    "computadora": ["ordenador", "computador", "computadora", "pc", "computador"],
    "ordenador": ["computadora", "ordenador", "pc"],
    "programa": ["software", "programa", "aplicación", "app"],
    "software": ["programa", "software", "aplicación"],

    # Educacion
    "escuela": ["colegio", "escuela", "instituto"],
    "universidad": ["universidad", "facultad"],
    "profesor": ["docente", "maestro", "profesor", "educador"],

    # Finanzas
    "dinero": ["plata", "efectivo", "dinero", "capital"],
    "plata": ["dinero", "plata", "efectivo"],
    "banco": ["banco", "entidad bancaria"],

    # Geografia
    "país": ["nación", "estado", "país"],
    "ciudad": ["urbe", "ciudad", "población"],
    "calle": ["vía", "calle", "avenida"],

    # Programacion
    "código": ["programa", "código", "script"],
    "función": ["método", "función", "rutina"],
    "variable": ["variable", "dato"],
    "error": ["bug", "fallo", "error", "defecto"],

    # Tiempo
    "rápido": ["veloz", "rápido", "presto"],
    "lento": ["pausado", "lento", "lerdo"],
    "grande": ["amplio", "grande", "vasto"],
    "pequeño": ["chico", "pequeño", "reducido"],

    # Conectores de pregunta
    "que es": ["qué es", "que es", "definición", "significado"],
    "qué es": ["que es", "qué es", "definición"],
    "cómo": ["como", "de qué manera", "cómo"],
    "donde": ["dónde", "en qué lugar", "donde"],
    "cuándo": ["cuando", "en qué momento", "cuándo"],
    "por qué": ["porque", "motivo", "razón", "por qué"],
    "porque": ["ya que", "puesto que", "porque"],

    # Sinonimos especificos del proyecto
    "contabilidad": ["contabilidad", "contabilizar", "registro contable"],
    "asiento": ["asiento", "apunte", "partida", "anotación"],
    "fundamento": ["fundamento", "base", "principio", "pilar"],
    "principio": ["fundamento", "principio", "regla", "base"],
    "postulado": ["postulado", "principio", "axioma"],
}


# Sinonimos de palabras de programacion (para cuando el SLM responde)
_EXTRA_SYNONYMS = {
    "python": ["python", "lenguaje python"],
    "java": ["java", "lenguaje java"],
    "javascript": ["javascript", "js", "lenguaje javascript"],
    "codigo": ["código", "programa", "script", "source code"],
    "funcion": ["función", "método", "rutina", "function"],
    "variable": ["variable", "dato", "valor"],
    "clase": ["clase", "tipo", "class"],
    "objeto": ["objeto", "instancia", "object"],
    "base de datos": ["base de datos", "bd", "database", "db"],
    "servidor": ["servidor", "server", "backend"],
    "cliente": ["cliente", "client", "frontend"],
    "interfaz": ["interfaz", "ui", "interface", "interfaz de usuario"],
}
# Combinar
SYNONYMS.update(_EXTRA_SYNONYMS)


def get_synonyms(word: str) -> list[str]:
    """Devuelve la lista de sinonimos de una palabra.

    Si la palabra no esta en el diccionario, devuelve [word].
    """
    word_lower = word.lower().strip()
    if not word_lower:
        return []
    return SYNONYMS.get(word_lower, [word_lower])


def expand_query(query: str) -> list[str]:
    """Expande una query agregando sinonimos de sus terminos clave.

    Ejemplo:
        'que es python' -> ['que es python', 'definicion python',
                            'significado python', 'que significa python']
    """
    import re
    query_lower = query.lower().strip()
    words = re.findall(r'\b[a-záéíóúñü]{3,}\b', query_lower)

    # Encontrar sinonimos para cada palabra
    expansions = set([query_lower])  # Original siempre incluido

    for word in words:
        syns = get_synonyms(word)
        for syn in syns:
            if syn != word:
                # Reemplazar la palabra por sinonimo en la query
                # Solo si la palabra no es una stop word comun
                if word not in {'que', 'qué', 'es', 'son', 'las', 'los', 'una', 'uno',
                                'por', 'para', 'con', 'del', 'los', 'las',
                                'como', 'cómo', 'sobre', 'cual', 'cuál',
                                'cuando', 'donde', 'porque', 'este', 'esta'}:
                    # Reemplazar usando regex (preservando boundaries)
                    new_query = re.sub(
                        r'\b' + re.escape(word) + r'\b',
                        syn,
                        query_lower
                    )
                    if new_query != query_lower:
                        expansions.add(new_query)

    return list(expansions)[:5]  # Max 5 expansions


def expand_fact_storage(fact: str) -> list[str]:
    """Genera sinonimos de un hecho para guardarlo en memoria.

    Si el hecho contiene 'auto', tambien se guarda como sinonimo
    'coche' (con menos confidence) para mejorar la busqueda.

    Returns:
        Lista de hechos alternativos (con sinonimos)
    """
    import re
    fact_lower = fact.lower()
    words = re.findall(r'\b[a-záéíóúñü]{3,}\b', fact_lower)

    # Si el hecho ya tiene sinonimos en el diccionario, no expandir
    expansions = [fact]  # Original siempre

    for word in words:
        syns = get_synonyms(word)
        if len(syns) > 1:  # Tiene sinonimos
            for syn in syns:
                if syn != word:
                    new_fact = re.sub(
                        r'\b' + re.escape(word) + r'\b',
                        syn,
                        fact_lower
                    )
                    if new_fact != fact_lower and new_fact not in expansions:
                        expansions.append(new_fact)

    return expansions[:3]  # Max 3


if __name__ == "__main__":
    # Tests
    print("Test de sinonimos:")
    print(f"  'auto' -> {get_synonyms('auto')}")
    print(f"  'python' -> {get_synonyms('python')}")
    print(f"  'que es python' expandido:")
    for exp in expand_query("que es python"):
        print(f"    - {exp}")
    print()
    print("Expandir hecho:")
    for exp in expand_fact_storage("Python es un lenguaje de programacion"):
        print(f"  - {exp}")
