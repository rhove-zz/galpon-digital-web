from src.memory.repositories.audit import AuditRepository


class FakeCursor:
    def __init__(self, fetchall_results=None, rowcount=0):
        self.fetchall_results = list(fetchall_results or [])
        self.executed = []
        self.closed = False
        self.rowcount = rowcount

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        if self.fetchall_results:
            return self.fetchall_results.pop(0)
        return []

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


def test_audit_repository_logs_tool_execution():
    cursor = FakeCursor()
    connector = FakeConnector(cursor)
    repository = AuditRepository(connector)

    result = repository.log_tool_execution(
        tool_name="buscar_contexto_braincore",
        parameters={"query": "fastapi"},
        result={"success": True},
        execution_time_ms=12.8,
        success=True,
    )

    assert result is True
    assert connector.connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "INSERT INTO tool_execution_log" in query
    assert params[0] == "buscar_contexto_braincore"
    assert params[1] == '{"query": "fastapi"}'
    assert params[3] == 12


def test_audit_repository_logs_api_access_and_truncates_user_agent():
    cursor = FakeCursor()
    connector = FakeConnector(cursor)
    repository = AuditRepository(connector)

    result = repository.log_api_access(
        method="POST",
        path="/chat",
        status_code=200,
        key_fingerprint="abc123",
        roles=["chat"],
        client_ip="127.0.0.1",
        user_agent="x" * 600,
        authorized=True,
        duration_ms=14.7,
    )

    assert result is True
    query, params = cursor.executed[0]
    assert "INSERT INTO api_access_log" in query
    assert params[4] == '["chat"]'
    assert len(params[6]) == 512
    assert params[8] == 14


def test_audit_repository_rejects_writes_on_read_only_connector():
    repository = AuditRepository(FakeConnector(FakeCursor(), use_read_only=True))

    assert repository.log_tool_execution("tool", {}, {}, 1.0, True) is False
    assert repository.log_api_access("GET", "/health", 200) is False
    assert repository.prune_tool_execution_log()["success"] is False
    assert repository.prune_api_access_log()["success"] is False


def test_audit_repository_lists_tool_executions_and_normalizes_json():
    rows = [
        {
            "id": 1,
            "tool_name": "buscar_contexto_braincore",
            "parameters": '{"query": "fastapi"}',
            "result": '{"success": true}',
            "execution_time_ms": 12,
            "success": 1,
            "executed_at": "2026-05-14 10:00:00",
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    repository = AuditRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.list_tool_executions(
        tool_name="buscar_contexto_braincore",
        success=True,
        limit=500,
    )

    assert result["success"] is True
    assert result["data"][0]["parameters"] == {"query": "fastapi"}
    assert result["data"][0]["result"] == {"success": True}
    assert result["data"][0]["success"] is True
    query, params = cursor.executed[0]
    assert "FROM tool_execution_log" in query
    assert params == ("buscar_contexto_braincore", True, 200)


def test_audit_repository_lists_api_access_log_and_normalizes_roles():
    rows = [
        {
            "id": 1,
            "method": "POST",
            "path": "/chat",
            "status_code": 200,
            "key_fingerprint": "abc123",
            "roles": '["chat"]',
            "client_ip": "127.0.0.1",
            "user_agent": "pytest",
            "authorized": 1,
            "duration_ms": 14,
            "accessed_at": "2026-05-14 10:00:00",
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    repository = AuditRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.list_api_access_log(
        path="/chat",
        status_code=200,
        authorized=True,
        limit=9,
    )

    assert result["success"] is True
    assert result["data"][0]["roles"] == ["chat"]
    assert result["data"][0]["authorized"] is True
    query, params = cursor.executed[0]
    assert "FROM api_access_log" in query
    assert params == ("/chat", 200, True, 9)


def test_audit_repository_prunes_tool_and_api_access_logs():
    tool_cursor = FakeCursor(rowcount=2)
    tool_connector = FakeConnector(tool_cursor)
    api_cursor = FakeCursor(rowcount=3)
    api_connector = FakeConnector(api_cursor)

    tool_result = AuditRepository(tool_connector).prune_tool_execution_log(
        older_than_days=15
    )
    api_result = AuditRepository(api_connector).prune_api_access_log(older_than_days=20)

    assert tool_result == {"success": True, "rows_deleted": 2}
    assert api_result == {"success": True, "rows_deleted": 3}
    assert "DELETE FROM tool_execution_log" in tool_cursor.executed[0][0]
    assert tool_cursor.executed[0][1] == (15,)
    assert "DELETE FROM api_access_log" in api_cursor.executed[0][0]
    assert api_cursor.executed[0][1] == (20,)
