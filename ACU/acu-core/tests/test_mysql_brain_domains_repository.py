from src.memory.repositories.brain_domains import BrainDomainRepository


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


def _decision_rows():
    return [
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


def _source_rows():
    return [
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


def _chunk_rows():
    return [
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


def test_brain_domain_repository_exports_domain_with_chunks():
    cursor = FakeCursor(
        fetchall_results=[_decision_rows(), _source_rows(), _chunk_rows()]
    )
    repository = BrainDomainRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.export_brain_domain(domain="acu", include_chunks=True)

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


def test_brain_domain_repository_exports_without_chunks_using_source_counts():
    cursor = FakeCursor(fetchall_results=[_decision_rows(), _source_rows()])
    repository = BrainDomainRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.export_brain_domain(domain="acu", include_chunks=False)

    assert result["success"] is True
    assert result["data"]["chunks_count"] == 1
    assert result["data"]["chunks"] == []
    assert len(cursor.executed) == 2


def test_brain_domain_repository_deletes_sources_chunks_and_decisions():
    source_rows = [
        {"id": 3, "source_path": "wiki/api.md"},
        {"id": 4, "source_path": "wiki/ops.md"},
    ]
    cursor = FakeCursor(fetchall_results=[source_rows], rowcounts=[0, 8, 2, 1])
    connector = FakeConnector(cursor)
    repository = BrainDomainRepository(connector)

    result = repository.delete_brain_domain(domain="acu", delete_decisions=True)

    assert result["success"] is True
    assert result["data"] == {
        "domain": "acu",
        "sources_deleted": 2,
        "chunks_deleted": 8,
        "decisions_deleted": 1,
        "vector_sources_deleted": 0,
        "deleted_source_paths": ["wiki/api.md", "wiki/ops.md"],
    }
    assert connector.connection.commit_calls == 1
    assert "FROM brain_sources" in cursor.executed[0][0]
    assert "DELETE FROM brain_chunks" in cursor.executed[1][0]
    assert cursor.executed[1][1] == (3, 4)
    assert "DELETE FROM brain_sources" in cursor.executed[2][0]
    assert cursor.executed[2][1] == (3, 4)
    assert "DELETE FROM brain_decisions" in cursor.executed[3][0]
    assert cursor.executed[3][1] == ("acu",)


def test_brain_domain_repository_deletes_empty_domain_without_decisions():
    cursor = FakeCursor(fetchall_results=[[]])
    connector = FakeConnector(cursor)
    repository = BrainDomainRepository(connector)

    result = repository.delete_brain_domain(domain="acu", delete_decisions=False)

    assert result["success"] is True
    assert result["data"]["sources_deleted"] == 0
    assert result["data"]["chunks_deleted"] == 0
    assert result["data"]["decisions_deleted"] == 0
    assert result["data"]["deleted_source_paths"] == []
    assert len(cursor.executed) == 1
    assert connector.connection.commit_calls == 1


def test_brain_domain_repository_rejects_read_only_delete_and_connection_errors():
    read_only = BrainDomainRepository(FakeConnector(FakeCursor(), use_read_only=True))
    disconnected = BrainDomainRepository(FakeConnector(FakeCursor(), connected=False))

    read_only_delete = read_only.delete_brain_domain(domain="acu")
    disconnected_delete = disconnected.delete_brain_domain(domain="acu")
    disconnected_export = disconnected.export_brain_domain(domain="acu")

    assert read_only_delete["success"] is False
    assert "solo lectura" in read_only_delete["error"]
    assert disconnected_delete["success"] is False
    assert "conexion" in disconnected_delete["error"]
    assert disconnected_export["success"] is False
    assert "conexion" in disconnected_export["error"]
