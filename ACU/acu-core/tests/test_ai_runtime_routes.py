from fastapi.testclient import TestClient

from src.api.app import create_app
from src.llm.runtime_flags import reset_gemini_runtime_override


def _client(monkeypatch):
    reset_gemini_runtime_override()
    monkeypatch.setenv("ACU_ENV", "staging")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("ACU_TOOLS_ENABLED", "false")
    monkeypatch.setenv("ACU_WRITE_TOOLS_ENABLED", "false")
    monkeypatch.setenv("ACU_WEB_TOOLS_ENABLED", "false")
    monkeypatch.setenv("ACU_FILESYSTEM_WRITE_ENABLED", "false")
    monkeypatch.setenv("ACU_EXTERNAL_TOOLS_ENABLED", "false")
    return TestClient(
        create_app(
            api_key="admin-secret",
            api_auth_required=True,
            rate_limit_requests=0,
        )
    )


def test_gemini_runtime_toggle_requires_admin(monkeypatch):
    client = _client(monkeypatch)

    response = client.post("/system/ai-runtime/gemini/enable", json={"ttl_seconds": 30})

    assert response.status_code == 401


def test_gemini_runtime_toggle_enable_disable_with_ttl(monkeypatch):
    client = _client(monkeypatch)
    headers = {"X-ACU-API-Key": "admin-secret"}

    enabled = client.post(
        "/system/ai-runtime/gemini/enable",
        json={"ttl_seconds": 30},
        headers=headers,
    )
    status = client.get("/system/ai-runtime/gemini", headers=headers)
    disabled = client.post("/system/ai-runtime/gemini/disable", headers=headers)

    assert enabled.status_code == 200
    assert enabled.json()["gemini"]["effective_enabled"] is True
    assert enabled.json()["gemini"]["ttl_remaining_seconds"] <= 30
    assert enabled.json()["safety"]["tools_enabled"] is False
    assert status.json()["secret_values"] == "not_returned"
    assert disabled.json()["gemini"]["effective_enabled"] is False

    reset_gemini_runtime_override()


def test_gemini_runtime_toggle_rejects_when_tools_enabled(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setenv("ACU_TOOLS_ENABLED", "true")

    response = client.post(
        "/system/ai-runtime/gemini/enable",
        json={"ttl_seconds": 30},
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["safety"]["tools_enabled"] is True

    reset_gemini_runtime_override()


def test_gemini_runtime_toggle_rejects_production(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setenv("ACU_ENV", "production")

    response = client.post(
        "/system/ai-runtime/gemini/enable",
        json={"ttl_seconds": 30},
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    assert response.status_code == 403

    reset_gemini_runtime_override()
