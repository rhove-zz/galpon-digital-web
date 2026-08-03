"""R62 tests for minimal read-only tools enablement gate."""

from types import SimpleNamespace

from src.api.routes import chat as chat_routes
from src.api.schemas import ChatRequest
from src.agent import agent_loop
from src.agent.agent_loop import ACUAgent
from src.llm import gemini_client
from src.llm.gemini_client import GeminiClient
from src.tools import tools_manager
from src.tools.tools_manager import ToolsManager
from src.utils.schemas import ToolCall
from src.utils.schemas import ToolType


class ExplodingGeminiModel:
    def generate_content(self, *_args, **_kwargs):
        raise AssertionError("Gemini must not be called when guard blocks")


class DirectBrainCoreGeminiClient:
    enabled = True
    api_key_configured = True
    max_tokens = 128

    def __init__(self):
        self.kwargs = None

    def generate_response(self, **kwargs):
        self.kwargs = kwargs
        return "respuesta con contexto braincore"


class DirectBrainCoreToolManager:
    def __init__(self):
        self.calls = []

    async def execute_tool(self, tool_call, **kwargs):
        self.calls.append((tool_call, kwargs))
        return SimpleNamespace(
            tool=ToolType.BRAINCORE_SEARCH,
            success=True,
            result=[
                {
                    "title": "Contexto sintetico",
                    "content": "Informacion operacional sintetica sobre ACU.",
                }
            ],
            error=None,
            execution_time_ms=1.0,
        )


class ExplodingDirectBrainCoreToolManager:
    async def execute_tool(self, *_args, **_kwargs):
        raise RuntimeError("braincore unavailable")


class SlowDirectBrainCoreToolManager:
    async def execute_tool(self, *_args, **_kwargs):
        import asyncio

        await asyncio.sleep(0.2)
        return SimpleNamespace(
            tool=ToolType.BRAINCORE_SEARCH,
            success=True,
            result=[],
            error=None,
            execution_time_ms=200.0,
        )


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
        "production_read_only": False,
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


def test_tools_manager_uses_read_only_braincore_and_skips_audit_in_production_read_only(monkeypatch):
    monkeypatch.setattr(
        tools_manager,
        "system_config",
        _tools_config(production_read_only=True),
    )
    manager = object.__new__(ToolsManager)
    manager.write_connector = SimpleNamespace(
        log_tool_execution=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("write audit must be skipped in production read-only")
        )
    )

    manager._audit_tool_execution(
        tool_call=ToolCall(
            tool=ToolType.BRAINCORE_SEARCH,
            parameters={"consulta": "contexto sintetico"},
            reasoning="test",
        ),
        raw_result={"success": True, "data": []},
        execution_time_ms=1.0,
        success=True,
    )


class FakeReadConnector:
    def connect(self):
        return True

    def get_database_schema(self):
        return None

    def disconnect(self):
        return None


class ExplodingWriteConnector:
    def start_agent_session(self, **_kwargs):
        raise AssertionError("agent session must not be persisted in production read-only")

    def log_conversation_context(self, **_kwargs):
        raise AssertionError("conversation context must not be persisted in production read-only")

    def end_agent_session(self, **_kwargs):
        raise AssertionError("agent session end must not be persisted in production read-only")

    def disconnect(self):
        return None


class ConnectedModel:
    def check_connection(self):
        return True


class FakePromptBuilder:
    def build_system_prompt(self, persona="default"):
        return f"system {persona}"


def test_agent_initialize_skips_session_write_in_production_read_only(monkeypatch):
    monkeypatch.setattr(
        agent_loop,
        "system_config",
        SimpleNamespace(production_read_only=True),
    )
    agent = object.__new__(ACUAgent)
    agent.domain = "production"
    agent.persona = "default"
    agent.db_connector = FakeReadConnector()
    agent.write_connector = ExplodingWriteConnector()
    agent.ollama_client = ConnectedModel()
    agent.prompt_builder = FakePromptBuilder()
    agent.conversation_history = []
    agent.system_prompt = None
    agent.session_id = "r62-test"
    agent.session_persisted = False

    import asyncio

    assert asyncio.run(agent.initialize()) is True
    assert agent.session_persisted is False

    agent._persist_conversation_turn("query", "answer", 1)


def test_direct_braincore_path_executes_only_allowed_tool_and_returns_context(monkeypatch):
    recorded = {"count": 0}
    tool_manager = DirectBrainCoreToolManager()
    gemini = DirectBrainCoreGeminiClient()
    monkeypatch.setattr(chat_routes, "GeminiClient", lambda: gemini)
    monkeypatch.setattr(chat_routes, "get_tools_manager", lambda: tool_manager)
    monkeypatch.setattr(
        chat_routes,
        "evaluate_ai_request",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True),
    )
    monkeypatch.setattr(
        chat_routes,
        "record_ai_request",
        lambda *_args, **_kwargs: recorded.__setitem__("count", recorded["count"] + 1),
    )

    import asyncio

    response = asyncio.run(
        chat_routes._direct_braincore_read_only_tool_response(
            ChatRequest(
                message="consulta sintetica",
                domain="production",
                persona="default",
                session_id="r62c-test",
            )
        )
    )

    assert response is not None
    assert response.session_id == "r62c-test"
    assert response.response == "respuesta con contexto braincore"
    assert response.iterations == 1
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "buscar_contexto_braincore"
    assert response.tool_calls[0].success is True
    assert tool_manager.calls[0][0].tool == ToolType.BRAINCORE_SEARCH
    assert recorded["count"] == 1
    assert gemini.kwargs["skip_cost_guard"] is True
    assert "Informacion operacional sintetica" in gemini.kwargs["user_message"]


def test_direct_braincore_path_fails_closed_when_tool_runtime_raises(monkeypatch):
    gemini = DirectBrainCoreGeminiClient()
    monkeypatch.setattr(chat_routes, "GeminiClient", lambda: gemini)
    monkeypatch.setattr(
        chat_routes,
        "get_tools_manager",
        lambda: ExplodingDirectBrainCoreToolManager(),
    )
    monkeypatch.setattr(
        chat_routes,
        "evaluate_ai_request",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True),
    )
    monkeypatch.setattr(chat_routes, "record_ai_request", lambda *_args, **_kwargs: None)

    import asyncio

    response = asyncio.run(
        chat_routes._direct_braincore_read_only_tool_response(
            ChatRequest(message="consulta sintetica", domain="production")
        )
    )

    assert response is not None
    assert response.tool_calls[0].tool == "buscar_contexto_braincore"
    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].error == "BrainCore read-only tool failed safely"
    assert "BrainCore no devolvio contexto util" in gemini.kwargs["user_message"]


def test_direct_braincore_path_fails_closed_when_tool_times_out(monkeypatch):
    gemini = DirectBrainCoreGeminiClient()
    monkeypatch.setattr(chat_routes, "GeminiClient", lambda: gemini)
    monkeypatch.setattr(
        chat_routes,
        "get_tools_manager",
        lambda: SlowDirectBrainCoreToolManager(),
    )
    monkeypatch.setattr(chat_routes, "_read_only_tool_timeout_seconds", lambda: 0.01)
    monkeypatch.setattr(
        chat_routes,
        "evaluate_ai_request",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True),
    )
    monkeypatch.setattr(chat_routes, "record_ai_request", lambda *_args, **_kwargs: None)

    import asyncio

    response = asyncio.run(
        chat_routes._direct_braincore_read_only_tool_response(
            ChatRequest(message="consulta sintetica", domain="production")
        )
    )

    assert response is not None
    assert response.tool_calls[0].tool == "buscar_contexto_braincore"
    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].error == "BrainCore read-only tool failed safely"
    assert "BrainCore no devolvio contexto util" in gemini.kwargs["user_message"]
