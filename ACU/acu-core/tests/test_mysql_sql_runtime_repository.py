from mysql.connector import Error

from src.memory.repositories.sql_runtime import SqlRuntimeRepository
from src.utils.schemas import DatabaseSchema


class FakeCursor:
    def __init__(self, fetchall_results=None, execute_error=None):
        self.fetchall_results = list(fetchall_results or [])
        self.execute_error = execute_error
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        if self.execute_error:
            raise self.execute_error
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
    def __init__(self, cursor=None, connected=True):
        self.connection = FakeConnection(cursor or FakeCursor())
        self.schema_cache = None
        self.connected = connected

    def _ensure_connection(self):
        return self.connected


def test_get_database_schema_builds_and_caches_schema():
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
            [
                {
                    "COLUMN_NAME": "empresa_id",
                    "REFERENCED_TABLE_NAME": "empresas",
                    "REFERENCED_COLUMN_NAME": "id",
                }
            ],
        ]
    )
    connector = FakeConnector(cursor)
    repository = SqlRuntimeRepository(connector)

    schema = repository.get_database_schema()
    cached_schema = repository.get_database_schema()

    assert schema is connector.schema_cache
    assert cached_schema is schema
    assert "usuarios" in schema.tables
    assert schema.tables["usuarios"]["columns"][0]["COLUMN_NAME"] == "id"
    assert len(cursor.executed) == 3


def test_get_database_schema_returns_none_without_connection():
    repository = SqlRuntimeRepository(FakeConnector(connected=False))

    result = repository.get_database_schema()

    assert result is None


def test_execute_read_query_rejects_non_select():
    cursor = FakeCursor()
    repository = SqlRuntimeRepository(FakeConnector(cursor))

    result = repository.execute_read_query("DELETE FROM usuarios")

    assert result["success"] is False
    assert "Solo se permiten queries SELECT" in result["error"]
    assert cursor.executed == []


def test_execute_read_query_returns_rows_and_count():
    cursor = FakeCursor(fetchall_results=[[{"ok": 1}, {"ok": 2}]])
    repository = SqlRuntimeRepository(FakeConnector(cursor))

    result = repository.execute_read_query("SELECT ok FROM checks")

    assert result == {
        "success": True,
        "data": [{"ok": 1}, {"ok": 2}],
        "rows_affected": 2,
    }
    assert cursor.closed is True


def test_execute_read_query_reports_mysql_error():
    repository = SqlRuntimeRepository(
        FakeConnector(FakeCursor(execute_error=Error("syntax error")))
    )

    result = repository.execute_read_query("SELECT * FROM broken")

    assert result["success"] is False
    assert result["error"] == "syntax error"
    assert "suggestion" in result


def test_format_schema_for_prompt_uses_cached_schema():
    connector = FakeConnector()
    connector.schema_cache = DatabaseSchema(
        database="acu",
        tables={
            "usuarios": {
                "columns": [
                    {
                        "COLUMN_NAME": "id",
                        "COLUMN_TYPE": "int",
                        "IS_NULLABLE": "NO",
                        "COLUMN_KEY": "PRI",
                    },
                    {
                        "COLUMN_NAME": "nombre",
                        "COLUMN_TYPE": "varchar(255)",
                        "IS_NULLABLE": "YES",
                        "COLUMN_KEY": "",
                    },
                ],
                "foreign_keys": [
                    {
                        "COLUMN_NAME": "empresa_id",
                        "REFERENCED_TABLE_NAME": "empresas",
                        "REFERENCED_COLUMN_NAME": "id",
                    }
                ],
            }
        },
    )
    repository = SqlRuntimeRepository(connector)

    result = repository.format_schema_for_prompt()

    assert "## SCHEMA DE BASE DE DATOS: acu" in result
    assert "### Tabla: usuarios" in result
    assert "id: int NOT NULL [PRI]" in result
    assert "nombre: varchar(255) NULL" in result
    assert "empresa_id -> empresas.id" in result
