from src.memory.repositories.lessons import LessonsRepository


class FakeCursor:
    def __init__(self, fetchall_results=None, fetchone_results=None):
        self.fetchall_results = list(fetchall_results or [])
        self.fetchone_results = list(fetchone_results or [])
        self.executed = []
        self.executemany_calls = []
        self.closed = False
        self.lastrowid = 99

    def execute(self, query, params=None):
        self.executed.append((query, params))

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


def test_lessons_repository_registers_lesson():
    lesson_row = {
        "id": 99,
        "categoria": "error_handling",
        "leccion_aprendida": "Revisar aliases",
        "fecha_registro": "2026-04-25 10:00:00",
        "relevancia": 3,
        "veces_utilizada": 0,
    }
    cursor = FakeCursor(fetchone_results=[lesson_row])
    connector = FakeConnector(cursor)
    repository = LessonsRepository(connector)

    result = repository.register_lesson(
        "error_handling", "Revisar aliases", relevancia=3
    )

    assert result["success"] is True
    assert result["data"]["id"] == 99
    assert connector.connection.commit_calls == 1
    assert len(cursor.executed) == 2
    assert "INSERT INTO memoria_evolutiva" in cursor.executed[0][0]


def test_lessons_repository_rejects_read_only_writes_and_empty_usage():
    repository = LessonsRepository(FakeConnector(FakeCursor(), use_read_only=True))

    registered = repository.register_lesson("cat", "desc")
    incremented = repository.increment_lesson_usage([1])
    empty_increment = LessonsRepository(
        FakeConnector(FakeCursor())
    ).increment_lesson_usage([])

    assert registered["success"] is False
    assert "solo lectura" in registered["error"]
    assert incremented is False
    assert empty_increment is False


def test_lessons_repository_query_ranks_and_limits_results():
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
    repository = LessonsRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.query_lessons("sql indices", limit=1)

    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["id"] == 1
    assert result["data"][0]["score"] > 0
    assert cursor.executed[0][1][-1] == 10


def test_lessons_repository_query_returns_empty_for_blank_terms():
    cursor = FakeCursor()
    repository = LessonsRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.query_lessons(" ")

    assert result == {"success": True, "data": []}
    assert cursor.executed == []


def test_lessons_repository_increment_usage_updates_rows():
    cursor = FakeCursor()
    connector = FakeConnector(cursor)
    repository = LessonsRepository(connector)

    result = repository.increment_lesson_usage([1, 2])

    assert result is True
    assert connector.connection.commit_calls == 1
    query, values = cursor.executemany_calls[0]
    assert "UPDATE memoria_evolutiva" in query
    assert values == [(1,), (2,)]


def test_lessons_repository_returns_connection_errors():
    repository = LessonsRepository(FakeConnector(FakeCursor(), connected=False))

    registered = repository.register_lesson("cat", "desc")
    queried = repository.query_lessons("sql")
    incremented = repository.increment_lesson_usage([1])

    assert registered["success"] is False
    assert "conexion" in registered["error"]
    assert queried["success"] is False
    assert "conexion" in queried["error"]
    assert incremented is False
