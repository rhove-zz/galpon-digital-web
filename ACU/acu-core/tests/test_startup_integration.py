import asyncio

import main as acu_main
from src.agent import agent_loop


class FakeDBConnector:
    def __init__(self, connect_result=True, schema_result=None, schema_text="schema"):
        self.connect_result = connect_result
        self.schema_result = schema_result
        self.schema_text = schema_text
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.schema_calls = 0
        self.session_calls = 0

    def connect(self):
        self.connect_calls += 1
        return self.connect_result

    def disconnect(self):
        self.disconnect_calls += 1

    def get_database_schema(self):
        self.schema_calls += 1
        return self.schema_result

    def format_schema_for_prompt(self):
        return self.schema_text

    def start_agent_session(self, session_id, domain):
        self.session_calls += 1
        return True

    def end_agent_session(self, session_id, total_iterations, status="completed"):
        return True

    def log_conversation_context(
        self,
        session_id,
        user_query,
        agent_response,
        steps_used,
    ):
        return True


class FakeOllamaClient:
    def __init__(self, available=True):
        self.available = available
        self.check_calls = 0

    def check_connection(self):
        self.check_calls += 1
        return self.available


class FakePromptBuilder:
    def __init__(self):
        self.calls = 0

    def build_system_prompt(self, persona="default"):
        self.calls += 1
        return "prompt listo"


class FakeToolsManager:
    pass


def test_agent_initialize_success(monkeypatch):
    fake_db = FakeDBConnector(connect_result=True, schema_result={"tables": 1})
    fake_ollama = FakeOllamaClient(available=True)
    fake_prompt_builder = FakePromptBuilder()

    monkeypatch.setattr(
        agent_loop, "get_db_connector", lambda use_read_only=True: fake_db
    )
    monkeypatch.setattr(agent_loop, "get_ollama_client", lambda: fake_ollama)
    monkeypatch.setattr(agent_loop, "get_tools_manager", lambda: FakeToolsManager())
    monkeypatch.setattr(
        agent_loop, "get_prompt_builder", lambda db: fake_prompt_builder
    )

    agent = agent_loop.ACUAgent(domain="integration")
    success = asyncio.run(agent.initialize())

    assert success is True
    assert fake_ollama.check_calls == 1
    assert fake_db.connect_calls == 1
    assert fake_db.schema_calls == 1
    assert fake_prompt_builder.calls == 1
    assert agent.system_prompt == "prompt listo"
    assert fake_db.session_calls == 1


def test_agent_initialize_fails_when_ollama_unavailable(monkeypatch):
    fake_db = FakeDBConnector(connect_result=True)
    fake_ollama = FakeOllamaClient(available=False)
    fake_prompt_builder = FakePromptBuilder()

    monkeypatch.setattr(
        agent_loop, "get_db_connector", lambda use_read_only=True: fake_db
    )
    monkeypatch.setattr(agent_loop, "get_ollama_client", lambda: fake_ollama)
    monkeypatch.setattr(agent_loop, "get_tools_manager", lambda: FakeToolsManager())
    monkeypatch.setattr(
        agent_loop, "get_prompt_builder", lambda db: fake_prompt_builder
    )

    agent = agent_loop.ACUAgent(domain="integration")
    success = asyncio.run(agent.initialize())

    assert success is False
    assert fake_db.connect_calls == 0
    assert fake_prompt_builder.calls == 0


class FakeMainAgent:
    instances = []

    def __init__(
        self,
        domain="generic",
        persona="default",
        initialize_result=True,
        responses=None,
    ):
        self.domain = domain
        self.persona = persona
        self.initialize_result = initialize_result
        self.responses = list(responses or ["respuesta"])
        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.processed_inputs = []
        self.__class__.instances.append(self)

    async def initialize(self):
        self.initialize_calls += 1
        return self.initialize_result

    async def process_user_message(self, user_input):
        self.processed_inputs.append(user_input)
        if self.responses:
            return self.responses.pop(0)
        return "respuesta"

    async def shutdown(self):
        self.shutdown_calls += 1


def test_main_interactive_loop_processes_input_and_shuts_down(monkeypatch):
    FakeMainAgent.instances = []
    outputs = []
    user_inputs = iter(["hola", "salir"])

    monkeypatch.setattr(
        acu_main,
        "ACUAgent",
        lambda domain="generic", persona="default": FakeMainAgent(
            domain=domain, persona=persona
        ),
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(user_inputs))
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: outputs.append(" ".join(map(str, args))),
    )

    exit_code = asyncio.run(acu_main.main())

    agent = FakeMainAgent.instances[0]
    assert exit_code == 0
    assert agent.initialize_calls == 1
    assert agent.processed_inputs == ["hola"]
    assert agent.shutdown_calls == 1
    assert any("Agente: respuesta" in line for line in outputs)


def test_demo_mode_processes_all_queries(monkeypatch):
    FakeMainAgent.instances = []
    outputs = []
    responses = ["r1", "r2", "r3"]

    monkeypatch.setattr(
        acu_main,
        "ACUAgent",
        lambda domain="generic", persona="default": FakeMainAgent(
            domain=domain, persona=persona, responses=list(responses)
        ),
    )
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: outputs.append(" ".join(map(str, args))),
    )

    exit_code = asyncio.run(acu_main.demo_mode())

    agent = FakeMainAgent.instances[0]
    assert exit_code == 0
    assert agent.domain == "demo"
    assert len(agent.processed_inputs) == 3
    assert agent.shutdown_calls == 1
    assert any("Respuesta: r1" in line for line in outputs)
