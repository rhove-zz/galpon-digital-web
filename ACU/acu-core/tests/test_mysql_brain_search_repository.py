from src.memory.repositories.brain_search import BrainSearchRepository


class FakeCursor:
    def __init__(self, fetchall_results=None):
        self.fetchall_results = list(fetchall_results or [])
        self.executed = []
        self.closed = False

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

    def cursor(self, dictionary=False):
        return self._cursor


class FakeConnector:
    def __init__(self, cursor, connected=True):
        self.connection = FakeConnection(cursor)
        self.connected = connected

    def _ensure_connection(self):
        return self.connected


def _candidate_rows():
    return [
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


def test_brain_search_repository_ranks_and_filters_results():
    cursor = FakeCursor(fetchall_results=[_candidate_rows()])
    repository = BrainSearchRepository(FakeConnector(cursor))

    result = repository.search_brain_chunks(
        query_text="fastapi rest",
        domain="acu",
        source_type="markdown",
        limit=1,
    )

    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["chunk_id"] == 1
    assert result["data"][0]["source_path"] == "wiki/api.md"
    assert result["data"][0]["metadata"]["chunk"] == {"section": "Arquitectura API"}
    assert result["data"][0]["metadata"]["source"]["domain"] == "acu"
    query, params = cursor.executed[0]
    assert "FROM brain_chunks" in query
    assert "JSON_UNQUOTE" in query
    assert params[-3:] == ("acu", "markdown", 10)
    assert cursor.closed is True


def test_brain_search_repository_returns_empty_for_blank_query():
    cursor = FakeCursor()
    repository = BrainSearchRepository(FakeConnector(cursor))

    result = repository.search_brain_chunks(query_text=" ")

    assert result == {"success": True, "data": []}
    assert cursor.executed == []


def test_brain_search_repository_caps_candidate_query_limit():
    cursor = FakeCursor(fetchall_results=[_candidate_rows()])
    repository = BrainSearchRepository(FakeConnector(cursor))

    result = repository.search_brain_chunks(query_text="fastapi", limit=100)

    assert result["success"] is True
    assert cursor.executed[0][1][-1] == 200


def test_brain_search_repository_returns_connection_error():
    repository = BrainSearchRepository(FakeConnector(FakeCursor(), connected=False))

    result = repository.search_brain_chunks(query_text="fastapi")

    assert result["success"] is False
    assert "conexion" in result["error"]
