"""LLM provider selection for ACU."""

import os

from src.llm.gemini_client import GeminiClient
from src.llm.ollama_client import OllamaClient


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_llm_client():
    """Return the configured LLM client.

    Defaults to Ollama/fallback behavior. Gemini is selected only when
    GEMINI_ENABLED is true and ACU_LLM_PROVIDER is empty or explicitly gemini.
    """
    provider = os.getenv("ACU_LLM_PROVIDER", "").strip().lower()
    if _enabled("GEMINI_ENABLED") and provider in {"", "gemini"}:
        return GeminiClient()
    return OllamaClient()

