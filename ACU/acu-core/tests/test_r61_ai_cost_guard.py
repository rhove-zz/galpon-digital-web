"""R61 tests for fail-closed AI cost guard."""

import json
from types import SimpleNamespace

from src.api.routes import chat as chat_routes
from src.api.schemas import ChatRequest
from src.llm import cost_guard


class FakeGeminiClient:
    enabled = True
    api_key_configured = True
    max_tokens = 128

    def generate_response(self, **kwargs):
        return "respuesta sintetica"


class ExplodingGeminiClient:
    enabled = True
    api_key_configured = True
    max_tokens = 128

    def generate_response(self, **kwargs):
        raise AssertionError("Gemini must not be called when cost guard blocks")


def _guard_config(tmp_path, **overrides):
    defaults = {
        "ai_cost_guard_enabled": True,
        "ai_cost_guard_mode": "block",
        "ai_daily_request_limit": 0,
        "ai_input_token_limit": 0,
        "ai_output_token_limit": 0,
        "ai_daily_cost_limit_usd": 0.0,
        "ai_estimated_cost_per_1k_tokens_usd": 0.0,
        "ai_cost_guard_state_file": str(tmp_path / "guard.json"),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _frozen_read_only_config(**overrides):
    defaults = {
        "is_secure_runtime": True,
        "safe_mode": True,
        "write_tools_enabled": False,
        "external_tools_enabled": False,
        "web_tools_enabled": False,
        "filesystem_write_enabled": False,
        "api_rest_enabled": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_cost_guard_blocks_daily_request_limit(monkeypatch, tmp_path):
    state_file = tmp_path / "guard.json"
    state_file.write_text(
        json.dumps(
            {
                "date_utc": cost_guard._today_key(),
                "requests": 1,
                "estimated_cost_usd": 0.0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cost_guard,
        "system_config",
        _guard_config(tmp_path, ai_daily_request_limit=1),
    )

    decision = cost_guard.evaluate_ai_request("consulta sintetica", 128)

    assert decision.allowed is False
    assert decision.reason == "daily_request_limit_exceeded"


def test_cost_guard_records_allowed_request(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cost_guard,
        "system_config",
        _guard_config(
            tmp_path,
            ai_daily_request_limit=5,
            ai_daily_cost_limit_usd=1.0,
            ai_estimated_cost_per_1k_tokens_usd=0.01,
        ),
    )

    decision = cost_guard.evaluate_ai_request("consulta sintetica", 128)
    cost_guard.record_ai_request(decision)

    state = json.loads((tmp_path / "guard.json").read_text(encoding="utf-8"))
    assert decision.allowed is True
    assert state["requests"] == 1
    assert state["estimated_cost_usd"] > 0


def test_direct_chat_returns_guard_response_without_calling_gemini(monkeypatch):
    monkeypatch.setattr(chat_routes, "system_config", _frozen_read_only_config())
    monkeypatch.setattr(chat_routes, "is_gemini_runtime_enabled", lambda: True)
    monkeypatch.setattr(chat_routes, "GeminiClient", ExplodingGeminiClient)
    monkeypatch.setattr(
        chat_routes,
        "evaluate_ai_request",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=False),
    )
    monkeypatch.setattr(
        chat_routes,
        "record_ai_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("blocked requests must not be recorded")
        ),
    )

    response = chat_routes._direct_read_only_gemini_response(
        ChatRequest(message="consulta sintetica", domain="production")
    )

    assert response is not None
    assert response.iterations == 0
    assert response.tool_calls == []
    assert response.session_id.startswith("guard-blocked:")


def test_direct_chat_records_allowed_request(monkeypatch):
    recorded = {"count": 0}
    monkeypatch.setattr(chat_routes, "system_config", _frozen_read_only_config())
    monkeypatch.setattr(chat_routes, "is_gemini_runtime_enabled", lambda: True)
    monkeypatch.setattr(chat_routes, "GeminiClient", FakeGeminiClient)
    monkeypatch.setattr(
        chat_routes,
        "evaluate_ai_request",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, enabled=True),
    )
    monkeypatch.setattr(
        chat_routes,
        "record_ai_request",
        lambda *_args, **_kwargs: recorded.__setitem__("count", recorded["count"] + 1),
    )

    response = chat_routes._direct_read_only_gemini_response(
        ChatRequest(message="consulta sintetica", domain="production")
    )

    assert response is not None
    assert response.iterations == 1
    assert response.tool_calls == []
    assert recorded["count"] == 1
