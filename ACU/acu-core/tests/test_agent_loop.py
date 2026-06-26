import asyncio

from src.agent import agent_loop
from src.utils.schemas import ReActState, ToolCall, ToolType


class DummyDBConnector:
    def __init__(self):
        self.started_sessions = []
        self.ended_sessions = []
        self.conversation_rows = []
        self.disconnect_calls = 0

    def connect(self):
        return True

    def disconnect(self):
        self.disconnect_calls += 1
        return True

    def get_database_schema(self):
        return None

    def format_schema_for_prompt(self):
        return ""

    def start_agent_session(self, session_id, domain):
        self.started_sessions.append((session_id, domain))
        return True

    def end_agent_session(self, session_id, total_iterations, status="completed"):
        self.ended_sessions.append((session_id, total_iterations, status))
        return True

    def log_conversation_context(
        self,
        session_id,
        user_query,
        agent_response,
        steps_used,
    ):
        self.conversation_rows.append(
            (session_id, user_query, agent_response, steps_used)
        )
        return True


class DummyPromptBuilder:
    def build_system_prompt(self, persona="default"):
        return "system prompt"


class DummyToolsManager:
    async def execute_tool(self, tool_call):
        return None


class MissingDecisionOllama:
    def check_connection(self):
        return True

    def generate_response(self, *args, **kwargs):
        return None

    def parse_tool_calls(self, response):
        return []


class InvalidToolOllama:
    def check_connection(self):
        return True

    def generate_response(self, *args, **kwargs):
        return '<tool>{"tool": "tool_inexistente", "parameters": {}}</tool>'

    def parse_tool_calls(self, response):
        return [{"tool": "tool_inexistente", "parameters": {}}]


class ResumeOllama:
    def __init__(self, response="respuesta reanudada"):
        self.response = response
        self.calls = []

    def check_connection(self):
        return True

    def generate_response(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.response

    def parse_tool_calls(self, response):
        return []


def _build_agent(monkeypatch, ollama):
    dummy_db = DummyDBConnector()
    dummy_tools = DummyToolsManager()
    dummy_prompt = DummyPromptBuilder()

    monkeypatch.setattr(
        agent_loop, "get_db_connector", lambda use_read_only=True: dummy_db
    )
    monkeypatch.setattr(agent_loop, "get_ollama_client", lambda: ollama)
    monkeypatch.setattr(agent_loop, "get_tools_manager", lambda: dummy_tools)
    monkeypatch.setattr(agent_loop, "get_prompt_builder", lambda db: dummy_prompt)

    agent = agent_loop.ACUAgent(domain="test")
    agent.system_prompt = "system prompt"
    return agent


def test_thought_phase_handles_missing_decision_response(monkeypatch):
    agent = _build_agent(monkeypatch, MissingDecisionOllama())
    state = ReActState(step=1, observation="obs", thought="prev")

    asyncio.run(agent._thought_phase(state, "consulta"))

    assert state.is_complete is True
    assert "decidir la siguiente accion" in state.final_answer.lower()


def test_thought_phase_handles_invalid_tool_call(monkeypatch):
    agent = _build_agent(monkeypatch, InvalidToolOllama())
    state = ReActState(step=1, observation="obs", thought="prev")

    asyncio.run(agent._thought_phase(state, "consulta"))

    assert state.is_complete is True
    assert "invocacion de herramienta invalida" in state.final_answer.lower()


def test_process_user_message_clears_previous_action_between_iterations(monkeypatch):
    agent = _build_agent(monkeypatch, MissingDecisionOllama())
    calls = {"action": 0}

    async def fake_observation(state, user_input):
        state.observation = "obs"

    async def fake_thought(state, user_input):
        if state.step == 0:
            state.action = ToolCall(
                tool=ToolType.SQL_READ,
                parameters={"query_sql": "SELECT 1"},
            )

    async def fake_action(state):
        calls["action"] += 1
        state.observation = "query ok"

    async def fake_conclusion(state, user_input):
        state.final_answer = "final"
        state.is_complete = True

    agent._observation_phase = fake_observation
    agent._thought_phase = fake_thought
    agent._action_phase = fake_action
    agent._conclusion_phase = fake_conclusion

    result = asyncio.run(agent.process_user_message("consulta"))

    assert result == "final"
    assert calls["action"] == 1
    assert agent.conversation_history[-1].content == "final"


def test_agent_persiste_sesion_y_contexto(monkeypatch):
    read_db = DummyDBConnector()
    write_db = DummyDBConnector()
    ollama = MissingDecisionOllama()
    dummy_prompt = DummyPromptBuilder()

    monkeypatch.setattr(
        agent_loop,
        "get_db_connector",
        lambda use_read_only=True: read_db if use_read_only else write_db,
    )
    monkeypatch.setattr(agent_loop, "get_ollama_client", lambda: ollama)
    monkeypatch.setattr(agent_loop, "get_tools_manager", lambda: DummyToolsManager())
    monkeypatch.setattr(agent_loop, "get_prompt_builder", lambda db: dummy_prompt)

    agent = agent_loop.ACUAgent(domain="integration")
    assert asyncio.run(agent.initialize()) is True

    async def fake_observation(state, user_input):
        state.observation = "obs"

    async def fake_thought(state, user_input):
        state.final_answer = "respuesta final"
        state.is_complete = True

    agent._observation_phase = fake_observation
    agent._thought_phase = fake_thought

    result = asyncio.run(agent.process_user_message("consulta"))
    asyncio.run(agent.shutdown())

    assert result == "respuesta final"
    assert write_db.started_sessions == [(agent.session_id, "integration")]
    assert write_db.conversation_rows == [
        (agent.session_id, "consulta", "respuesta final", 1)
    ]
    assert write_db.ended_sessions == [(agent.session_id, 1, "completed")]


def test_resume_after_tool_approval_generates_and_persists_response(monkeypatch):
    read_db = DummyDBConnector()
    write_db = DummyDBConnector()
    ollama = ResumeOllama("respuesta final tras aprobacion")
    dummy_prompt = DummyPromptBuilder()

    monkeypatch.setattr(
        agent_loop,
        "get_db_connector",
        lambda use_read_only=True: read_db if use_read_only else write_db,
    )
    monkeypatch.setattr(agent_loop, "get_ollama_client", lambda: ollama)
    monkeypatch.setattr(agent_loop, "get_tools_manager", lambda: DummyToolsManager())
    monkeypatch.setattr(agent_loop, "get_prompt_builder", lambda db: dummy_prompt)

    agent = agent_loop.ACUAgent(domain="integration")
    assert asyncio.run(agent.initialize()) is True

    response = asyncio.run(
        agent.resume_after_tool_approval(
            {
                "id": "tool-1",
                "tool": "peticion_api_rest",
                "parameters": {"url": "https://example.test"},
                "result": {"success": True, "result": {"status_code": 200}},
            }
        )
    )

    assert response == "respuesta final tras aprobacion"
    assert agent.conversation_history[-1].content == response
    assert "peticion_api_rest" in ollama.calls[0]["user_message"]
    assert write_db.conversation_rows[-1] == (
        agent.session_id,
        "Reanudacion HITL tool-1",
        response,
        0,
    )
