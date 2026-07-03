"""Gemini LLM adapter for ACU.

This module is intentionally fail-closed: it does not initialize or call Gemini
unless GEMINI_ENABLED is true and a Gemini API key is present in the runtime
environment. Tests can inject a fake model client to avoid real network calls.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from src.config.settings import agent_config
from src.llm.runtime_flags import is_gemini_runtime_enabled
from src.utils.logger import log


class GeminiClient:
    """Adapter with the same surface used by the ACU agent loop."""

    def __init__(self, model_client: Any = None):
        self.enabled = is_gemini_runtime_enabled()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        self.timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "1024"))
        self.api_key_configured = bool(os.getenv("GEMINI_API_KEY", "").strip())
        self._model_client = model_client

    def check_connection(self) -> bool:
        """Return readiness without exposing secrets or performing broad discovery."""
        return bool(self.enabled and self.api_key_configured and self._client_available())

    def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Optional[str]:
        """Generate a response through Gemini, or fail closed with None."""
        if not self.enabled:
            log.warning("Gemini adapter disabled by GEMINI_ENABLED")
            return None
        if not self.api_key_configured:
            log.warning("Gemini adapter unavailable: API key not configured")
            return None

        client = self._get_model_client()
        if client is None:
            return None

        prompt = self._build_prompt(system_prompt, user_message, conversation_history)
        generation_config = {
            "temperature": agent_config.temperature if temperature is None else temperature,
            "top_p": agent_config.top_p if top_p is None else top_p,
            "max_output_tokens": self.max_tokens,
        }

        try:
            response = client.generate_content(
                prompt,
                generation_config=generation_config,
                request_options={"timeout": self.timeout_seconds},
            )
        except TypeError:
            response = client.generate_content(prompt, generation_config=generation_config)
        except Exception as exc:
            log.warning(f"Gemini generation failed safely: {exc.__class__.__name__}")
            return None

        text = getattr(response, "text", None)
        if text:
            return str(text)

        try:
            return str(response.candidates[0].content.parts[0].text)
        except Exception:
            log.warning("Gemini response did not include text content")
            return None

    def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ):
        """Yield a single generated response chunk for compatibility."""
        response = self.generate_response(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=conversation_history,
            temperature=temperature,
            top_p=top_p,
        )
        if response:
            yield response

    def parse_tool_calls(self, response_text: Optional[str]) -> List[Dict[str, Any]]:
        """Parse tool calls with the same XML-tag convention used by OllamaClient."""
        if not response_text:
            return []

        tool_calls: List[Dict[str, Any]] = []
        for match in re.findall(r"<tool>(.*?)</tool>", response_text, re.DOTALL):
            try:
                tool_calls.append(json.loads(match.strip()))
            except json.JSONDecodeError:
                log.warning("Gemini adapter ignored invalid tool-call JSON")
        return tool_calls

    def _client_available(self) -> bool:
        return self._model_client is not None or self._sdk_available()

    def _sdk_available(self) -> bool:
        try:
            import google.generativeai  # noqa: F401

            return True
        except Exception:
            return False

    def _get_model_client(self):
        if self._model_client is not None:
            return self._model_client

        try:
            import google.generativeai as genai
        except Exception:
            log.warning("Gemini SDK not installed; adapter failed closed")
            return None

        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY", "").strip())
            self._model_client = genai.GenerativeModel(self.model)
            return self._model_client
        except Exception as exc:
            log.warning(f"Gemini adapter initialization failed safely: {exc.__class__.__name__}")
            return None

    def _build_prompt(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
    ) -> str:
        history = conversation_history or []
        history_text = "\n".join(
            f"{item.get('role', 'unknown')}: {item.get('content', '')}" for item in history[-6:]
        )
        return (
            "System:\n"
            f"{system_prompt}\n\n"
            "Recent conversation:\n"
            f"{history_text}\n\n"
            "User:\n"
            f"{user_message}"
        )
