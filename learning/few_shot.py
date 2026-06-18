"""
Núcleo Nexus — Dataset Few-Shot para Qwen 0.5B
===============================================
Ejemplos de calidad para enseñar a Qwen 0.5B el formato estructurado.
Cada ejemplo muestra: entrada → respuesta JSON esperada.

Usados como few-shot en el prompt del sistema para mejorar
la adherencia al formato sin necesidad de fine-tuning.
"""

FEW_SHOT_EXAMPLES = [
    {
        "input": "explicame como se hace una multiplicacion",
        "output": {
            "razonamiento": "El usuario pregunta sobre multiplicacion. Puedo responder con mi conocimiento.",
            "accion": "responder",
            "respuesta": "Multiplicar es sumar un numero varias veces. Por ejemplo, 3x4 significa sumar 3 cuatro veces: 3+3+3+3 = 12."
        }
    },
    {
        "input": "que es la fotosintesis",
        "output": {
            "razonamiento": "Pregunta sobre fotosintesis, un proceso biologico.",
            "accion": "responder",
            "respuesta": "La fotosintesis es el proceso donde las plantas convierten luz solar, agua y dioxido de carbono en glucosa y oxigeno."
        }
    },
    {
        "input": "cuanto es 2+2",
        "output": {
            "razonamiento": "El usuario pide un calculo matematico simple.",
            "accion": "responder",
            "respuesta": "2+2 = 4"
        }
    },
    {
        "input": "que es un agujero negro",
        "output": {
            "razonamiento": "Pregunta sobre un concepto de astronomia.",
            "accion": "responder",
            "respuesta": "Un agujero negro es una region del espacio con gravedad tan intensa que ni la luz puede escapar."
        }
    },
    {
        "input": "como se llama el presidente de chile",
        "output": {
            "razonamiento": "No tengo informacion actualizada sobre el presidente de Chile.",
            "accion": "responder",
            "respuesta": "No tengo esa informacion actualizada. Puedes ensenarmelo y lo recordare."
        }
    },
]


def build_few_shot_prompt() -> str:
    """Construye el bloque de ejemplos few-shot para inyectar en el prompt."""
    lines = ["=== EJEMPLOS ==="]
    for ex in FEW_SHOT_EXAMPLES:
        lines.append(f"Pregunta: {ex['input']}")
        lines.append(f"JSON: {{")
        for key, val in ex['output'].items():
            lines.append(f'  "{key}": "{val}"')
        lines.append(f"}}")
        lines.append("")
    lines.append("=== FIN EJEMPLOS ===")
    return "\n".join(lines)
