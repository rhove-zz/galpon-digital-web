from src.memory.repositories.brain_metrics import BrainMetricsRepository


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

    def cursor(self, dictionary=False):
        return self._cursor


class FakeConnector:
    def __init__(self, cursor, connected=True):
        self.connection = FakeConnection(cursor)
        self.connected = connected

    def _ensure_connection(self):
        return self.connected


def test_brain_metrics_repository_returns_aggregate_counts():
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
    repository = BrainMetricsRepository(FakeConnector(cursor))

    result = repository.get_brain_metrics()

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
    assert cursor.closed is True


def test_brain_metrics_repository_normalizes_empty_totals():
    cursor = FakeCursor(fetchone_results=[None], fetchall_results=[[], []])
    repository = BrainMetricsRepository(FakeConnector(cursor))

    result = repository.get_brain_metrics()

    assert result["success"] is True
    assert result["data"] == {
        "decisions_count": 0,
        "sources_count": 0,
        "chunks_count": 0,
        "domains_count": 0,
        "last_indexed_at": None,
        "last_updated_at": None,
        "domains": [],
        "source_types": [],
    }


def test_brain_metrics_repository_returns_connection_error():
    repository = BrainMetricsRepository(FakeConnector(FakeCursor(), connected=False))

    result = repository.get_brain_metrics()

    assert result["success"] is False
    assert "conexion" in result["error"]
