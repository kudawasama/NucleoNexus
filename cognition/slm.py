"""
Núcleo Nexus — Backend SLM Local
=================================
Puente para conectar modelos de lenguaje pequeños (SLM) locales.
Soporta:
- llama.cpp (modelos GGUF) — ejecución local, CPU/GPU
- Ollama — servidor local de modelos
- API compatible OpenAI — para cualquier backend

Cuando se activa, reemplaza al motor simbólico para la generación
de respuestas, pero el motor de estado y las skills siguen siendo
los que ejecutan la lógica.
"""

import logging
import json
import subprocess
import time
import os
from typing import Optional

logger = logging.getLogger("nexus.cognition.slm")


class SLMBackend:
    """Backend para modelos de lenguaje locales (SLM).
    
    Modos de conexión:
    - "llamacpp": Ejecuta un binario de llama.cpp directamente
    - "ollama": Se conecta a un servidor Ollama local
    - "openai": API compatible OpenAI (puede apuntar a cualquier endpoint)
    """

    def __init__(self, config: dict):
        self.config = config
        self.mode = config.get("backend", None)
        self.model_path = config.get("model_path", None)
        self.model_name = config.get("model_name", "phi-2")
        self.max_tokens = config.get("max_tokens", 512)
        self.temperature = config.get("temperature", 0.7)
        self.loaded = False
        self._process = None
        self._api_key = config.get("api_key")
        # Fallback: leer de variables de entorno
        if not self._api_key:
            self._api_key = os.environ.get("OPENCODE_GO_API_KEY")
        # Fallback 2: leer del archivo master env (configurable via env var)
        if not self._api_key:
            master_path = os.environ.get(
                "NEXUS_MASTER_ENV",
                "H:/Mi unidad/kudawa-master.env"
            )
            if os.path.exists(master_path):
                try:
                    with open(master_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("OPENCODE_GO_API_KEY=") and "***" not in line:
                                self._api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
                except Exception as e:
                    logger.warning(f"No se pudo leer master env: {e}")
        logger.info(f"SLMBackend creado (modo: {self.mode})")

    def load(self) -> bool:
        """Carga el modelo SLM. Cada modo tiene su propia inicialización."""
        if self.mode == "llamacpp":
            return self._load_llamacpp()
        elif self.mode == "ollama":
            return self._check_ollama()
        elif self.mode == "openai":
            return self._check_openai()
        else:
            logger.warning(f"Modo SLM desconocido: {self.mode}")
            return False

    def _load_llamacpp(self) -> bool:
        """Carga un modelo GGUF via llama.cpp."""
        if not self.model_path:
            logger.error("model_path requerido para modo llamacpp")
            return False
        try:
            # Intenta iniciar llama.cpp server
            self._process = subprocess.Popen(
                ["llama-server", "-m", self.model_path,
                 "--port", "8713", "--n-gpu-layers", "0",
                 "--ctx-size", "2048"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)  # Espera a que inicie
            self.loaded = True
            logger.info(f"llama.cpp iniciado con modelo: {self.model_path}")
            return True
        except FileNotFoundError:
            logger.warning("llama-server no encontrado. Instálalo o usa modo symbolic.")
            return False
        except Exception as e:
            logger.error(f"Error iniciando llama.cpp: {e}")
            return False

    def _check_ollama(self) -> bool:
        """Verifica conexión con servidor Ollama."""
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                models = r.json().get("models", [])
                model_names = [m["name"] for m in models]
                if self.model_name not in model_names:
                    logger.warning(f"Modelo '{self.model_name}' no encontrado en Ollama. "
                                   f"Disponibles: {model_names[:5]}")
                self.loaded = True
                logger.info(f"Ollama conectado. Modelo: {self.model_name}")
                return True
        except ImportError:
            logger.warning("requests no instalado. Usa: pip install requests")
        except Exception as e:
            logger.warning(f"No se pudo conectar a Ollama: {e}")
        return False

    def _check_openai(self) -> bool:
        """Verifica conexión con API compatible OpenAI."""
        try:
            import requests
            base_url = self.config.get("api_base", "http://localhost:8000/v1")
            # Usar la misma key que ya se obtuvo en __init__
            api_key = self._api_key
            if not api_key:
                logger.warning("No API key para OpenAI. Configura OPENCODE_GO_API_KEY")
                return False
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Nexus/1.0",
            }
            r = requests.get(f"{base_url}/models", headers=headers, timeout=5)
            if r.status_code == 200:
                self.loaded = True
                logger.info(f"OpenAI compatible conectada: {base_url}")
                return True
        except Exception as e:
            logger.warning(f"No se pudo conectar a API OpenAI: {e}")
        return False

    def generate(self, prompt: str, system_prompt: str = None,
                 structured: bool = False) -> Optional[str]:
        """Genera una respuesta usando el SLM cargado.
        
        Args:
            prompt: Texto del usuario
            system_prompt: Contexto del sistema (opcional)
            structured: Si True, fuerza salida JSON (Ollama format mode)
            
        Returns:
            Dict con 'response', 'model', 'tokens_prompt', 'tokens_generated',
            'duration_ms', o None si falla
        """
        if not self.loaded:
            logger.warning("SLM no cargado. Usa load() primero.")
            return None

        if structured and self.mode == "ollama":
            return self._generate_ollama_structured(prompt, system_prompt)

        if self.mode == "ollama":
            return self._generate_ollama(prompt, system_prompt)
        elif self.mode == "openai":
            result = self._generate_openai(prompt, system_prompt)
            if result and structured:
                # Envolver en dict para mantener consistencia con structured mode
                return {"response": result, "model": self.model_name}
            return result
        elif self.mode == "llamacpp":
            return self._generate_llamacpp(prompt, system_prompt)
        return None

    def _generate_ollama_structured(self, prompt: str, system_prompt: str = None) -> Optional[dict]:
        """Genera respuesta via Ollama con formato JSON forzado y metadata."""
        try:
            import requests
            # Sistema + instrucción de formato JSON
            json_instruction = (
                "Responde SOLO con JSON valido. El campo 'accion' determina "
                "que hace Nexus con tu respuesta:\n"
                '- "responder": solo responde al usuario (mas comun)\n'
                '- "buscar_memoria": busca un tema en la base de conocimiento\n'
                '- "calcular": evalua una expresion matematica\n'
                '- "usar_herramienta": ejecuta una herramienta del sistema '
                "(web_search, read_file, write_file, search_files, "
                "run_command, python_eval)\n\n"
                "Esquema:\n"
                '{"respuesta": "texto al usuario", '
                '"accion": "responder|buscar_memoria|calcular|usar_herramienta", '
                '"tema": "tema a buscar (si accion=buscar_memoria)", '
                '"expresion": "2+2 (si accion=calcular)", '
                '"herramienta": "web_search (si accion=usar_herramienta)", '
                '"parametros": {"query": "termino busqueda"}}'
            )
            full_system = f"{system_prompt}\n\n{json_instruction}" if system_prompt else json_instruction

            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": full_system,
                "format": "json",
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                }
            }

            r = requests.post("http://localhost:11434/api/generate",
                            json=payload, timeout=45)
            if r.status_code == 200:
                data = r.json()
                raw = data.get("response", "")
                # Verificar que es JSON válido
                import json as _json
                try:
                    _json.loads(raw)
                    return {
                        "response": raw,
                        "model": data.get("model", self.model_name),
                        "tokens_prompt": data.get("prompt_eval_count", 0),
                        "tokens_generated": data.get("eval_count", 0),
                        "duration_ms": round(data.get("eval_duration", 0) / 1_000_000, 1),
                        "total_duration_ms": round(data.get("total_duration", 0) / 1_000_000, 1),
                    }
                except _json.JSONDecodeError:
                    logger.warning(f"JSON inválido del SLM: {raw[:60]}")
                    return None
            return None
        except Exception as e:
            logger.error(f"Error en generación Ollama estructurada: {e}")
            return None

    def _generate_ollama(self, prompt: str, system_prompt: str = None) -> Optional[dict]:
        """Genera respuesta via Ollama con metadata de tokens."""
        try:
            import requests
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                }
            }
            if system_prompt:
                payload["system"] = system_prompt

            r = requests.post("http://localhost:11434/api/generate",
                            json=payload, timeout=30)
            if r.status_code == 200:
                data = r.json()
                response = data.get("response", "")
                return {
                    "response": response,
                    "model": data.get("model", self.model_name),
                    "tokens_prompt": data.get("prompt_eval_count", 0),
                    "tokens_generated": data.get("eval_count", 0),
                    "duration_ms": round(data.get("eval_duration", 0) / 1_000_000, 1),
                    "total_duration_ms": round(data.get("total_duration", 0) / 1_000_000, 1),
                }
        except Exception as e:
            logger.error(f"Error en generación Ollama: {e}")
        return None

    def _generate_openai(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """Genera respuesta via API compatible OpenAI."""
        try:
            import requests
            base_url = self.config.get("api_base", "http://localhost:8000/v1")
            chat_url = f"{base_url}/chat/completions"
            api_key = self._api_key
            if not api_key:
                logger.error("No API key configurada para OpenAI")
                return None

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Nexus/1.0",
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            r = requests.post(chat_url, headers=headers, json=payload, timeout=45)
            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"].get("content", "")
                # Si el modelo es de razonamiento y no dio contenido,
                # aumentar tokens o devolver lo que haya
                if not content.strip():
                    reasoning = data["choices"][0]["message"].get("reasoning_content", "")
                    if reasoning:
                        logger.info("Modelo de razonamiento, sin contenido visible")
                return content or None
            else:
                logger.error(f"OpenAI API error {r.status_code}: {r.text[:100]}")
                return None
        except ImportError:
            logger.warning("requests no instalado. Usa: pip install requests")
            return None
        except Exception as e:
            logger.error(f"Error en generación OpenAI: {e}")
            return None

    def _generate_llamacpp(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """Genera respuesta via llama.cpp server."""
        try:
            import requests
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            r = requests.post(
                "http://localhost:8713/v1/completions",
                json={
                    "prompt": full_prompt,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                },
                timeout=30
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["text"]
        except Exception as e:
            logger.error(f"Error en generación llama.cpp: {e}")
        return None

    def unload(self):
        """Descarga el SLM."""
        if self._process:
            self._process.terminate()
            self._process = None
        self.loaded = False
        logger.info("SLM descargado")

    def get_info(self) -> dict:
        return {
            "loaded": self.loaded,
            "mode": self.mode,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
