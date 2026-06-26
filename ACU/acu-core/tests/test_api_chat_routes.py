from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

from src.api.agent_runtime import get_initialized_agent
from src.api.routes.chat import _count_tool_log, _serialize_tool_calls


class FakeToolsManager:
    def __init__(self):
        self.log = [
            SimpleNamespace(
                tool=SimpleNamespace(value="sql_query"),
                success=True,
                result={"rows": 1},
                error=None,
                execution_time_ms=12.5,
            )
        ]

    def get_execution_log(self):
        return self.log


class FakeAgent:
    def __init__(self, system_prompt="", initialize_result=True):
        self.system_prompt = system_prompt
        self.initialize_result = initialize_result

    async def initialize(self, session_id=None):
        self.session_id = session_id
        self.system_prompt = "ready" if self.initialize_result else ""
        return self.initialize_result


def test_chat_route_helpers_serialize_new_tool_calls():
    manager = FakeToolsManager()

    assert _count_tool_log(manager) == 1
    serialized = _serialize_tool_calls(manager, 0)

    assert len(serialized) == 1
    assert serialized[0].tool == "sql_query"
    assert serialized[0].success is True
    assert serialized[0].result == {"rows": 1}


@pytest.mark.asyncio
async def test_get_initialized_agent_initializes_when_needed():
    app = FastAPI()
    agent = FakeAgent(initialize_result=True)

    async def provider(domain, persona):
        return agent

    app.state.agent_provider = provider

    initialized = await get_initialized_agent(app, "acu", "default", "session-1")

    assert initialized is agent
    assert agent.session_id == "session-1"


@pytest.mark.asyncio
async def test_get_initialized_agent_raises_503_when_initialization_fails():
    app = FastAPI()
    agent = FakeAgent(initialize_result=False)

    async def provider(domain, persona):
        return agent

    app.state.agent_provider = provider

    with pytest.raises(HTTPException) as exc:
        await get_initialized_agent(app, "acu", "default")

    assert exc.value.status_code == 503
