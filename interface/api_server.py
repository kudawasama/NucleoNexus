"""
Nucleo Nexus -- Servidor API FastAPI
=====================================
Implementación del servidor API HTTP REST y WebSockets para interacciones remotas.
"""

import logging
import os
import time
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from main import NexusCore
import config

logger = logging.getLogger("nexus.api")

app = FastAPI(
    title="Nucleo Nexus API",
    description="API HTTP REST de NucleoNexus con autenticación Bearer Token",
    version=config.SYSTEM.get("version", "1.0.0")
)

security = HTTPBearer()
nexus_core: Optional[NexusCore] = None


def get_nexus() -> NexusCore:
    """Devuelve la instancia singleton de NexusCore."""
    global nexus_core
    if nexus_core is None:
        nexus_core = NexusCore()
    return nexus_core


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Valida la cabecera de autenticación Bearer Token."""
    token = credentials.credentials
    # Leer el token esperado de la variable de entorno o un valor por defecto seguro
    expected_token = os.environ.get("NEXUS_API_TOKEN", "nexus_secret_key_2026")
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido o expirado",
        )
    return token


class ChatRequest(BaseModel):
    message: str


class FactRequest(BaseModel):
    fact: str
    category: str = "general"


@app.get("/v1/status", dependencies=[Depends(verify_token)])
def get_status(core: NexusCore = Depends(get_nexus)):
    """Retorna las estadísticas del sistema."""
    from engine.state import StateEngine
    from config import DATA_DIR
    state = StateEngine(str(DATA_DIR / "state"))
    return state.get_snapshot()


@app.post("/v1/chat", dependencies=[Depends(verify_token)])
def chat(request: ChatRequest, core: NexusCore = Depends(get_nexus)):
    """Procesa un mensaje y retorna la respuesta del agente."""
    try:
        response, metadata = core.process(request.message)
        return {"response": response, "metadata": metadata}
    except Exception as e:
        logger.error(f"Error procesando chat en la API: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/memory", dependencies=[Depends(verify_token)])
def learn_fact(request: FactRequest, core: NexusCore = Depends(get_nexus)):
    """Aprende un hecho en la memoria semántica de Nexus."""
    try:
        success = core.memory.learn_fact(request.fact, category=request.category, confidence=0.8, source="api")
        return {"success": success, "message": "Hecho registrado de manera exitosa."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
