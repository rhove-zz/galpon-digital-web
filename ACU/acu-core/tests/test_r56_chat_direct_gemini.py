"""R56 chat stabilization tests for direct read-only Gemini routing."""

from types import SimpleNamespace

from src.api.routes import chat as chat_routes
from src.api.schemas import ChatRequest


class FakeGeminiClient:
    enabled = True
    api_key_configured = True

    def generate_response(self, **kwargs):
        self.kwargs = kwargs
        return "respuesta sintetica"


class EmptyGeminiClient:
    enabled = True
    api_key_configured = True

    def generate_response(self, **kwargs):
        return None


def _frozen_read_only_config():
    return SimpleNamespace(
        is_secure_runtime=True,
        safe_mode=True,
        write_tools_enabled=False,
        external_tools_enabled=False,
        web_tools_enabled=False,
        filesystem_write_enabled=False,
        api_rest_enabled=False,
    )


def test_chat_uses_direct_read_only_gemini_when_actions_are_frozen(monkeypatch):
    monkeypatch.setattr(chat_routes, "system_config", _frozen_read_only_config())
    monkeypatch.setattr(chat_routes, "is_gemini_runtime_enabled", lambda: True)
    monkeypatch.setattr(chat_routes, "GeminiClient", FakeGeminiClient)

    payload = ChatRequest(
        message="consulta sintetica R56",
        domain="production",
        persona="default",
        session_id="r56-test",
    )

    assert chat_routes._should_use_direct_read_only_gemini() is True
    response = chat_routes._direct_read_only_gemini_response(payload)

    assert response is not None
    assert response.session_id == "r56-test"
    assert response.response == "respuesta sintetica"
    assert response.iterations == 1
    assert response.tool_calls == []


def test_chat_falls_back_when_direct_gemini_returns_empty(monkeypatch):
    monkeypatch.setattr(chat_routes, "system_config", _frozen_read_only_config())
    monkeypatch.setattr(chat_routes, "is_gemini_runtime_enabled", lambda: True)
    monkeypatch.setattr(chat_routes, "GeminiClient", EmptyGeminiClient)

    payload = ChatRequest(message="consulta sintetica R56", domain="production")

    direct_response = chat_routes._direct_read_only_gemini_response(payload)
    fallback_response = chat_routes._read_only_fallback_response(payload)

    assert direct_response is None
    assert fallback_response.iterations == 0
    assert fallback_response.tool_calls == []
