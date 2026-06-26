from src.memory.repositories.sessions import SessionsRepository


class FakeCursor:
    def __init__(self, fetchall_results=None, rowcount=0, rowcounts=None):
        self.fetchall_results = list(fetchall_results or [])
        self.executed = []
        self.closed = False
        self.rowcount = rowcount
        self._rowcounts = list(rowcounts or [])

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if self._rowcounts:
            self.rowcount = self._rowcounts.pop(0)

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


def test_sessions_repository_starts_and_ends_agent_session():
    start_cursor = FakeCursor()
    start_connector = FakeConnector(start_cursor)
    end_cursor = FakeCursor()
    end_connector = FakeConnector(end_cursor)

    started = SessionsRepository(start_connector).start_agent_session(
        "session-1",
        "acu",
    )
    ended = SessionsRepository(end_connector).end_agent_session(
        session_id="session-1",
        total_iterations=4,
        status="completed",
    )

    assert started is True
    assert start_connector.connection.commit_calls == 1
    assert "INSERT INTO agent_sessions" in start_cursor.executed[0][0]
    assert start_cursor.executed[0][1] == ("session-1", "acu", 0, "active")
    assert ended is True
    assert end_connector.connection.commit_calls == 1
    assert "UPDATE agent_sessions" in end_cursor.executed[0][0]
    assert end_cursor.executed[0][1] == (4, "completed", "session-1")


def test_sessions_repository_rejects_writes_on_read_only_connector():
    repository = SessionsRepository(FakeConnector(FakeCursor(), use_read_only=True))

    assert repository.start_agent_session("session-1", "acu") is False
    assert repository.end_agent_session("session-1", 1) is False
    assert repository.log_conversation_context("session-1", "q", "a", 1) is False
    assert repository.prune_conversation_context()["success"] is False
    assert repository.prune_agent_sessions()["success"] is False


def test_sessions_repository_logs_conversation_context():
    cursor = FakeCursor()
    connector = FakeConnector(cursor)
    repository = SessionsRepository(connector)

    result = repository.log_conversation_context(
        session_id="session-1",
        user_query="consulta",
        agent_response="respuesta",
        steps_used=2,
    )

    assert result is True
    assert connector.connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "INSERT INTO conversation_context" in query
    assert params == ("session-1", "consulta", "respuesta", 2)


def test_sessions_repository_lists_sessions_with_filters_and_limit_bounds():
    rows = [
        {
            "session_id": "session-1",
            "domain": "acu",
            "started_at": "2026-05-14 10:00:00",
            "ended_at": None,
            "total_iterations": 3,
            "status": "active",
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    repository = SessionsRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.list_agent_sessions(domain="acu", status="active", limit=500)

    assert result["success"] is True
    assert result["data"] == rows
    query, params = cursor.executed[0]
    assert "FROM agent_sessions" in query
    assert params == ("acu", "active", 100)


def test_sessions_repository_gets_conversation_context_with_limit_bounds():
    rows = [
        {
            "id": 1,
            "session_id": "session-1",
            "user_query": "hola",
            "agent_response": "respuesta",
            "timestamp": "2026-05-14 10:00:00",
            "steps_used": 2,
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    repository = SessionsRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.get_conversation_context(session_id="session-1", limit=500)

    assert result["success"] is True
    assert result["data"] == rows
    query, params = cursor.executed[0]
    assert "FROM conversation_context" in query
    assert params == ("session-1", 200)


def test_sessions_repository_prunes_context_and_completed_sessions():
    context_cursor = FakeCursor(rowcount=3)
    context_connector = FakeConnector(context_cursor)
    sessions_cursor = FakeCursor(rowcounts=[4, 2])
    sessions_connector = FakeConnector(sessions_cursor)

    context_result = SessionsRepository(context_connector).prune_conversation_context(
        older_than_days=45
    )
    sessions_result = SessionsRepository(sessions_connector).prune_agent_sessions(
        older_than_days=60
    )

    assert context_result == {"success": True, "rows_deleted": 3}
    assert context_connector.connection.commit_calls == 1
    assert "DELETE FROM conversation_context" in context_cursor.executed[0][0]
    assert context_cursor.executed[0][1] == (45,)
    assert sessions_result == {
        "success": True,
        "rows_deleted": 2,
        "context_rows_deleted": 4,
    }
    assert sessions_connector.connection.commit_calls == 1
    assert "DELETE FROM conversation_context" in sessions_cursor.executed[0][0]
    assert "DELETE FROM agent_sessions" in sessions_cursor.executed[1][0]
    assert sessions_cursor.executed[0][1] == (60,)
    assert sessions_cursor.executed[1][1] == (60,)
