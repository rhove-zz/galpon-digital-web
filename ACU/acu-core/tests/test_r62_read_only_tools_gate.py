"""R62 tests for minimal read-only tools enablement gate."""

from types import SimpleNamespace

from src.api.routes import chat as chat_routes
from src.llm import gemini_client
from src.llm.gemini_client import GeminiClient
from src.tools import tools_manager
from src.tools.tools_manager import ToolsManager
from src.utils.schemas import ToolType


class ExplodingGeminiModel:
    def generate_content(self, *_args, **_kwargs):
        raise AssertionError("Gemini must not be called when guard blocks")


def _chat_config(**overrides):
    defaults = {
        "is_secure_runtime": True,
        "safe_mode": True,
        "tools_enabled": False,
        "read_only_tools_enabled": False,
        "write_tools_enabled": False,
        "external_tools_enabled": False,
        "web_tools_enabled": False,
        "filesystem_write_enabled": False,
        "api_rest_enabled": False,
        "allowed_tools": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _tools_config(**overrides):
    defaults = {
        "tools_enabled": True,
        "read_only_tools_enabled": True,
        "write_tools_enabled": False,
        "external_tools_enabled": False,
        "python_sandbox_enabled": False,
        "filesystem_write_enabled": False,
        "api_rest_enabled": False,
        "web_tools_enabled": False,
        "blocked_tools": "",
        "allowed_tools": "buscar_contexto_braincore",
        "safe_mode": True,
        "audit_full_payloads": False,
        "audit_redact_secrets": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_direct_bypass_disabled_for_exact_minimal_read_only_tool_allowlist(monkeypatch):
    monkeypatch.setattr(
        chat_routes,
        "system_config",
        _chat_config(
            tools_enabled=True,
            read_only_tools_enabled=True,
            allowed_tools="buscar_contexto_braincore",
        ),
    )
    monkeypatch.setattr(chat_routes, "is_gemini_runtime_enabled", lambda: True)

    assert chat_routes._minimal_read_only_tools_runtime_enabled() is True
    assert chat_routes._should_use_direct_read_only_gemini() is False


def test_direct_bypass_stays_enabled_without_minimal_read_only_tool_mode(monkeypatch):
    monkeypatch.setattr(chat_routes, "system_config", _chat_config())
    monkeypatch.setattr(chat_routes, "is_gemini_runtime_enabled", lambda: True)

    assert chat_routes._minimal_read_only_tools_runtime_enabled() is False
    assert chat_routes._should_use_direct_read_only_gemini() is True


def test_extra_allowlisted_tool_does_not_enter_r62_minimal_mode(monkeypatch):
    monkeypatch.setattr(
        chat_routes,
        "system_config",
        _chat_config(
            tools_enabled=True,
            read_only_tools_enabled=True,
            allowed_tools="buscar_contexto_braincore,ejecutar_sql_lectura",
        ),
    )
    monkeypatch.setattr(chat_routes, "is_gemini_runtime_enabled", lambda: True)

    assert chat_routes._minimal_read_only_tools_runtime_enabled() is False
    assert chat_routes._should_use_direct_read_only_gemini() is True


def test_tools_policy_allows_only_braincore_read_only(monkeypatch):
    monkeypatch.setattr(tools_manager, "system_config", _tools_config())
    manager = object.__new__(ToolsManager)

    assert manager._tool_policy_block_reason(ToolType.BRAINCORE_SEARCH) is None
    assert (
        manager._tool_policy_block_reason(ToolType.SQL_READ)
        == "Herramienta no incluida en ACU_ALLOWED_TOOLS"
    )
    assert (
        manager._tool_policy_block_reason(ToolType.REGISTER_LESSON)
        == "Herramienta write bloqueada por ACU_WRITE_TOOLS_ENABLED"
    )


def test_gemini_client_cost_guard_blocks_react_model_call(monkeypatch):
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "defined-for-test")
    monkeypatch.setattr(
        gemini_client,
        "evaluate_ai_request",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=False),
    )
    monkeypatch.setattr(
        gemini_client,
        "record_ai_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("blocked requests must not be recorded")
        ),
    )

    client = GeminiClient(model_client=ExplodingGeminiModel())

    assert (
        client.generate_response(
            system_prompt="system",
            user_message="consulta sintetica",
            conversation_history=[],
        )
        is None
    )
