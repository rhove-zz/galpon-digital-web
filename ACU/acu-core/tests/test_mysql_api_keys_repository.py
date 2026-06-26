from src.memory.repositories.api_keys import ApiKeyRepository


class FakeCursor:
    def __init__(self, fetchall_results=None, fetchone_results=None):
        self.fetchall_results = list(fetchall_results or [])
        self.fetchone_results = list(fetchone_results or [])
        self.executed = []
        self.closed = False
        self.lastrowid = 10

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


def _api_key_row(status="active"):
    return {
        "id": 10,
        "name": "chat client",
        "key_fingerprint": "abc123",
        "roles": '["chat"]',
        "status": status,
        "created_by": "admin",
        "created_at": "2026-05-14 10:00:00",
        "revoked_at": "2026-05-14 11:00:00" if status == "revoked" else None,
        "expires_at": None,
        "last_used_at": None,
    }


def test_api_key_repository_creates_key_and_normalizes_roles():
    cursor = FakeCursor(fetchone_results=[_api_key_row()])
    connector = FakeConnector(cursor)
    repository = ApiKeyRepository(connector)

    result = repository.create_api_key(
        name="chat client",
        key_hash="hash123",
        key_fingerprint="abc123",
        roles=["chat"],
        created_by="admin",
    )

    assert result["success"] is True
    assert result["data"]["roles"] == ["chat"]
    assert connector.connection.commit_calls == 1
    insert_query, insert_params = cursor.executed[0]
    assert "INSERT INTO api_keys" in insert_query
    assert insert_params[1] == "hash123"
    assert insert_params[3] == '["chat"]'


def test_api_key_repository_rejects_writes_on_read_only_connector():
    repository = ApiKeyRepository(FakeConnector(FakeCursor(), use_read_only=True))

    created = repository.create_api_key(
        name="chat client",
        key_hash="hash123",
        key_fingerprint="abc123",
        roles=["chat"],
    )
    revoked = repository.revoke_api_key(10)

    assert created["success"] is False
    assert "solo lectura" in created["error"]
    assert revoked["success"] is False
    assert "solo lectura" in revoked["error"]


def test_api_key_repository_finds_active_key_and_updates_last_used():
    cursor = FakeCursor(fetchone_results=[_api_key_row()])
    connector = FakeConnector(cursor)
    repository = ApiKeyRepository(connector)

    result = repository.find_active_api_key("hash123")

    assert result["success"] is True
    assert result["data"]["key_fingerprint"] == "abc123"
    assert connector.connection.commit_calls == 1
    assert "WHERE key_hash = %s" in cursor.executed[0][0]
    assert "UPDATE api_keys SET last_used_at" in cursor.executed[1][0]


def test_api_key_repository_lists_with_status_filter_and_limit_bounds():
    cursor = FakeCursor(fetchall_results=[[_api_key_row()]])
    repository = ApiKeyRepository(FakeConnector(cursor, use_read_only=True))

    result = repository.list_api_keys(status="active", limit=999)

    assert result["success"] is True
    assert result["data"][0]["roles"] == ["chat"]
    query, params = cursor.executed[0]
    assert "FROM api_keys" in query
    assert params == ("active", 200)


def test_api_key_repository_revokes_key_and_returns_metadata():
    cursor = FakeCursor(fetchone_results=[_api_key_row(status="revoked")])
    connector = FakeConnector(cursor)
    repository = ApiKeyRepository(connector)

    result = repository.revoke_api_key(10)

    assert result["success"] is True
    assert result["data"]["status"] == "revoked"
    assert connector.connection.commit_calls == 1
    assert "UPDATE api_keys" in cursor.executed[0][0]
