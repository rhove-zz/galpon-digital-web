from src.memory import mysql_manager


class FakeCursor:
    def __init__(
        self,
        fetchall_results=None,
        fetchone_results=None,
        rowcount=0,
        rowcounts=None,
    ):
        self.fetchall_results = list(fetchall_results or [])
        self.fetchone_results = list(fetchone_results or [])
        self.executed = []
        self.closed = False
        self.lastrowid = 99
        self.executemany_calls = []
        self.rowcount = rowcount
        self._rowcounts = list(rowcounts or [])

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if self._rowcounts:
            self.rowcount = self._rowcounts.pop(0)

    def executemany(self, query, values):
        self.executemany_calls.append((query, values))

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
        self.closed = False

    def is_connected(self):
        return True

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        self.commit_calls += 1

    def close(self):
        self.closed = True


def test_build_config_switches_credentials(monkeypatch):
    monkeypatch.setattr(mysql_manager.mysql_config, "read_only_user", "reader")
    monkeypatch.setattr(mysql_manager.mysql_config, "read_only_password", "reader-pass")
    monkeypatch.setattr(mysql_manager.mysql_config, "user", "writer")
    monkeypatch.setattr(mysql_manager.mysql_config, "password", "writer-pass")

    read_connector = mysql_manager.MySQLConnector(use_read_only=True)
    write_connector = mysql_manager.MySQLConnector(use_read_only=False)

    assert read_connector._build_config()["user"] == "reader"
    assert read_connector._build_config()["password"] == "reader-pass"
    assert read_connector._build_config()["autocommit"] is True
    assert write_connector._build_config()["user"] == "writer"
    assert write_connector._build_config()["password"] == "writer-pass"
    assert write_connector._build_config()["autocommit"] is True


def test_execute_read_query_rejects_non_select():
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector._ensure_connection = lambda: True
    connector.connection = FakeConnection(FakeCursor())

    result = connector.execute_read_query("DELETE FROM usuarios")

    assert result["success"] is False
    assert "Solo se permiten queries SELECT" in result["error"]


def test_get_database_schema_builds_and_caches_schema(monkeypatch):
    cursor = FakeCursor(
        fetchall_results=[
            [{"TABLE_NAME": "usuarios"}],
            [
                {
                    "COLUMN_NAME": "id",
                    "COLUMN_TYPE": "int",
                    "IS_NULLABLE": "NO",
                    "COLUMN_KEY": "PRI",
                }
            ],
            [],
        ]
    )
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    schema = connector.get_database_schema()
    cached_schema = connector.get_database_schema()

    assert schema.database == mysql_manager.mysql_config.database
    assert "usuarios" in schema.tables
    assert cached_schema is schema
    assert len(cursor.executed) == 3


def test_register_lesson_persists_with_write_connector():
    lesson_row = {
        "id": 99,
        "categoria": "error_handling",
        "leccion_aprendida": "Revisar aliases",
        "fecha_registro": "2026-04-25 10:00:00",
        "relevancia": 3,
        "veces_utilizada": 0,
    }
    cursor = FakeCursor(fetchone_results=[lesson_row])
    cursor.lastrowid = 99

    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.register_lesson(
        "error_handling", "Revisar aliases", relevancia=3
    )

    assert result["success"] is True
    assert result["data"]["id"] == 99
    assert connector.connection.commit_calls == 1
    assert len(cursor.executed) == 2


def test_query_lessons_ranks_and_limits_results():
    candidates = [
        {
            "id": 1,
            "categoria": "sql_optimization",
            "leccion_aprendida": "Usar indices en columnas frecuentes",
            "fecha_registro": "2026-04-25 09:00:00",
            "relevancia": 5,
            "veces_utilizada": 2,
        },
        {
            "id": 2,
            "categoria": "general",
            "leccion_aprendida": "Consulta no relacionada",
            "fecha_registro": "2026-04-24 09:00:00",
            "relevancia": 1,
            "veces_utilizada": 0,
        },
    ]
    cursor = FakeCursor(fetchall_results=[candidates])
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.query_lessons("sql indices", limit=1)

    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["id"] == 1
    assert result["data"][0]["score"] > 0
    assert cursor.executed[0][1][-1] == 10


def test_increment_lesson_usage_updates_rows():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    success = connector.increment_lesson_usage([3, 4])

    assert success is True
    assert connection.commit_calls == 1
    assert cursor.executemany_calls[0][1] == [(3,), (4,)]


def test_log_tool_execution_persists_audit_row():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    success = connector.log_tool_execution(
        tool_name="ejecutar_sql_lectura",
        parameters={"query_sql": "SELECT 1"},
        result={"success": True, "data": [{"ok": 1}]},
        execution_time_ms=12.7,
        success=True,
    )

    assert success is True
    assert connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "INSERT INTO tool_execution_log" in query
    assert params[0] == "ejecutar_sql_lectura"
    assert '"query_sql": "SELECT 1"' in params[1]
    assert '"success": true' in params[2]
    assert params[3] == 12
    assert params[4] is True


def test_log_api_access_persists_audit_row():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    success = connector.log_api_access(
        method="POST",
        path="/chat",
        status_code=200,
        key_fingerprint="abc123",
        roles=["chat"],
        client_ip="127.0.0.1",
        user_agent="testclient",
        authorized=True,
        duration_ms=14.8,
    )

    assert success is True
    assert connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "INSERT INTO api_access_log" in query
    assert params[0] == "POST"
    assert params[1] == "/chat"
    assert params[2] == 200
    assert params[3] == "abc123"
    assert params[4] == '["chat"]'
    assert params[8] == 14


def test_create_api_key_persists_hash_and_returns_metadata():
    key_row = {
        "id": 10,
        "name": "chat client",
        "key_fingerprint": "abc123",
        "roles": '["chat"]',
        "status": "active",
        "created_by": "admin",
        "created_at": "2026-05-14 10:00:00",
        "revoked_at": None,
        "expires_at": None,
        "last_used_at": None,
    }
    cursor = FakeCursor(fetchone_results=[key_row])
    cursor.lastrowid = 10
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.create_api_key(
        name="chat client",
        key_hash="hash123",
        key_fingerprint="abc123",
        roles=["chat"],
        created_by="admin",
    )

    assert result["success"] is True
    assert result["data"]["roles"] == ["chat"]
    assert connection.commit_calls == 1
    insert_query, insert_params = cursor.executed[0]
    assert "INSERT INTO api_keys" in insert_query
    assert insert_params[1] == "hash123"
    assert insert_params[3] == '["chat"]'


def test_find_active_api_key_returns_metadata_and_updates_last_used():
    key_row = {
        "id": 10,
        "name": "chat client",
        "key_fingerprint": "abc123",
        "roles": '["chat"]',
        "status": "active",
        "created_by": "admin",
        "created_at": "2026-05-14 10:00:00",
        "revoked_at": None,
        "expires_at": None,
        "last_used_at": None,
    }
    cursor = FakeCursor(fetchone_results=[key_row])
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.find_active_api_key("hash123")

    assert result["success"] is True
    assert result["data"]["roles"] == ["chat"]
    assert connection.commit_calls == 1
    assert "WHERE key_hash = %s" in cursor.executed[0][0]
    assert "UPDATE api_keys SET last_used_at" in cursor.executed[1][0]


def test_revoke_api_key_updates_status_and_returns_metadata():
    key_row = {
        "id": 10,
        "name": "chat client",
        "key_fingerprint": "abc123",
        "roles": '["chat"]',
        "status": "revoked",
        "created_by": "admin",
        "created_at": "2026-05-14 10:00:00",
        "revoked_at": "2026-05-14 11:00:00",
        "expires_at": None,
        "last_used_at": None,
    }
    cursor = FakeCursor(fetchone_results=[key_row])
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.revoke_api_key(10)

    assert result["success"] is True
    assert result["data"]["status"] == "revoked"
    assert connection.commit_calls == 1
    assert "UPDATE api_keys" in cursor.executed[0][0]


def test_start_agent_session_persists_session_row():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    success = connector.start_agent_session("session-1", "generic")

    assert success is True
    assert connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "INSERT INTO agent_sessions" in query
    assert params == ("session-1", "generic", 0, "active")


def test_end_agent_session_updates_session_row():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    success = connector.end_agent_session(
        session_id="session-1",
        total_iterations=4,
        status="completed",
    )

    assert success is True
    assert connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "UPDATE agent_sessions" in query
    assert params == (4, "completed", "session-1")


def test_log_conversation_context_persists_turn_row():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    success = connector.log_conversation_context(
        session_id="session-1",
        user_query="consulta",
        agent_response="respuesta",
        steps_used=2,
    )

    assert success is True
    assert connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "INSERT INTO conversation_context" in query
    assert params == ("session-1", "consulta", "respuesta", 2)


def test_prune_conversation_context_deletes_old_turns():
    cursor = FakeCursor(rowcount=3)
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.prune_conversation_context(older_than_days=45)

    assert result == {"success": True, "rows_deleted": 3}
    assert connection.commit_calls == 1
    query, params = cursor.executed[0]
    assert "DELETE FROM conversation_context" in query
    assert "timestamp < DATE_SUB" in query
    assert params == (45,)


def test_prune_agent_sessions_deletes_context_before_completed_sessions():
    cursor = FakeCursor(rowcount=2)
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.prune_agent_sessions(older_than_days=60)

    assert result == {
        "success": True,
        "rows_deleted": 2,
        "context_rows_deleted": 2,
    }
    assert connection.commit_calls == 1
    context_query, context_params = cursor.executed[0]
    session_query, session_params = cursor.executed[1]
    assert "DELETE FROM conversation_context" in context_query
    assert "FROM agent_sessions" in context_query
    assert "fin IS NOT NULL" in context_query
    assert "DELETE FROM agent_sessions" in session_query
    assert "fin IS NOT NULL" in session_query
    assert context_params == (60,)
    assert session_params == (60,)


def test_register_brain_decision_persists_adr_row():
    decision_row = {
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
    cursor = FakeCursor(fetchone_results=[decision_row])
    cursor.lastrowid = 99
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.register_brain_decision(
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
    assert result["data"]["id"] == 99
    assert result["data"]["alternatives"] == ["Flask"]
    assert result["data"]["tags"] == ["api", "braincore"]
    assert connection.commit_calls == 1
    insert_query, insert_params = cursor.executed[0]
    assert "INSERT INTO brain_decisions" in insert_query
    assert insert_params[0] == "Usar FastAPI"
    assert insert_params[3] == '["Flask"]'


def test_register_brain_decision_rejects_missing_required_fields():
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = FakeConnection(FakeCursor())
    connector._ensure_connection = lambda: True

    result = connector.register_brain_decision(
        title="",
        context="ctx",
        decision="decision",
        alternatives=[],
        impact="",
    )

    assert result["success"] is False
    assert "requeridos" in result["error"]


def test_list_brain_decisions_applies_filters_and_normalizes_rows():
    rows = [
        {
            "id": 1,
            "title": "Usar FastAPI",
            "context": "Necesitamos API REST",
            "decision": "Exponer ACU via FastAPI",
            "alternatives": '["Flask"]',
            "impact": "Permite clientes externos",
            "domain": "acu",
            "status": "accepted",
            "tags": '["api"]',
            "created_at": "2026-05-14 10:00:00",
            "updated_at": "2026-05-14 10:00:00",
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.list_brain_decisions(
        search="fastapi",
        domain="acu",
        status="accepted",
        limit=5,
    )

    assert result["success"] is True
    assert result["data"][0]["alternatives"] == ["Flask"]
    assert result["data"][0]["tags"] == ["api"]
    query, params = cursor.executed[0]
    assert "FROM brain_decisions" in query
    assert params[-3:] == ("acu", "accepted", 5)


def test_upsert_brain_source_persists_source_and_chunks():
    source_row = {"id": 42, "content_hash": "abc123"}
    cursor = FakeCursor(fetchone_results=[source_row])
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.upsert_brain_source(
        source_path="C:/repo/wiki/decision.md",
        source_type="markdown",
        content_hash="abc123",
        metadata={"domain": "acu"},
        chunks=[
            {
                "chunk_index": 0,
                "chunk_hash": "chunk123",
                "title": "Arquitectura",
                "content": "Usar FastAPI como puente REST.",
                "metadata": {"section": "Arquitectura"},
            }
        ],
    )

    assert result["success"] is True
    assert result["data"]["source_id"] == 42
    assert result["data"]["chunks_indexed"] == 1
    assert connection.commit_calls == 2
    assert "INSERT INTO brain_sources" in cursor.executed[0][0]
    assert "SELECT id, content_hash" in cursor.executed[1][0]
    assert "DELETE FROM brain_chunks" in cursor.executed[2][0]
    assert "INSERT INTO brain_chunks" in cursor.executed[3][0]
    assert cursor.executed[3][1][0] == 42


def test_upsert_brain_source_rejects_read_only_connector():
    connector = mysql_manager.MySQLConnector(use_read_only=True)

    result = connector.upsert_brain_source(
        source_path="file.md",
        source_type="markdown",
        content_hash="abc",
        metadata={},
        chunks=[],
    )

    assert result["success"] is False
    assert "solo lectura" in result["error"]


def test_list_brain_sources_applies_filters_and_counts_chunks():
    rows = [
        {
            "id": 3,
            "source_path": "wiki/api.md",
            "source_type": "markdown",
            "content_hash": "abc123",
            "metadata": '{"domain": "acu"}',
            "status": "indexed",
            "chunks_count": 4,
            "indexed_at": "2026-05-14 10:00:00",
            "updated_at": "2026-05-14 10:05:00",
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.list_brain_sources(
        domain="acu",
        source_type="markdown",
        status="indexed",
        limit=5,
    )

    assert result["success"] is True
    assert result["data"][0]["metadata"] == {"domain": "acu"}
    assert result["data"][0]["chunks_count"] == 4
    query, params = cursor.executed[0]
    assert "FROM brain_sources" in query
    assert "FROM brain_chunks" in query
    assert "JSON_UNQUOTE" in query
    assert params == ("acu", "markdown", "indexed", 5)


def test_get_brain_metrics_returns_aggregate_counts():
    totals = {
        "decisions_count": 2,
        "sources_count": 3,
        "chunks_count": 12,
        "domains_count": 2,
        "last_indexed_at": "2026-05-14 10:00:00",
        "last_updated_at": "2026-05-14 10:05:00",
    }
    domains = [
        {"name": "acu", "sources_count": 2, "chunks_count": 8},
        {"name": "sales", "sources_count": 1, "chunks_count": 4},
    ]
    source_types = [
        {"name": "markdown", "sources_count": 2, "chunks_count": 10},
        {"name": "code", "sources_count": 1, "chunks_count": 2},
    ]
    cursor = FakeCursor(
        fetchone_results=[totals],
        fetchall_results=[domains, source_types],
    )
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.get_brain_metrics()

    assert result["success"] is True
    assert result["data"]["decisions_count"] == 2
    assert result["data"]["sources_count"] == 3
    assert result["data"]["chunks_count"] == 12
    assert result["data"]["domains"][0] == {
        "name": "acu",
        "sources_count": 2,
        "chunks_count": 8,
    }
    assert result["data"]["source_types"][0]["name"] == "markdown"
    assert len(cursor.executed) == 3
    assert "FROM brain_decisions" in cursor.executed[0][0]
    assert "GROUP BY name" in cursor.executed[1][0]


def test_delete_brain_source_removes_source_by_id():
    source_row = {
        "id": 3,
        "source_path": "wiki/api.md",
        "source_type": "markdown",
        "content_hash": "abc123",
        "metadata": '{"domain": "acu"}',
        "status": "indexed",
        "indexed_at": "2026-05-14 10:00:00",
        "updated_at": "2026-05-14 10:05:00",
    }
    cursor = FakeCursor(fetchone_results=[source_row])
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.delete_brain_source(3)

    assert result["success"] is True
    assert result["data"]["source_path"] == "wiki/api.md"
    assert result["data"]["metadata"] == {"domain": "acu"}
    assert connection.commit_calls == 1
    assert "SELECT" in cursor.executed[0][0]
    assert "DELETE FROM brain_sources" in cursor.executed[1][0]
    assert cursor.executed[1][1] == (3,)


def test_delete_brain_source_rejects_read_only_connector():
    connector = mysql_manager.MySQLConnector(use_read_only=True)

    result = connector.delete_brain_source(3)

    assert result["success"] is False
    assert "solo lectura" in result["error"]


def test_search_brain_chunks_ranks_and_filters_results():
    rows = [
        {
            "chunk_id": 1,
            "source_id": 10,
            "chunk_index": 0,
            "title": "Arquitectura API",
            "content": "FastAPI expone ACU como puente REST para clientes externos.",
            "chunk_metadata": '{"section": "Arquitectura API"}',
            "source_path": "wiki/api.md",
            "source_type": "markdown",
            "source_metadata": '{"domain": "acu"}',
            "indexed_at": "2026-05-14 10:00:00",
        },
        {
            "chunk_id": 2,
            "source_id": 11,
            "chunk_index": 0,
            "title": "General",
            "content": "Contenido no relacionado",
            "chunk_metadata": "{}",
            "source_path": "wiki/general.md",
            "source_type": "markdown",
            "source_metadata": '{"domain": "acu"}',
            "indexed_at": "2026-05-14 09:00:00",
        },
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.search_brain_chunks(
        query_text="fastapi rest",
        domain="acu",
        source_type="markdown",
        limit=1,
    )

    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["chunk_id"] == 1
    assert result["data"][0]["source_path"] == "wiki/api.md"
    assert result["data"][0]["metadata"]["source"]["domain"] == "acu"
    query, params = cursor.executed[0]
    assert "FROM brain_chunks" in query
    assert "JSON_UNQUOTE" in query
    assert params[-3:] == ("acu", "markdown", 10)


def test_search_brain_chunks_returns_empty_for_blank_query():
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(FakeCursor())
    connector._ensure_connection = lambda: True

    result = connector.search_brain_chunks(query_text=" ")

    assert result == {"success": True, "data": []}


def test_list_agent_sessions_applies_filters():
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
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.list_agent_sessions(domain="acu", status="active", limit=5)

    assert result["success"] is True
    assert result["data"] == rows
    query, params = cursor.executed[0]
    assert "FROM agent_sessions" in query
    assert params == ("acu", "active", 5)


def test_get_conversation_context_lists_turns():
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
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.get_conversation_context(session_id="session-1", limit=10)

    assert result["success"] is True
    assert result["data"] == rows
    query, params = cursor.executed[0]
    assert "FROM conversation_context" in query
    assert params == ("session-1", 10)


def test_list_tool_executions_normalizes_json_fields():
    rows = [
        {
            "id": 1,
            "tool_name": "buscar_contexto_braincore",
            "parameters": '{"consulta": "fastapi"}',
            "result": '{"success": true}',
            "execution_time_ms": 12,
            "success": 1,
            "executed_at": "2026-05-14 10:00:00",
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.list_tool_executions(
        tool_name="buscar_contexto_braincore",
        success=True,
        limit=7,
    )

    assert result["success"] is True
    assert result["data"][0]["parameters"] == {"consulta": "fastapi"}
    assert result["data"][0]["result"] == {"success": True}
    assert result["data"][0]["success"] is True
    query, params = cursor.executed[0]
    assert "FROM tool_execution_log" in query
    assert params == ("buscar_contexto_braincore", True, 7)


def test_list_api_access_log_applies_filters_and_normalizes_rows():
    rows = [
        {
            "id": 1,
            "method": "POST",
            "path": "/chat",
            "status_code": 200,
            "key_fingerprint": "abc123",
            "roles": '["chat"]',
            "client_ip": "127.0.0.1",
            "user_agent": "testclient",
            "authorized": 1,
            "duration_ms": 14,
            "accessed_at": "2026-05-14 10:00:00",
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.list_api_access_log(
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


def test_list_api_keys_filters_and_normalizes_rows():
    rows = [
        {
            "id": 10,
            "name": "chat client",
            "key_fingerprint": "abc123",
            "roles": '["chat"]',
            "status": "active",
            "created_by": "admin",
            "created_at": "2026-05-14 10:00:00",
            "revoked_at": None,
            "expires_at": None,
            "last_used_at": None,
        }
    ]
    cursor = FakeCursor(fetchall_results=[rows])
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.list_api_keys(status="active", limit=3)

    assert result["success"] is True
    assert result["data"][0]["roles"] == ["chat"]
    query, params = cursor.executed[0]
    assert "FROM api_keys" in query
    assert params == ("active", 3)


def test_export_brain_domain_returns_decisions_sources_and_chunks():
    decision_rows = [
        {
            "id": 7,
            "title": "Usar FastAPI",
            "context": "Necesitamos API REST",
            "decision": "Exponer ACU via FastAPI",
            "alternatives": '["Flask"]',
            "impact": "Permite clientes externos",
            "domain": "acu",
            "status": "accepted",
            "tags": '["api"]',
            "created_at": "2026-05-14 10:00:00",
            "updated_at": "2026-05-14 10:00:00",
        }
    ]
    source_rows = [
        {
            "id": 3,
            "source_path": "wiki/api.md",
            "source_type": "markdown",
            "content_hash": "abc123",
            "metadata": '{"domain":"acu"}',
            "status": "indexed",
            "indexed_at": "2026-05-14 10:00:00",
            "updated_at": "2026-05-14 10:05:00",
            "chunks_count": 1,
        }
    ]
    chunk_rows = [
        {
            "id": 9,
            "source_id": 3,
            "chunk_index": 0,
            "chunk_hash": "chunk123",
            "title": "API",
            "content": "FastAPI expone ACU.",
            "metadata": '{"domain":"acu"}',
            "indexed_at": "2026-05-14 10:00:00",
            "source_path": "wiki/api.md",
            "source_type": "markdown",
        }
    ]
    cursor = FakeCursor(fetchall_results=[decision_rows, source_rows, chunk_rows])
    connector = mysql_manager.MySQLConnector(use_read_only=True)
    connector.connection = FakeConnection(cursor)
    connector._ensure_connection = lambda: True

    result = connector.export_brain_domain(domain="acu", include_chunks=True)

    assert result["success"] is True
    assert result["data"]["domain"] == "acu"
    assert result["data"]["decisions_count"] == 1
    assert result["data"]["sources_count"] == 1
    assert result["data"]["chunks_count"] == 1
    assert result["data"]["decisions"][0]["alternatives"] == ["Flask"]
    assert result["data"]["sources"][0]["metadata"] == {"domain": "acu"}
    assert result["data"]["chunks"][0]["metadata"] == {"domain": "acu"}
    assert len(cursor.executed) == 3
    assert cursor.executed[0][1] == ("acu",)
    assert cursor.executed[1][1] == ("acu",)
    assert cursor.executed[2][1] == ("acu",)


def test_delete_brain_domain_deletes_sources_chunks_and_optional_decisions():
    source_rows = [
        {"id": 3, "source_path": "wiki/api.md"},
        {"id": 4, "source_path": "wiki/ops.md"},
    ]
    cursor = FakeCursor(fetchall_results=[source_rows], rowcounts=[0, 8, 2, 1])
    connection = FakeConnection(cursor)
    connector = mysql_manager.MySQLConnector(use_read_only=False)
    connector.connection = connection
    connector._ensure_connection = lambda: True

    result = connector.delete_brain_domain(domain="acu", delete_decisions=True)

    assert result["success"] is True
    assert result["data"] == {
        "domain": "acu",
        "sources_deleted": 2,
        "chunks_deleted": 8,
        "decisions_deleted": 1,
        "vector_sources_deleted": 0,
        "deleted_source_paths": ["wiki/api.md", "wiki/ops.md"],
    }
    assert connection.commit_calls == 1
    assert "FROM brain_sources" in cursor.executed[0][0]
    assert "DELETE FROM brain_chunks" in cursor.executed[1][0]
    assert cursor.executed[1][1] == (3, 4)
    assert "DELETE FROM brain_sources" in cursor.executed[2][0]
    assert cursor.executed[2][1] == (3, 4)
    assert "DELETE FROM brain_decisions" in cursor.executed[3][0]
    assert cursor.executed[3][1] == ("acu",)
