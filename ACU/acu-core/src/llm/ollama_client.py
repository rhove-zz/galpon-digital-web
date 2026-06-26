"""
Ollama LLM Integration.
Handles communication with local Ollama instance for reasoning.
"""

import requests
import json
import time
from typing import Optional, List, Dict, Any
from src.config.settings import ollama_config, agent_config
from src.utils.logger import log


class OllamaClient:
    """
    Client for interacting with Ollama API.
    - Envío de prompts al modelo local
    - Parsing de respuestas estructuradas
    - Manejo de tool calls en formato JSON
    """

    def __init__(self):
        """Initialize Ollama client."""
        self.base_url = ollama_config.base_url
        self.model = ollama_config.model
        self.timeout = ollama_config.timeout

        # Circuit Breaker state
        self.failures = 0
        self.max_failures = 3
        self.circuit_open = False
        self.last_failure_time = 0
        self.recovery_timeout = 30  # Segundos antes de reintentar

    def _check_circuit(self) -> bool:
        if self.circuit_open:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                log.info(
                    "Circuit Breaker en estado half-open. Probando conexión a Ollama..."
                )
                self.circuit_open = False
                return True
            return False
        return True

    def _record_success(self):
        if self.failures > 0 or self.circuit_open:
            log.info("Conexión con Ollama recuperada. Circuit Breaker cerrado.")
            self.failures = 0
            self.circuit_open = False

    def _record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.max_failures:
            if not self.circuit_open:
                log.error(
                    f"Circuit Breaker ABIERTO. Ollama falló {self.failures} veces seguidas."
                )
            self.circuit_open = True

    def check_connection(self) -> bool:
        """Verify Ollama is running and accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                log.info(f"✓ Ollama disponible en {self.base_url}")
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models]
                log.debug(f"Modelos disponibles: {model_names}")
                return True
            else:
                log.error(f"✗ Ollama retornó código {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            log.error(f"✗ No se puede conectar a Ollama: {e}")
            return False

    def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Optional[str]:
        """
        Generate response from LLM with given prompts.

        Args:
            system_prompt: System instruction/context
            user_message: User query
            conversation_history: Previous messages for context
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter

        Returns:
            Generated text or None if request fails
        """
        temperature = agent_config.temperature if temperature is None else temperature
        top_p = agent_config.top_p if top_p is None else top_p

        if not self._check_circuit():
            log.warning("Petición rechazada por Circuit Breaker (Ollama caído)")
            return None

        try:
            # Build messages
            messages = [{"role": "system", "content": system_prompt}]

            if conversation_history:
                messages.extend(conversation_history)

            messages.append({"role": "user", "content": user_message})

            # Make request to Ollama
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "top_p": top_p,
                    },
                },
                timeout=self.timeout,
            )

            if response.status_code == 200:
                self._record_success()
                result = response.json()
                content = result.get("message", {}).get("content", "")
                log.debug(f"✓ Respuesta generada ({len(content)} chars)")
                return content
            else:
                self._record_failure()
                log.error(f"✗ Error de Ollama: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            self._record_failure()
            log.error(f"✗ Timeout en Ollama (>{self.timeout}s)")
            return None
        except Exception as e:
            self._record_failure()
            log.error(f"✗ Error en generación: {e}")
            return None

    def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ):
        """
        Generate streaming response from LLM yielding tokens.
        """
        temperature = agent_config.temperature if temperature is None else temperature
        top_p = agent_config.top_p if top_p is None else top_p

        if not self._check_circuit():
            log.warning("Petición rechazada por Circuit Breaker (Ollama caído)")
            return

        try:
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})

            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "top_p": top_p,
                    },
                },
                timeout=self.timeout,
                stream=True,
            )

            if response.status_code == 200:
                self._record_success()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
            else:
                self._record_failure()
                log.error(f"✗ Error de Ollama en stream: {response.status_code}")
        except Exception as e:
            self._record_failure()
            log.error(f"✗ Error en generación stream: {e}")

    def parse_tool_calls(self, response_text: Optional[str]) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response.
        Expects JSON blocks like: <tool>{"tool": "...", "parameters": {...}}</tool>

        Args:
            response_text: Raw response from LLM

        Returns:
            List of parsed tool calls
        """
        tool_calls: List[Dict[str, Any]] = []

        if not response_text:
            return tool_calls

        try:
            # Look for JSON blocks between <tool> tags
            import re

            pattern = r"<tool>(.*?)</tool>"
            matches = re.findall(pattern, response_text, re.DOTALL)

            for match in matches:
                try:
                    tool_json = json.loads(match.strip())
                    tool_calls.append(tool_json)
                except json.JSONDecodeError as e:
                    log.warning(f"No se pudo parsear JSON: {e}")

            log.debug(f"Tool calls parseados: {len(tool_calls)}")
            return tool_calls

        except Exception as e:
            log.error(f"Error al parsear tool calls: {e}")
            return []

    def list_available_models(self) -> List[str]:
        """Get list of available models in Ollama."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m.get("name") for m in models]
            return []
        except Exception as e:
            log.error(f"Error listando modelos: {e}")
            return []


# Singleton instance
_ollama_client = None


def get_ollama_client() -> OllamaClient:
    """Get or create singleton Ollama client."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
