import asyncio
from pathlib import Path
import shutil
from types import SimpleNamespace

from src.agent import agent_loop
from src.llm import ollama_client
from src.tools import tools_manager


class DummyReadConnector:
    def __init__(self):
        self.queries = []

    def execute_read_query(self, query):
        self.queries.append(query)
        return {"success": True, "data": [{"ok": True}], "rows_affected": 1}

    def query_lessons(self, terminos, limit=5):
        return {
            "success": True,
            "data": [
                {"id": 1, "categoria": "sql", "leccion": "uno"},
                {"id": 2, "categoria": "sql", "leccion": "dos"},
            ],
        }


class DummyWriteConnector:
    def __init__(self):
        self.lesson_payload = None
        self.incremented_ids = None
        self.audit_payload = None
        self.connected = True

    def register_lesson(self, categoria, descripcion, relevancia=1):
        self.lesson_payload = (categoria, descripcion, relevancia)
        return {
            "success": True,
            "data": {"id": 7, "categoria": categoria, "leccion_aprendida": descripcion},
        }

    def is_connected(self):
        return self.connected

    def increment_lesson_usage(self, lesson_ids):
        self.incremented_ids = lesson_ids
        return True

    def log_tool_execution(
        self,
        tool_name,
        parameters,
        result,
        execution_time_ms,
        success,
    ):
        self.audit_payload = (
            tool_name,
            parameters,
            result,
            execution_time_ms,
            success,
        )
        return True


class DummyBrainCoreManager:
    def __init__(self):
        self.search_payload = None

    def search_context(
        self,
        query,
        domain=None,
        source_type=None,
        top_k=5,
    ):
        self.search_payload = {
            "query": query,
            "domain": domain,
            "source_type": source_type,
            "top_k": top_k,
        }
        return {
            "success": True,
            "data": [
                {
                    "chunk_id": 1,
                    "source_path": "wiki/api.md",
                    "title": "Arquitectura API",
                    "content": "FastAPI expone ACU como puente REST.",
                    "similarity": 0.9,
                    "metadata": {"source": {"domain": "acu"}},
                }
            ],
        }


class FakeWorkerAgent:
    instances = []
    initialize_result = True
    responses = ["worker result"]

    def __init__(self, domain="generic", persona="default"):
        self.domain = domain
        self.persona = persona
        self.initialize_calls = []
        self.messages = []
        self.responses = list(self.__class__.responses)
        self.__class__.instances.append(self)

    async def initialize(self, session_id=None):
        self.initialize_calls.append(session_id)
        return self.__class__.initialize_result

    async def process_user_message(self, message):
        self.messages.append(message)
        if self.responses:
            return self.responses.pop(0)
        return "worker fallback"


class FakeJudgeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_response(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _build_manager(monkeypatch):
    read_connector = DummyReadConnector()
    write_connector = DummyWriteConnector()
    braincore_manager = DummyBrainCoreManager()

    monkeypatch.setattr(
        tools_manager,
        "get_db_connector",
        lambda use_read_only=True: read_connector if use_read_only else write_connector,
    )
    monkeypatch.setattr(
        tools_manager,
        "get_braincore_manager",
        lambda: braincore_manager,
    )

    manager = tools_manager.ToolsManager()
    return manager, read_connector, write_connector


def test_execute_sql_read_requires_query(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)

    result = asyncio.run(manager._execute_sql_read({}))

    assert result["success"] is False
    assert "query_sql" in result["error"]


def test_execute_tool_persiste_auditoria(monkeypatch):
    manager, read_connector, write_connector = _build_manager(monkeypatch)
    tool_call = tools_manager.ToolCall(
        tool=tools_manager.ToolType.SQL_READ,
        parameters={"query_sql": "SELECT 1"},
    )

    result = asyncio.run(manager.execute_tool(tool_call))

    assert result.success is True
    assert read_connector.queries == ["SELECT 1"]
    assert write_connector.audit_payload is not None
    assert write_connector.audit_payload[0] == "ejecutar_sql_lectura"
    assert write_connector.audit_payload[1] == {"query_sql": "SELECT 1"}
    assert write_connector.audit_payload[2]["success"] is True
    assert write_connector.audit_payload[4] is True


def test_tool_audit_redacts_sensitive_payload(monkeypatch):
    manager, _, write_connector = _build_manager(monkeypatch)
    tool_call = tools_manager.ToolCall(
        tool=tools_manager.ToolType.SQL_READ,
        parameters={
            "query_sql": "SELECT 1",
            "Authorization": "Bearer secret-token",
            "nested": {"password": "hidden"},
        },
    )

    result = asyncio.run(manager.execute_tool(tool_call))

    assert result.success is True
    audited_parameters = write_connector.audit_payload[1]
    assert audited_parameters["Authorization"] == "[REDACTED]"
    assert audited_parameters["nested"]["password"] == "[REDACTED]"
    assert "secret-token" not in str(audited_parameters)


def test_registrar_leccion_uses_write_connector(monkeypatch):
    manager, _, write_connector = _build_manager(monkeypatch)

    result = asyncio.run(
        manager._registrar_leccion(
            {
                "categoria_sugerida": "error_handling",
                "descripcion_regla": "Revisar aliases",
                "relevancia": 3,
            }
        )
    )

    assert result["success"] is True
    assert write_connector.lesson_payload == ("error_handling", "Revisar aliases", 3)


def test_consultar_lecciones_incrementa_uso_si_hay_conexion_escritura(monkeypatch):
    manager, _, write_connector = _build_manager(monkeypatch)

    result = asyncio.run(
        manager._consultar_lecciones_aprendidas(
            {"terminos_busqueda": "sql optimization", "top_k": 2}
        )
    )

    assert result["success"] is True
    assert write_connector.incremented_ids == [1, 2]


def test_buscar_contexto_braincore_usa_manager(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)

    result = asyncio.run(
        manager._buscar_contexto_braincore(
            {
                "consulta": "decision arquitectura fastapi",
                "domain": "acu",
                "source_type": "markdown",
                "top_k": 3,
            }
        )
    )

    assert result["success"] is True
    assert result["data"][0]["source_path"] == "wiki/api.md"
    assert manager.braincore_manager.search_payload == {
        "query": "decision arquitectura fastapi",
        "domain": "acu",
        "source_type": "markdown",
        "top_k": 3,
    }


def test_buscar_contexto_braincore_requiere_consulta(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)

    result = asyncio.run(manager._buscar_contexto_braincore({}))

    assert result["success"] is False
    assert "consulta" in result["error"]


def test_execute_tool_soporta_busqueda_braincore(monkeypatch):
    manager, _, write_connector = _build_manager(monkeypatch)
    tool_call = tools_manager.ToolCall(
        tool=tools_manager.ToolType.BRAINCORE_SEARCH,
        parameters={"query": "fastapi rest", "top_k": 1},
    )

    result = asyncio.run(manager.execute_tool(tool_call))

    assert result.success is True
    assert result.result[0]["title"] == "Arquitectura API"
    assert write_connector.audit_payload[0] == "buscar_contexto_braincore"


def test_safe_mode_blocks_dangerous_tools_before_hitl(monkeypatch):
    manager, _, write_connector = _build_manager(monkeypatch)
    monkeypatch.setattr(tools_manager.system_config, "safe_mode", True)
    tools_manager.redis_manager.redis = None
    tools_manager.redis_manager.enabled = False
    tools_manager.redis_manager._local_pending_tools.clear()

    tool_call = tools_manager.ToolCall(
        tool=tools_manager.ToolType.API_REST,
        parameters={"method": "GET", "url": "https://example.test"},
    )

    result = asyncio.run(manager.execute_tool(tool_call, session_id="session-1"))

    assert result.success is False
    assert result.status == "blocked_by_policy"
    assert result.pending_tool_id is None
    assert write_connector.audit_payload[2]["status"] == "blocked_by_policy"


def test_sensitive_tool_returns_pending_when_safe_mode_disabled(monkeypatch):
    manager, _, write_connector = _build_manager(monkeypatch)
    monkeypatch.setattr(tools_manager.system_config, "safe_mode", False)
    monkeypatch.setattr(tools_manager.system_config, "external_tools_enabled", True)
    monkeypatch.setattr(tools_manager.system_config, "api_rest_enabled", True)
    tools_manager.redis_manager.redis = None
    tools_manager.redis_manager.enabled = False
    tools_manager.redis_manager._local_pending_tools.clear()

    tool_call = tools_manager.ToolCall(
        tool=tools_manager.ToolType.API_REST,
        parameters={"method": "GET", "url": "https://example.test"},
    )

    result = asyncio.run(manager.execute_tool(tool_call, session_id="session-1"))

    assert result.success is False
    assert result.status == "pending_approval"
    assert result.pending_tool_id
    assert write_connector.audit_payload[2]["status"] == "pending_approval"

    pending = asyncio.run(
        tools_manager.redis_manager.get_pending_tool(result.pending_tool_id)
    )
    assert pending["tool"] == tools_manager.ToolType.API_REST.value
    assert pending["session_id"] == "session-1"
    assert pending["parameters"] == {"method": "GET", "url": "https://example.test"}


def test_execute_pending_tool_runs_after_approval(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    monkeypatch.setattr(tools_manager.system_config, "safe_mode", False)
    monkeypatch.setattr(tools_manager.system_config, "external_tools_enabled", True)
    monkeypatch.setattr(tools_manager.system_config, "api_rest_enabled", True)
    tools_manager.redis_manager.redis = None
    tools_manager.redis_manager.enabled = False
    tools_manager.redis_manager._local_pending_tools.clear()

    async def fake_api_rest(parameters):
        return {"success": True, "data": {"status_code": 200, "response": "ok"}}

    manager._peticion_api_rest = fake_api_rest
    tool_call = tools_manager.ToolCall(
        tool=tools_manager.ToolType.API_REST,
        parameters={"method": "GET", "url": "https://example.test"},
    )

    pending_result = asyncio.run(
        manager.execute_tool(tool_call, session_id="session-approval")
    )
    assert pending_result.pending_tool_id

    approved = asyncio.run(
        tools_manager.redis_manager.resolve_pending_tool(
            pending_result.pending_tool_id, "approved"
        )
    )
    assert approved is True

    executed = asyncio.run(manager.execute_pending_tool(pending_result.pending_tool_id))

    assert executed.success is True
    assert executed.status == "executed"
    assert executed.pending_tool_id == pending_result.pending_tool_id
    assert executed.result == {"status_code": 200, "response": "ok"}

    pending = asyncio.run(
        tools_manager.redis_manager.get_pending_tool(pending_result.pending_tool_id)
    )
    assert pending["status"] == "executed"
    assert pending["result"]["success"] is True


def test_delegar_tarea_requires_task_description(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)

    result = asyncio.run(manager._delegar_tarea({}, session_id="session-main"))

    assert result["success"] is False
    assert "task_description" in result["error"]


def test_delegar_tarea_returns_error_when_worker_initialization_fails(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    FakeWorkerAgent.instances = []
    FakeWorkerAgent.initialize_result = False
    FakeWorkerAgent.responses = ["unused"]
    monkeypatch.setattr(agent_loop, "ACUAgent", FakeWorkerAgent)

    result = asyncio.run(
        manager._delegar_tarea(
            {
                "worker_persona": "arquitecto",
                "task_description": "Analiza el flujo API",
            },
            session_id="session-main",
        )
    )

    worker = FakeWorkerAgent.instances[0]
    assert result["success"] is False
    assert "inicializar" in result["error"]
    assert worker.domain == "worker"
    assert worker.persona == "arquitecto"
    assert worker.initialize_calls[0].startswith("session-main_worker_arquitecto_")
    assert worker.messages == []


def test_delegar_tarea_passes_worker_result_when_judge_approves(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    FakeWorkerAgent.instances = []
    FakeWorkerAgent.initialize_result = True
    FakeWorkerAgent.responses = ["respuesta del worker"]
    judge = FakeJudgeClient("PASS")
    monkeypatch.setattr(agent_loop, "ACUAgent", FakeWorkerAgent)
    monkeypatch.setattr(ollama_client, "get_ollama_client", lambda: judge)

    result = asyncio.run(
        manager._delegar_tarea(
            {
                "worker_persona": "analista",
                "task_description": "Resume riesgos tecnicos",
            },
            session_id="session-main",
        )
    )

    worker = FakeWorkerAgent.instances[0]
    assert result["success"] is True
    assert result["data"]["worker_persona"] == "analista"
    assert result["data"]["worker_session_id"].startswith(
        "session-main_worker_analista_"
    )
    assert result["data"]["result"] == "respuesta del worker"
    assert result["data"]["judge_approved"] is True
    assert worker.messages == ["Resume riesgos tecnicos"]
    assert judge.calls[0]["temperature"] == 0.0
    assert "respuesta del worker" in judge.calls[0]["user_message"]


def test_delegar_tarea_requests_worker_correction_when_judge_fails(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    FakeWorkerAgent.instances = []
    FakeWorkerAgent.initialize_result = True
    FakeWorkerAgent.responses = ["respuesta incompleta", "respuesta corregida"]
    judge = FakeJudgeClient("FAIL: faltan criterios de aceptacion")
    monkeypatch.setattr(agent_loop, "ACUAgent", FakeWorkerAgent)
    monkeypatch.setattr(ollama_client, "get_ollama_client", lambda: judge)

    result = asyncio.run(
        manager._delegar_tarea(
            {
                "worker_persona": "qa",
                "task_description": "Valida la feature",
            },
            session_id="session-main",
        )
    )

    worker = FakeWorkerAgent.instances[0]
    assert result["success"] is True
    assert result["data"]["result"] == "respuesta corregida"
    assert result["data"]["judge_approved"] is False
    assert worker.messages[0] == "Valida la feature"
    assert "faltan criterios de aceptacion" in worker.messages[1]


def test_buscar_documentos_indexa_archivos_locales(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    tmp_path = Path("tests/.tmp_docs")
    tmp_path.mkdir(parents=True, exist_ok=True)

    try:
        manager.project_root = tmp_path
        manager._document_index = []

        document = tmp_path / "guia.md"
        document.write_text(
            "# Configuracion\n\n"
            "La autenticacion LDAP requiere configurar el servicio y validar credenciales.\n\n"
            "## Detalle\n\n"
            "La configuracion del servicio depende del entorno.",
            encoding="utf-8",
        )

        result = asyncio.run(
            manager._buscar_documentos(
                {"consulta_semantica": "configurar autenticacion ldap", "top_k": 1}
            )
        )

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["metadata"]["source"] == "guia.md"
        assert "autenticacion" in result["data"][0]["document"].lower()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_buscar_documentos_prefiere_resultados_vectoriales(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    manager.vector_search_enabled = True
    manager._document_index = [
        {
            "source": "guia.md",
            "section": "Configuracion",
            "content": "La autenticacion LDAP requiere configurar credenciales.",
        }
    ]

    monkeypatch.setattr(
        manager,
        "_search_documents_vector",
        lambda query, top_k: [
            {
                "document": "resultado vectorial",
                "similarity": 0.91,
                "metadata": {
                    "source": "guia.md",
                    "section": "Configuracion",
                    "search_type": "vector_chromadb",
                },
            }
        ],
    )

    result = asyncio.run(
        manager._buscar_documentos(
            {"consulta_semantica": "autenticacion ldap", "top_k": 1}
        )
    )

    assert result["success"] is True
    assert result["data"][0]["document"] == "resultado vectorial"
    assert result["data"][0]["metadata"]["search_type"] == "vector_chromadb"


def test_busqueda_vectorial_no_soportada_degrada_a_textual(monkeypatch):
    manager, _, _ = _build_manager(monkeypatch)
    manager.vector_search_enabled = True
    manager.vector_config = SimpleNamespace(
        enabled=True,
        engine="faiss",
        persist_directory="./data/vectors",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )

    result = manager._search_documents_vector("autenticacion ldap", 1)

    assert result is None
    assert manager.vector_search_enabled is False
