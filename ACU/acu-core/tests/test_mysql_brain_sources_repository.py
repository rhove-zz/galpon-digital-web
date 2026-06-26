from src.memory.repositories.brain_sources import BrainSourceRepository


class FakeCursor:
    def __init__(self, fetchall_results=None, fetchone_results=None):
        self.fetchall_results = list(fetchall_results or [])
        self.fetchone_results = list(fetchone_results or [])
        self.executed = []
        self.closed = False

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


def _source_row(chunks_count=4):
    return {
        "id": 3,
        "source_path": "wiki/api.md",
        "source_type": "markdown",
        "content_hash": "abc123",
        "metadata": '{"domain": "acu"}',
        "status": "indexed",
        "chunks_count": chunks_count,
        "indexed_at": "2026-05-14 10:00:00",
        "updated_at": "2026-05-14 10:05:00",
    }


def test_brain_source_repository_upserts_source_and_chunks():
    cursor = FakeCursor(fetchone_results=[{"id": 42, "content_hash": "abc123"}])
    connector = FakeConnector(cursor)
    repository = BrainSourceRepository(connector)

    result = repository.upsert_brain_source(
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
    assert result["data"] == {
        "source_id": 42,
        "source_path": "C:/repo/wiki/decision.md",
        "chunks_indexed": 1,
    }
    assert connector.connection.commit_calls == 2
    assert "INSERT INTO brain_sources" in cursor.executed[0][0]
    assert "SELECT id, content_hash" in cursor.executed[1][0]
    assert "DELETE FROM brain_chunks" in cursor.executed[2][0]
    assert "INSERT INTO brain_chunks" in cursor.executed[3][0]
    assert cursor.executed[3][1][0] == 42


def test_brain_source_repository_rejects_invalid_or_read_only_writes():
    writable_repository = BrainSourceRepository(FakeConnector(FakeCursor()))
    read_only_repository = BrainSourceRepository(
        FakeConnector(FakeCursor(), use_read_only=True)
    )

    invalid = writable_repository.upsert_brain_source(
        source_path="",
        source_type="markdown",
        content_hash="abc",
        metadata={},
        chunks=[],
    )
    read_only = read_only_repository.upsert_brain_source(
        source_path="file.md",
        source_type="markdown",
        content_hash="abc",
        metadata={},
        chunks=[],
    )
    deleted = read_only_repository.delete_brain_source(3)

    assert invalid["success"] is False
    assert "requeridos" in invalid["error"]
    assert read_only["success"] is False
    assert "solo lectura" in read_only["error"]
    assert deleted["success"] is False
    assert "solo lectura" in deleted["error"]


def test_brain_source_repository_returns_error_when_upserted_source_is_missing():
    cursor = FakeCursor(fetchone_results=[None])
    repository = BrainSourceRepository(FakeConnector(cursor))

    result = repository.upsert_brain_source(
        source_path="file.md",
        source_type="markdown",
        content_hash="abc",
        metadata={},
        chunks=[],
    )

    assert result["success"] is False
    assert "recuperar" in result["error"]
    assert cursor.closed is True


def test_brain_source_repository_lists_sources_with_filters_and_limit_bounds():
    cursor = FakeCursor(fetchall_results=[[_source_row()]])
    repository = BrainSourceRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.list_brain_sources(
        domain="acu",
        source_type="markdown",
        status="indexed",
        limit=500,
    )

    assert result["success"] is True
    assert result["data"][0]["metadata"] == {"domain": "acu"}
    assert result["data"][0]["chunks_count"] == 4
    query, params = cursor.executed[0]
    assert "FROM brain_sources" in query
    assert "FROM brain_chunks" in query
    assert "JSON_UNQUOTE" in query
    assert params == ("acu", "markdown", "indexed", 100)


def test_brain_source_repository_deletes_source_and_normalizes_payload():
    cursor = FakeCursor(fetchone_results=[_source_row(chunks_count=0)])
    connector = FakeConnector(cursor)
    repository = BrainSourceRepository(connector)

    result = repository.delete_brain_source(3)

    assert result["success"] is True
    assert result["data"]["source_path"] == "wiki/api.md"
    assert result["data"]["metadata"] == {"domain": "acu"}
    assert result["data"]["chunks_count"] == 0
    assert connector.connection.commit_calls == 1
    assert "SELECT" in cursor.executed[0][0]
    assert "DELETE FROM brain_sources" in cursor.executed[1][0]
    assert cursor.executed[1][1] == (3,)


def test_brain_source_repository_delete_reports_missing_source():
    cursor = FakeCursor(fetchone_results=[None])
    repository = BrainSourceRepository(FakeConnector(cursor))

    result = repository.delete_brain_source(404)

    assert result["success"] is False
    assert "no encontrada" in result["error"]
    assert cursor.closed is True


def test_brain_source_repository_returns_connection_errors():
    repository = BrainSourceRepository(FakeConnector(FakeCursor(), connected=False))

    upserted = repository.upsert_brain_source("file.md", "markdown", "abc", {}, [])
    listed = repository.list_brain_sources()
    deleted = repository.delete_brain_source(3)

    assert upserted["success"] is False
    assert "conexion" in upserted["error"]
    assert listed["success"] is False
    assert "conexion" in listed["error"]
    assert deleted["success"] is False
    assert "conexion" in deleted["error"]
