"""
Skill Builtin — Clima (Weather)
================================
Skill de ejemplo que muestra como extender Nexus con nuevas capacidades.
Usa wttr.in (gratuito, sin API key) para consultar el clima.

Para crear una skill nueva solo necesitas:
1. Crear un archivo .py en skills/builtins/
2. Definir una funcion register() que devuelva un Skill
3. Registrar acciones con skill.register_action()
4. Listo — Nexus la carga automaticamente al iniciar
"""

import re
import urllib.request
import urllib.error
import json

from skills.registry import Skill


def register() -> Skill:
    """Registra y devuelve la skill de clima."""
    skill = Skill(
        name="weather",
        description="Consulta el clima actual y pronosticos en cualquier ciudad",
        version="1.0.0",
        author="Nexus"
    )

    # --- get_weather ---
    def _get_weather(text: str = "", ciudad: str = ""):
        """Consulta el clima actual para una ciudad."""
        # Extraer ciudad del texto si no se especifico directamente
        location = ciudad.strip() if ciudad.strip() else _extract_city(text)
        if not location:
            return {
                "error": "No especificaste ninguna ciudad. Ej: 'clima en Santiago'",
                "_help": "Usa: 'clima en [ciudad]' o 'temperatura en [ciudad]'"
            }

        try:
            # wttr.in devuelve JSON simple sin necesidad de API key
            url = f"https://wttr.in/{urllib.request.quote(location)}?format=j1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "curl/8.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            # Extraer datos actuales
            current = data["current_condition"][0]
            temp_c = current["temp_C"]
            feels_like = current["FeelsLikeC"]
            humidity = current["humidity"]
            wind = current["windspeedKmph"]
            desc = current["weatherDesc"][0]["value"]
            pressure = current["pressure"]

            # Pronostico 3 dias
            forecasts = []
            for day in data["weather"][:3]:
                date = day["date"]
                max_t = day["maxtempC"]
                min_t = day["mintempC"]
                desc_day = day["hourly"][4]["weatherDesc"][0]["value"]
                forecasts.append(f"  {date}: {min_t}-{max_t}C, {desc_day}")

            result = (
                f"Clima en **{location.title()}** ahora:\n"
                f"  Temperatura: {temp_c}C (sensacion {feels_like}C)\n"
                f"  Estado: {desc}\n"
                f"  Humedad: {humidity}% | Viento: {wind} km/h\n"
                f"  Presion: {pressure} hPa\n"
                f"\nPronostico 3 dias:\n"
                + "\n".join(forecasts)
            )
            return {"respuesta": result, "ciudad": location, "temp": temp_c}

        except urllib.error.HTTPError as e:
            return {"error": f"Ciudad no encontrada: {location} (HTTP {e.code})"}
        except urllib.error.URLError:
            return {"error": "No hay conexion a internet. Sin conexion no puedo consultar el clima."}
        except Exception as e:
            return {"error": f"Error consultando clima: {e}"}

    skill.register_action(
        name="get_weather",
        description="Consulta el clima actual y pronostico para una ciudad",
        handler=_get_weather,
        parameters={
            "ciudad": {
                "type": "string",
                "description": "Nombre de la ciudad (ej: Santiago, Huechuraba)",
            },
            "text": {
                "type": "string",
                "description": "Texto completo del usuario (para extraer ciudad automaticamente)",
            },
        },
    )

    return skill


# Cache de ultima ciudad consultada
_last_city = None

def _extract_city(text: str) -> str:
    """Extrae el nombre de una ciudad del texto del usuario.
    Si no encuentra ciudad, usa la ultima consultada (contexto)."""
    global _last_city
    
    # Palabras que NO son ciudades pero el regex podria capturar
    not_cities = {'minima', 'maxima', 'actual', 'hoy', 'manana', 'ahora', 
                  'por', 'favor', 'plz', 'gracias', 'temperatura', 'clima',
                  'pronostico', 'ambiente', 'cual', 'que', 'como', 'esta',
                  'sensacion', 'termica', 'humedad', 'viento', 'presion'}
    
    # Patrones: "en [ciudad]", "clima [ciudad]", "pronostico [ciudad]"
    patterns = [
        r'(?:en|para|de)\s+([a-záéíóúñ\s]+?)(?:$|[?.,!]|por favor|plz)',
        r'(?:clima|temperatura|pronostico)\s+(?:de\s+|en\s+|para\s+)?([a-záéíóúñ\s]+?)(?:$|[?.,!]|por favor|plz)',
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            city = m.group(1).strip()
            # Limpiar palabras sobrantes
            city = re.sub(r'\b(por favor|plz|gracias|ahora|hoy|manana)\b', '', city).strip()
            city = ' '.join(w for w in city.split() if w not in not_cities)
            if city and len(city) > 1:
                _last_city = city
                return city
    
    # Si no encontro ciudad en este texto, usar la ultima
    if _last_city:
        return _last_city
    return ""
