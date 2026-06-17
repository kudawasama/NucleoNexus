"""
Skill — Conversor de Monedas
==============================
Consulta valores del dolar, UF, UTM, euro en CLP.
Usa mindicador.cl (API gratuita chilena, sin API key).
"""

import urllib.request
import json
from skills.registry import Skill


def register() -> Skill:
    skill = Skill(name="monedas", description="Conversor de monedas: dolar, UF, UTM, euro a CLP", version="1.0.0")

    def _indicador(tipo: str = ""):
        """Obtiene el valor de un indicador desde mindicador.cl"""
        try:
            tipo = tipo.upper().strip()
            mapa = {"DOLAR": "dolar", "UF": "uf", "UTM": "utm", "EURO": "euro", "IPC": "ipc"}
            key = mapa.get(tipo, tipo.lower())
            url = f"https://mindicador.cl/api/{key}"
            req = urllib.request.Request(url, headers={"User-Agent": "Nexus/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            serie = data.get("serie", [])
            if not serie:
                return {"respuesta": f"No encontre datos para {tipo}"}

            ultimo = serie[0]
            valor = ultimo["valor"]
            fecha = ultimo.get("fecha", "")[:10]
            nombre = data.get("nombre", tipo)
            return {"respuesta": f"{nombre}: **${valor:,.2f}** ({fecha})"}

        except Exception as e:
            return {"respuesta": f"Error consultando {tipo}: {e}"}

    skill.register_action("indicador", "Consulta valor de dolar, UF, UTM, euro, IPC", _indicador,
        parameters={"tipo": {"type": "string", "description": "dolar, uf, utm, euro, ipc"}})

    def _convertir(monto: float = 0, desde: str = "", a: str = ""):
        """Convierte entre monedas usando tipo de cambio actual."""
        try:
            desde = desde.upper().strip()
            a = a.upper().strip()

            # Obtener valor de cada moneda en CLP
            valores = {}
            for moneda in [desde, a]:
                if moneda == "CLP":
                    valores[moneda] = 1
                else:
                    url = f"https://mindicador.cl/api/{moneda.lower()}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Nexus/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                    serie = data.get("serie", [])
                    if serie:
                        valores[moneda] = serie[0]["valor"]

            if desde not in valores or a not in valores:
                return {"respuesta": f"No pude obtener valores para {desde} o {a}"}

            en_clp = monto * valores[desde]
            resultado = en_clp / valores[a]
            return {"respuesta": f"{monto:g} {desde} = **{resultado:,.2f} {a}**"}

        except Exception as e:
            return {"respuesta": f"Error en conversion: {e}"}

    skill.register_action("convertir", "Convierte entre monedas (dolar, euro, uf, clp)", _convertir,
        parameters={
            "monto": {"type": "number", "description": "Cantidad a convertir"},
            "desde": {"type": "string", "description": "Moneda origen (USD, EUR, UF, CLP)"},
            "a": {"type": "string", "description": "Moneda destino"},
        })

    return skill
