import os
from uuid import uuid4

import pytest

from src.memory import mysql_manager


pytestmark = pytest.mark.integration_mysql


@pytest.fixture
def mysql_integration(monkeypatch):
    """Provide real MySQL connectors configured for the integration test DB."""
    monkeypatch.setattr(
        mysql_manager.mysql_config,
        "host",
        _env("MYSQL_HOST", "localhost"),
    )
    monkeypatch.setattr(
        mysql_manager.mysql_config,
        "port",
        int(_env("MYSQL_PORT", "3306")),
    )
    monkeypatch.setattr(
        mysql_manager.mysql_config,
        "database",
        _env("MYSQL_DATABASE", "acu_db"),
    )
    monkeypatch.setattr(
        mysql_manager.mysql_config,
        "user",
        _env("MYSQL_USER", "root"),
    )
    monkeypatch.setattr(
        mysql_manager.mysql_config,
        "password",
        _env("MYSQL_PASSWORD", "root"),
    )
    monkeypatch.setattr(
        mysql_manager.mysql_config,
        "read_only_user",
        _env("MYSQL_READ_ONLY_USER", "acu_reader"),
    )
    monkeypatch.setattr(
        mysql_manager.mysql_config,
        "read_only_password",
        _env("MYSQL_READ_ONLY_PASSWORD", "acu_secure_read_only"),
    )

    writer = mysql_manager.MySQLConnector(use_read_only=False)
    reader = mysql_manager.MySQLConnector(use_read_only=True)
    cleanup_statements = []

    if not writer.connect():
        pytest.fail(
            "No se pudo conectar a MySQL de escritura. "
            "Levanta `docker compose -f docker/docker-compose.yml up -d mysql` "
            "o ajusta ACU_TEST_MYSQL_*."
        )
    if not reader.connect():
        writer.disconnect()
        pytest.fail(
            "No se pudo conectar a MySQL read-only. "
            "Verifica usuario acu_reader y password acu_secure_read_only."
        )

    try:
        yield reader, writer, cleanup_statements
    finally:
        _cleanup(writer, cleanup_statements)
        reader.disconnect()
        writer.disconnect()


def test_mysql_integration_schema_and_read_only_user(mysql_integration):
    reader, writer, _cleanup_statements = mysql_integration

    schema = reader.get_database_schema()
    assert schema is not None
    assert "memoria_evolutiva" in schema.tables
    assert "brain_sources" in schema.tables
    assert "api_keys" in schema.tables

    result = reader.execute_read_query(
        "SELECT COUNT(*) AS total FROM memoria_evolutiva"
    )
    assert result["success"] is True
    assert "total" in result["data"][0]

    rejected = reader.execute_read_query(
        "INSERT INTO memoria_evolutiva (categoria, leccion_aprendida) VALUES ('x', 'y')"
    )
    assert rejected["success"] is False
    assert "Solo se permiten queries SELECT" in rejected["error"]

    read_only_write = reader.register_lesson("integration", "no debe escribir")
    assert read_only_write["success"] is False
    assert "solo lectura" in read_only_write["error"]

    write_result = writer.execute_read_query("SELECT 1 AS ok")
    assert write_result["success"] is True


def test_mysql_integration_braincore_round_trip(mysql_integration):
    reader, writer, cleanup_statements = mysql_integration
    suffix = uuid4().hex
    domain = f"integration-{suffix}"
    title = f"ADR integracion MySQL {suffix}"
    source_path = f"integration/mysql/{suffix}.md"

    cleanup_statements.extend(
        [
            ("DELETE FROM brain_sources WHERE source_path = %s", (source_path,)),
            ("DELETE FROM brain_decisions WHERE titulo = %s", (title,)),
        ]
    )

    decision = writer.register_brain_decision(
        title=title,
        context="Validar persistencia real MySQL",
        decision="Usar prueba de integracion opt-in",
        alternatives=["solo fakes"],
        impact="Aumenta confianza del esquema real",
        domain=domain,
        status="accepted",
        tags=["integration", "mysql"],
    )
    assert_success(decision)
    assert decision["data"]["title"] == title

    listed_decisions = reader.list_brain_decisions(
        search=suffix,
        domain=domain,
        status="accepted",
        limit=5,
    )
    assert_success(listed_decisions)
    assert listed_decisions["data"][0]["title"] == title

    upsert = writer.upsert_brain_source(
        source_path=source_path,
        source_type="markdown",
        content_hash=f"{suffix[:32]}{suffix[:32]}",
        metadata={"domain": domain},
        chunks=[
            {
                "chunk_index": 0,
                "chunk_hash": f"{suffix[:32]}{suffix[:32]}",
                "title": "Prueba integracion MySQL",
                "content": f"FastAPI BrainCore MySQL integration {suffix}",
                "metadata": {"section": "integration"},
            }
        ],
    )
    assert_success(upsert)
    source_id = upsert["data"]["source_id"]
    assert upsert["data"]["chunks_indexed"] == 1

    sources = reader.list_brain_sources(domain=domain, limit=5)
    assert_success(sources)
    assert sources["data"][0]["source_path"] == source_path
    assert sources["data"][0]["chunks_count"] == 1

    search = reader.search_brain_chunks(
        query_text=f"BrainCore integration {suffix}",
        domain=domain,
        source_type="markdown",
        limit=3,
    )
    assert_success(search)
    assert search["data"][0]["source_path"] == source_path
    assert search["data"][0]["metadata"]["source"]["domain"] == domain

    metrics = reader.get_brain_metrics()
    assert_success(metrics)
    assert metrics["data"]["sources_count"] >= 1
    assert metrics["data"]["chunks_count"] >= 1

    deleted = writer.delete_brain_source(source_id)
    assert_success(deleted)
    assert deleted["data"]["source_path"] == source_path


def test_mysql_integration_audit_sessions_and_api_keys_round_trip(mysql_integration):
    reader, writer, cleanup_statements = mysql_integration
    suffix = uuid4().hex
    domain = f"integration-{suffix}"
    session_id = f"session-{suffix}"
    tool_name = f"integration_tool_{suffix}"
    access_path = f"/integration/{suffix}"
    key_hash = f"{suffix[:32]}{suffix[:32]}"
    key_fingerprint = suffix[:16]

    cleanup_statements.extend(
        [
            ("DELETE FROM conversation_context WHERE session_id = %s", (session_id,)),
            ("DELETE FROM agent_sessions WHERE session_id = %s", (session_id,)),
            (
                "DELETE FROM tool_execution_log WHERE nombre_herramienta = %s",
                (tool_name,),
            ),
            ("DELETE FROM api_access_log WHERE path = %s", (access_path,)),
            ("DELETE FROM api_keys WHERE key_hash = %s", (key_hash,)),
        ]
    )

    assert writer.start_agent_session(session_id, domain) is True
    assert (
        writer.log_conversation_context(
            session_id=session_id,
            user_query="hola integracion",
            agent_response="respuesta integracion",
            steps_used=2,
        )
        is True
    )
    assert (
        writer.end_agent_session(
            session_id=session_id,
            total_iterations=2,
            status="completed",
        )
        is True
    )

    sessions = reader.list_agent_sessions(domain=domain, status="completed", limit=5)
    assert_success(sessions)
    assert sessions["data"][0]["session_id"] == session_id

    context = reader.get_conversation_context(session_id=session_id, limit=5)
    assert_success(context)
    assert context["data"][0]["user_query"] == "hola integracion"

    assert (
        writer.log_tool_execution(
            tool_name=tool_name,
            parameters={"query": "SELECT 1"},
            result={"success": True},
            execution_time_ms=8.7,
            success=True,
        )
        is True
    )
    tools = reader.list_tool_executions(tool_name=tool_name, success=True, limit=5)
    assert_success(tools)
    assert tools["data"][0]["tool_name"] == tool_name
    assert tools["data"][0]["parameters"]["query"] == "SELECT 1"

    assert (
        writer.log_api_access(
            method="GET",
            path=access_path,
            status_code=200,
            key_fingerprint=key_fingerprint,
            roles=["monitoring"],
            client_ip="127.0.0.1",
            user_agent="pytest",
            authorized=True,
            duration_ms=3.4,
        )
        is True
    )
    access_log = reader.list_api_access_log(path=access_path, authorized=True, limit=5)
    assert_success(access_log)
    assert access_log["data"][0]["roles"] == ["monitoring"]

    created_key = writer.create_api_key(
        name=f"integration key {suffix}",
        key_hash=key_hash,
        key_fingerprint=key_fingerprint,
        roles=["chat", "monitoring"],
        created_by="pytest",
    )
    assert_success(created_key)
    assert created_key["data"]["roles"] == ["chat", "monitoring"]

    active_key = writer.find_active_api_key(key_hash)
    assert_success(active_key)
    assert active_key["data"]["key_fingerprint"] == key_fingerprint

    revoked = writer.revoke_api_key(created_key["data"]["id"])
    assert_success(revoked)
    assert revoked["data"]["status"] == "revoked"


def assert_success(result):
    assert result["success"] is True, result.get("error")


def _env(name: str, default: str) -> str:
    return os.getenv(f"ACU_TEST_{name}") or os.getenv(name) or default


def _cleanup(connector, statements):
    if not connector.is_connected():
        return
    cursor = connector.connection.cursor()
    for query, params in statements:
        try:
            cursor.execute(query, params)
        except Exception:
            continue
    connector.connection.commit()
    cursor.close()
