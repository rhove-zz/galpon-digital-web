import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.routes.admin_ai import SYNTHETIC_GEMINI_SMOKE_PROMPT
from src.llm.runtime_flags import get_gemini_runtime_status, reset_gemini_runtime_override


class FakeGeminiModel:
    def __init__(self, text="smoke gemini controlado ok"):
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
        raise RuntimeError("synthetic failure")


class SlowGeminiModel:
    def generate_content(self, *args, **kwargs):
        time.sleep(11)
        return SimpleNamespace(text="late")


def _client(monkeypatch, model=None):
    reset_gemini_runtime_override()
    monkeypatch.setenv("ACU_ENV", "staging")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ACU_TOOLS_ENABLED", "false")
    monkeypatch.setenv("ACU_WRITE_TOOLS_ENABLED", "false")
    monkeypatch.setenv("ACU_WEB_TOOLS_ENABLED", "false")
    monkeypatch.setenv("ACU_FILESYSTEM_WRITE_ENABLED", "false")
    monkeypatch.setenv("ACU_EXTERNAL_TOOLS_ENABLED", "false")
    app = create_app(
        api_key="admin-secret",
        api_auth_required=True,
        rate_limit_requests=0,
    )
    if model is not None:
        app.state.gemini_smoke_model_client = model
    return TestClient(app)


def test_direct_smoke_requires_admin_auth(monkeypatch):
    client = _client(monkeypatch, FakeGeminiModel())

    response = client.post("/admin/ai/gemini/smoke")

    assert response.status_code == 401


def test_direct_smoke_uses_synthetic_prompt_and_bypasses_agent(monkeypatch):
    model = FakeGeminiModel()
    client = _client(monkeypatch, model)

    response = client.post(
        "/admin/ai/gemini/smoke",
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["direct_gemini_adapter"] is True
    assert body["bypassed_react_agent"] is True
    assert body["bypassed_chat_session_flow"] is True
    assert body["bypassed_tools"] is True
    assert body["bypassed_writes"] is True
    assert body["tools_enabled"] is False
    assert body["acu_writes_enabled"] is False
    assert body["secret_values"] == "not_returned"
    assert SYNTHETIC_GEMINI_SMOKE_PROMPT in model.calls[0]["prompt"]
    assert "test-key-not-real" not in model.calls[0]["prompt"]
    assert model.calls[0]["request_options"]["timeout"] == 8
    assert get_gemini_runtime_status()["effective_enabled"] is False

    reset_gemini_runtime_override()


def test_direct_smoke_sanitizes_gemini_exception_and_disables_toggle(monkeypatch):
    client = _client(monkeypatch, FailingGeminiModel())

    response = client.post(
        "/admin/ai/gemini/smoke",
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["error_code"] == "GEMINI_EMPTY_OR_FAILED_RESPONSE"
    assert body["secret_values"] == "not_returned"
    assert get_gemini_runtime_status()["effective_enabled"] is False

    reset_gemini_runtime_override()


def test_direct_smoke_timeout_is_controlled_and_disables_toggle(monkeypatch):
    client = _client(monkeypatch, SlowGeminiModel())

    response = client.post(
        "/admin/ai/gemini/smoke",
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["error_code"] == "GEMINI_TIMEOUT"
    assert get_gemini_runtime_status()["effective_enabled"] is False

    reset_gemini_runtime_override()


def test_direct_smoke_rejects_when_tools_enabled(monkeypatch):
    client = _client(monkeypatch, FakeGeminiModel())
    monkeypatch.setenv("ACU_TOOLS_ENABLED", "true")

    response = client.post(
        "/admin/ai/gemini/smoke",
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["safety"]["tools_enabled"] is True
    assert get_gemini_runtime_status()["effective_enabled"] is False

    reset_gemini_runtime_override()
