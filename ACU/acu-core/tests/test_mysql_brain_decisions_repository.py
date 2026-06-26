from src.memory.repositories.brain_decisions import BrainDecisionRepository


class FakeCursor:
    def __init__(self, fetchall_results=None, fetchone_results=None):
        self.fetchall_results = list(fetchall_results or [])
        self.fetchone_results = list(fetchone_results or [])
        self.executed = []
        self.closed = False
        self.lastrowid = 99

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        if self.fetchall_results:
            return self.fetchall_results.pop(0)
        return []

    def fetchone(self):
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commit_calls = 0

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        self.commit_calls += 1


class FakeConnector:
    def __init__(self, cursor, use_read_only=False, connected=True):
        self.use_read_only = use_read_only
        self.connection = FakeConnection(cursor)
        self.connected = connected

    def _ensure_connection(self):
        return self.connected


def _decision_row():
    return {
        "id": 99,
        "title": "Usar FastAPI",
        "context": "Necesitamos API REST",
        "decision": "Exponer ACU via FastAPI",
        "alternatives": '["Flask"]',
        "impact": "Permite clientes externos",
        "domain": "acu",
        "status": "accepted",
        "tags": '["api", "braincore"]',
        "created_at": "2026-05-14 10:00:00",
        "updated_at": "2026-05-14 10:00:00",
    }


def test_brain_decision_repository_registers_decision_and_normalizes_json():
    cursor = FakeCursor(fetchone_results=[_decision_row()])
    connector = FakeConnector(cursor)
    repository = BrainDecisionRepository(connector)

    result = repository.register_brain_decision(
        title="Usar FastAPI",
        context="Necesitamos API REST",
        decision="Exponer ACU via FastAPI",
        alternatives=["Flask"],
        impact="Permite clientes externos",
        domain="acu",
        status="accepted",
        tags=["api", "braincore"],
    )

    assert result["success"] is True
    assert result["data"]["alternatives"] == ["Flask"]
    assert result["data"]["tags"] == ["api", "braincore"]
    assert connector.connection.commit_calls == 1
    insert_query, insert_params = cursor.executed[0]
    assert "INSERT INTO brain_decisions" in insert_query
    assert insert_params[0] == "Usar FastAPI"
    assert insert_params[3] == '["Flask"]'


def test_brain_decision_repository_rejects_invalid_or_read_only_writes():
    writable_repository = BrainDecisionRepository(FakeConnector(FakeCursor()))
    read_only_repository = BrainDecisionRepository(
        FakeConnector(FakeCursor(), use_read_only=True)
    )

    invalid = writable_repository.register_brain_decision(
        title="",
        context="ctx",
        decision="decision",
        alternatives=[],
        impact="",
    )
    read_only = read_only_repository.register_brain_decision(
        title="titulo",
        context="ctx",
        decision="decision",
        alternatives=[],
        impact="",
    )

    assert invalid["success"] is False
    assert "requeridos" in invalid["error"]
    assert read_only["success"] is False
    assert "solo lectura" in read_only["error"]


def test_brain_decision_repository_lists_with_filters_and_limit_bounds():
    cursor = FakeCursor(fetchall_results=[[_decision_row()]])
    repository = BrainDecisionRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.list_brain_decisions(
        search="fastapi",
        domain="acu",
        status="accepted",
        limit=500,
    )

    assert result["success"] is True
    assert result["data"][0]["alternatives"] == ["Flask"]
    assert result["data"][0]["tags"] == ["api", "braincore"]
    query, params = cursor.executed[0]
    assert "FROM brain_decisions" in query
    assert params[-3:] == ("acu", "accepted", 100)
    assert params[:4] == ("%fastapi%", "%fastapi%", "%fastapi%", "%fastapi%")


def test_brain_decision_repository_returns_connection_error():
    repository = BrainDecisionRepository(FakeConnector(FakeCursor(), connected=False))

    listed = repository.list_brain_decisions()
    registered = repository.register_brain_decision(
        title="titulo",
        context="ctx",
        decision="decision",
        alternatives=[],
        impact="",
    )

    assert listed["success"] is False
    assert "conexion" in listed["error"]
    assert registered["success"] is False
    assert "conexion" in registered["error"]
