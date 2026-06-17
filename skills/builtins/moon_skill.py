"""
Skill — Fase Lunar
===================
Calcula la fase de la luna para cualquier fecha.
Algoritmo astronomico simple, sin APIs externas.
"""

import math
import time
from skills.registry import Skill


def _fase_lunar(fecha=None):
    """Calcula la fase lunar para una fecha dada.
    Retorna: nombre de la fase, iluminacion %, edad lunar en dias.
    Algoritmo: Jean Meeus 'Astronomical Algorithms'.
    """
    if fecha is None:
        fecha = time.localtime()[:3]  # (year, month, day)

    year, month, day = fecha

    # Convertir a dia juliano
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5

    # Dias desde luna nueva conocida (6 enero 2000)
    dias = jd - 2451549.5
    lunaciones = dias / 29.53058867  # ciclo lunar
    edad = (lunaciones - math.floor(lunaciones)) * 29.53058867

    # Determinar fase
    iluminacion = (1 - math.cos(2 * math.pi * edad / 29.53058867)) / 2 * 100

    if edad < 1.845:
        nombre, icono = "Luna Nueva", "🌑"
    elif edad < 5.536:
        nombre, icono = "Luna Creciente", "🌒"
    elif edad < 9.228:
        nombre, icono = "Cuarto Creciente", "🌓"
    elif edad < 12.919:
        nombre, icono = "Luna Gibosa Creciente", "🌔"
    elif edad < 16.610:
        nombre, icono = "Luna Llena", "🌕"
    elif edad < 20.301:
        nombre, icono = "Luna Gibosa Menguante", "🌖"
    elif edad < 23.993:
        nombre, icono = "Cuarto Menguante", "🌗"
    elif edad < 27.684:
        nombre, icono = "Luna Menguante", "🌘"
    else:
        nombre, icono = "Luna Nueva", "🌑"

    return {
        "nombre": f"{icono} {nombre}",
        "iluminacion": round(iluminacion, 1),
        "edad_dias": round(edad, 1),
    }


NOMBRES_FASES = {
    "nueva": "Luna Nueva",
    "llena": "Luna Llena",
    "creciente": "Cuarto Creciente",
    "menguante": "Cuarto Menguante",
}


def register() -> Skill:
    skill = Skill(name="luna", description="Muestra la fase lunar actual o de una fecha", version="1.0.0")

    def _fase_actual():
        info = _fase_lunar()
        return {"respuesta": f"Fase lunar hoy: **{info['nombre']}**\nIluminacion: {info['iluminacion']}%\nEdad lunar: {info['edad_dias']} dias"}

    skill.register_action("fase_actual", "Muestra la fase lunar de hoy", _fase_actual)

    def _fase_en(fecha: str = ""):
        """formato: 2026-12-25"""
        try:
            parts = fecha.strip().split("-")
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            info = _fase_lunar((y, m, d))
            return {"respuesta": f"Fase lunar el {fecha}: **{info['nombre']}** (ilum:{info['iluminacion']}%)"}
        except:
            return {"respuesta": "Formato: fase_en 2026-12-25"}

    skill.register_action("fase_en", "Fase lunar para una fecha especifica (YYYY-MM-DD)", _fase_en,
        parameters={"fecha": {"type": "string", "description": "Formato YYYY-MM-DD"}})

    def _proxima_fase(fase: str = ""):
        """Calcula la proxima luna nueva o llena"""
        target = fase.lower().strip()
        if target not in NOMBRES_FASES:
            return {"respuesta": f"Fases disponibles: nueva, llena, creciente, menguante"}

        hoy = time.localtime()[:3]
        for dias in range(30):
            prueba = time.strptime(f"{hoy[0]}-{hoy[1]}-{hoy[2]+dias}", "%Y-%m-%d")[:3] if dias == 0 else \
                     time.localtime(time.mktime((hoy[0], hoy[1], hoy[2]+dias, 0,0,0,0,0,0)))[:3]
            # Simplificado: probamos dia por dia
            try:
                t = time.mktime((hoy[0], hoy[1], hoy[2]+dias, 0,0,0,0,0,0))
                fecha_f = time.localtime(t)[:3]
                info = _fase_lunar(fecha_f)
                if NOMBRES_FASES[target] in info["nombre"]:
                    fecha_str = f"{fecha_f[2]}/{fecha_f[1]}/{fecha_f[0]}"
                    return {"respuesta": f"Proxima {NOMBRES_FASES[target]}: **{fecha_str}** ({info['iluminacion']}%)"}
            except:
                continue
        return {"respuesta": f"No encontre la proxima {fase} en los proximos 30 dias."}

    skill.register_action("proxima_fase", "Calcula la proxima luna nueva, llena, etc", _proxima_fase,
        parameters={"fase": {"type": "string", "description": "nueva, llena, creciente, menguante"}})

    return skill
