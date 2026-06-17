"""
Skill — Network / IP / DNS
===========================
Consulta IP publica, resuelve dominios, ping.
Usa servicios publicos gratuitos.
"""

import urllib.request
import socket
import json
from skills.registry import Skill


def _get_public_ip():
    """Obtiene la IP publica desde varios servicios."""
    services = ["https://api.ipify.org", "https://icanhazip.com", "https://ifconfig.me"]
    for url in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                ip = r.read().decode().strip()
                if ip:
                    return ip
        except:
            continue
    return None


def register() -> Skill:
    skill = Skill(name="network", description="Consulta IP publica, resuelve dominios, informacion de red", version="1.0.0")

    def _mi_ip():
        ip = _get_public_ip()
        if ip:
            return {"respuesta": f"Tu IP publica es: **{ip}**"}
        return {"respuesta": "No pude obtener tu IP publica. Sin conexion?"}

    skill.register_action("mi_ip", "Muestra tu direccion IP publica", _mi_ip)

    def _resolver_dominio(dominio: str = ""):
        if not dominio.strip():
            return {"respuesta": "Que dominio quieres resolver? Ej: resolver google.com"}
        try:
            ip = socket.gethostbyname(dominio.strip())
            return {"respuesta": f"{dominio} → **{ip}**"}
        except socket.gaierror:
            return {"respuesta": f"No pude resolver el dominio: {dominio}"}

    skill.register_action("resolver_dominio", "Resuelve un dominio a IP", _resolver_dominio,
        parameters={"dominio": {"type": "string", "description": "Ej: google.com"}})

    def _mi_ubicacion():
        """Obtiene ubicacion aproximada por IP."""
        ip = _get_public_ip()
        if not ip:
            return {"respuesta": "No pude determinar tu ubicacion."}
        try:
            url = f"https://ipapi.co/{ip}/json/"
            req = urllib.request.Request(url, headers={"User-Agent": "Nexus/1.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
            return {"respuesta": f"Ubicacion estimada:\n  IP: {data.get('ip', ip)}\n  Ciudad: {data.get('city', '?')}\n  Region: {data.get('region', '?')}\n  Pais: {data.get('country_name', '?')}\n  ISP: {data.get('org', '?')}"}
        except Exception as e:
            return {"respuesta": f"IP: {ip}. No pude obtener ubicacion: {e}"}

    skill.register_action("mi_ubicacion", "Muestra ubicacion geografica aproximada", _mi_ubicacion)

    return skill
