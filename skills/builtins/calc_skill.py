"""
Skill — Calculadora Cientifica
===============================
Operaciones matematicas avanzadas usando math de la stdlib.
Sin dependencias externas.
"""

import math
import re
from skills.registry import Skill


def register() -> Skill:
    skill = Skill(name="calculadora", description="Calculadora cientifica: trigonometria, logaritmos, raices", version="1.0.0")

    def _calcular(expresion: str = ""):
        if not expresion.strip():
            return {"respuesta": "Que quieres calcular? Ej: raiz cuadrada de 144, seno de 45 grados"}

        e = expresion.lower().strip()

        # Mapeo de palabras a funciones
        operations = {
            "raiz": (lambda x: math.sqrt(x), "raiz cuadrada"),
            "sqrt": (lambda x: math.sqrt(x), "raiz cuadrada"),
            "seno": (lambda x: math.sin(math.radians(x)), "seno"),
            "coseno": (lambda x: math.cos(math.radians(x)), "coseno"),
            "tangente": (lambda x: math.tan(math.radians(x)), "tangente"),
            "log": (lambda x: math.log10(x), "logaritmo base 10"),
            "log10": (lambda x: math.log10(x), "logaritmo base 10"),
            "ln": (lambda x: math.log(x), "logaritmo natural"),
            "log natural": (lambda x: math.log(x), "logaritmo natural"),
            "sen": (lambda x: math.sin(math.radians(x)), "seno"),
            "cos": (lambda x: math.cos(math.radians(x)), "coseno"),
            "tan": (lambda x: math.tan(math.radians(x)), "tangente"),
        }

        # Detectar operacion
        for palabra, (func, nombre) in operations.items():
            if palabra in e:
                nums = re.findall(r'(\d+\.?\d*)', e)
                if nums:
                    try:
                        val = float(nums[0])
                        res = func(val)
                        return {"respuesta": f"{nombre} de {val} = **{res:.4f}**"}
                    except Exception as ex:
                        return {"respuesta": f"Error: {ex}"}

        # Potencia: "2 al cubo", "5 al cuadrado", "2^10"
        pot_match = re.search(r'(\d+)\s*(?:al?\s*|\^)(\d+)', e)
        if pot_match:
            base, exp = float(pot_match.group(1)), float(pot_match.group(2))
            res = base ** exp
            return {"respuesta": f"{base}^{exp} = **{res:g}**"}

        # Porcentaje: "20% de 500"
        pct_match = re.search(r'(\d+\.?\d*)\s*%\s*(?:de|del?)\s*(\d+\.?\d*)', e)
        if pct_match:
            pct, total = float(pct_match.group(1)), float(pct_match.group(2))
            res = total * pct / 100
            return {"respuesta": f"El {pct}% de {total} = **{res:g}**"}

        # Constantes: "pi", "e"
        if e == "pi" or e == "π":
            return {"respuesta": f"π = **{math.pi:.10f}**"}
        if e == "e" or e == "euler":
            return {"respuesta": f"e = **{math.e:.10f}**"}

        return {"respuesta": "No entendi la operacion. Prueba: 'raiz de 144', 'seno de 45', '2 al cubo', '20% de 500'"}

    skill.register_action("calcular", "Realiza operaciones de calculadora cientifica", _calcular,
        parameters={"expresion": {"type": "string", "description": "Ej: raiz de 144, seno de 45, 2 al cubo"}})

    return skill
