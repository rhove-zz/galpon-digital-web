import os
from types import SimpleNamespace

from src.llm.gemini_client import GeminiClient
from src.llm.provider import get_llm_client
from src.llm.ollama_client import OllamaClient
from src.llm.runtime_flags import (
    get_gemini_runtime_status,
    reset_gemini_runtime_override,
    set_gemini_runtime_override,
)


class FakeGeminiModel:
    def __init__(self, text="respuesta gemini"):
        self.text = text
        self.calls = []

    def generate_content(self, prompt, generation_config=None, request_options=None):
        self.calls.append(
            {
                "prompt": prompt,
                "generation_config": generation_config,
                "request_options": request_options,
            }
        )
        return SimpleNamespace(text=self.text)


class FailingGeminiModel:
    def generate_content(self, *args, **kwargs):
        raise RuntimeError("network disabled")


def test_gemini_client_fails_closed_when_disabled(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    model = FakeGeminiModel()

    client = GeminiClient(model_client=model)

    assert client.check_connection() is False
    assert client.generate_response("system", "consulta") is None
    assert model.calls == []


def test_gemini_client_uses_injected_model_without_printing_secret(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    model = FakeGeminiModel("respuesta controlada")

    client = GeminiClient(model_client=model)
    response = client.generate_response(
        "system",
        "consulta sintetica",
        conversation_history=[{"role": "user", "content": "hola"}],
    )

    assert response == "respuesta controlada"
    assert len(model.calls) == 1
    assert "test-key-not-real" not in model.calls[0]["prompt"]
    assert model.calls[0]["request_options"]["timeout"] > 0


def test_gemini_client_falls_back_on_generation_error(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")

    client = GeminiClient(model_client=FailingGeminiModel())

    assert client.generate_response("system", "consulta") is None


def test_gemini_client_parses_tool_calls(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    client = GeminiClient(model_client=FakeGeminiModel())

    calls = client.parse_tool_calls('<tool>{"tool": "sql_read", "parameters": {}}</tool>')

    assert calls == [{"tool": "sql_read", "parameters": {}}]


def test_provider_defaults_to_ollama_when_gemini_off(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.delenv("ACU_LLM_PROVIDER", raising=False)

    assert isinstance(get_llm_client(), OllamaClient)


def test_provider_selects_gemini_when_enabled(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ACU_LLM_PROVIDER", "gemini")

    assert isinstance(get_llm_client(), GeminiClient)


def test_provider_selects_gemini_for_authorized_runtime_override(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ACU_LLM_PROVIDER", "gemini")

    set_gemini_runtime_override(enabled=True, ttl_seconds=60, updated_by="test")

    assert isinstance(get_llm_client(), GeminiClient)

    reset_gemini_runtime_override()


def test_runtime_override_expires_without_redeploy(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("GEMINI_ENABLED", "false")

    set_gemini_runtime_override(enabled=True, ttl_seconds=10, now=1000)

    assert get_gemini_runtime_status(now=1005)["effective_enabled"] is True
    assert get_gemini_runtime_status(now=1011)["effective_enabled"] is False
