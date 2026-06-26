import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.tools import router
from src.memory.redis_manager import redis_manager


class FakeAgent:
    def __init__(self):
        self.system_prompt = "ready"
        self.resumed_pending_tool = None

    async def initialize(self, session_id=None):
        return True

    async def resume_after_tool_approval(self, pending_tool):
        self.resumed_pending_tool = pending_tool
        return "respuesta reanudada"


class FakeToolsManager:
    async def execute_pending_tool(self, tool_id):
        pending_tool = await redis_manager.get_pending_tool(tool_id)
        assert pending_tool["status"] == "approved"
        pending_tool["status"] = "executed"
        pending_tool["result"] = {"success": True, "data": {"ok": 1}}
        await redis_manager.set_pending_tool(tool_id, pending_tool)
        return SimpleNamespace(
            success=True,
            status="executed",
            result=pending_tool["result"],
            error=None,
        )


def _client(agent: FakeAgent | None = None) -> TestClient:
    app = FastAPI()

    async def provider(domain, persona="default"):
        return agent or FakeAgent()

    app.state.agent_provider = provider
    app.state.agent_initialized = False
    app.include_router(router)
    return TestClient(app)


def _set_pending(tool_id: str, payload: dict):
    asyncio.run(redis_manager.set_pending_tool(tool_id, payload))


def setup_function():
    redis_manager.redis = None
    redis_manager.enabled = False
    redis_manager._local_pending_tools.clear()


def test_tools_router_lists_and_rejects_pending_tools():
    _set_pending(
        "tool-reject",
        {
            "tool": "peticion_api_rest",
            "parameters": {"url": "https://example.test"},
            "status": "pending",
            "session_id": "session-1",
        },
    )
    client = _client()

    pending = client.get("/tools/pending")
    rejected = client.post("/tools/pending/tool-reject/reject")
    missing = client.post("/tools/pending/missing/reject")

    assert pending.status_code == 200
    assert pending.json()[0]["id"] == "tool-reject"
    assert rejected.status_code == 200
    assert rejected.json() == {"success": True, "status": "rejected"}
    assert missing.status_code == 404


def test_tools_router_approves_and_executes_pending_tool(monkeypatch):
    _set_pending(
        "tool-approve",
        {
            "tool": "peticion_api_rest",
            "parameters": {"url": "https://example.test"},
            "status": "pending",
            "session_id": "session-1",
        },
    )
    from src.tools import tools_manager as tools_manager_module

    monkeypatch.setattr(
        tools_manager_module,
        "get_tools_manager",
        lambda: FakeToolsManager(),
    )
    client = _client()

    response = client.post("/tools/pending/tool-approve/approve")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "status": "executed",
        "pending_tool_id": "tool-approve",
        "result": {"success": True, "data": {"ok": 1}},
        "error": None,
    }


def test_tools_router_resume_requires_executed_status():
    _set_pending(
        "tool-pending",
        {
            "tool": "peticion_api_rest",
            "parameters": {},
            "status": "pending",
            "session_id": "session-1",
        },
    )
    client = _client()

    response = client.post("/tools/pending/tool-pending/resume")

    assert response.status_code == 409
    assert (
        response.json()["detail"] == "Tool call debe estar ejecutado antes de reanudar"
    )


def test_tools_router_resumes_executed_tool_and_marks_resumed():
    fake_agent = FakeAgent()
    _set_pending(
        "tool-executed",
        {
            "tool": "peticion_api_rest",
            "parameters": {"url": "https://example.test"},
            "status": "executed",
            "result": {"success": True},
            "session_id": "session-1",
            "domain": "ops",
            "persona": "admin",
        },
    )
    client = _client(fake_agent)

    response = client.post("/tools/pending/tool-executed/resume")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "status": "resumed",
        "pending_tool_id": "tool-executed",
        "session_id": "session-1",
        "response": "respuesta reanudada",
    }
    assert fake_agent.resumed_pending_tool["id"] == "tool-executed"

    pending = asyncio.run(redis_manager.get_pending_tool("tool-executed"))
    assert pending["status"] == "resumed"
    assert pending["resumed_response"] == "respuesta reanudada"
