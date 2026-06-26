from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.monitoring import router


class FakeDatabase:
    def __init__(self):
        self.sessions_payload = None
        self.context_payload = None
        self.tools_payload = None
        self.access_payload = None
        self.failures = set()

    def list_agent_sessions(self, domain=None, status=None, limit=20):
        self.sessions_payload = {
            "domain": domain,
            "status": status,
            "limit": limit,
        }
        if "sessions" in self.failures:
            return {"success": False, "error": "sessions failed"}
        return {
            "success": True,
            "data": [
                {
                    "session_id": "session-1",
                    "domain": domain,
                    "started_at": "2026-05-19 10:00:00",
                    "ended_at": None,
                    "total_iterations": 3,
                    "status": status or "active",
                }
            ],
        }

    def get_conversation_context(self, session_id, limit=50):
        self.context_payload = {"session_id": session_id, "limit": limit}
        return {
            "success": True,
            "data": [
                {
                    "id": 1,
                    "session_id": session_id,
                    "user_query": "hola",
                    "agent_response": "respuesta",
                    "timestamp": "2026-05-19 10:01:00",
                    "steps_used": 2,
                }
            ],
        }

    def list_tool_executions(self, tool_name=None, success=None, limit=50):
        self.tools_payload = {
            "tool_name": tool_name,
            "success": success,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "id": 7,
                    "tool_name": tool_name or "ejecutar_sql_lectura",
                    "parameters": {"query_sql": "SELECT 1"},
                    "result": {"success": True},
                    "execution_time_ms": 12,
                    "success": bool(success) if success is not None else True,
                    "executed_at": "2026-05-19 10:02:00",
                }
            ],
        }

    def list_api_access_log(
        self,
        path=None,
        status_code=None,
        authorized=None,
        limit=50,
    ):
        self.access_payload = {
            "path": path,
            "status_code": status_code,
            "authorized": authorized,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "id": 9,
                    "method": "GET",
                    "path": path or "/sessions",
                    "status_code": status_code or 200,
                    "key_fingerprint": "abc123",
                    "roles": ["monitoring"],
                    "client_ip": "127.0.0.1",
                    "user_agent": "testclient",
                    "authorized": authorized if authorized is not None else True,
                    "duration_ms": 4,
                    "accessed_at": "2026-05-19 10:03:00",
                }
            ],
        }


def _client(db: FakeDatabase) -> TestClient:
    app = FastAPI()
    app.state.database_provider = lambda: db
    app.include_router(router)
    return TestClient(app)


def test_monitoring_router_lists_sessions_with_filters():
    db = FakeDatabase()
    client = _client(db)

    response = client.get("/sessions?domain=acu&status=active&limit=5")

    assert response.status_code == 200
    assert response.json()[0]["session_id"] == "session-1"
    assert db.sessions_payload == {"domain": "acu", "status": "active", "limit": 5}


def test_monitoring_router_lists_session_context():
    db = FakeDatabase()
    client = _client(db)

    response = client.get("/sessions/session-1/context?limit=10")

    assert response.status_code == 200
    assert response.json()[0]["agent_response"] == "respuesta"
    assert db.context_payload == {"session_id": "session-1", "limit": 10}


def test_monitoring_router_lists_tool_executions():
    db = FakeDatabase()
    client = _client(db)

    response = client.get("/tools/executions?tool_name=sql&success=true&limit=3")

    assert response.status_code == 200
    assert response.json()[0]["tool_name"] == "sql"
    assert db.tools_payload == {"tool_name": "sql", "success": True, "limit": 3}


def test_monitoring_router_lists_api_access_log():
    db = FakeDatabase()
    client = _client(db)

    response = client.get("/api/access-log?path=/chat&status_code=200&authorized=true")

    assert response.status_code == 200
    assert response.json()[0]["path"] == "/chat"
    assert db.access_payload == {
        "path": "/chat",
        "status_code": 200,
        "authorized": True,
        "limit": 50,
    }


def test_monitoring_router_returns_500_on_repository_error():
    db = FakeDatabase()
    db.failures.add("sessions")
    client = _client(db)

    response = client.get("/sessions")

    assert response.status_code == 500
    assert response.json()["detail"] == "sessions failed"
