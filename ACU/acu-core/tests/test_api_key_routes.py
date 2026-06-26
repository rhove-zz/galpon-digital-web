from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.api_keys import router


class FakeApiKeyManager:
    def __init__(self):
        self.created_payload = None
        self.list_payload = None
        self.revoked_id = None

    def create_api_key(
        self,
        name,
        key_hash,
        key_fingerprint,
        roles,
        expires_at=None,
        created_by="",
    ):
        self.created_payload = {
            "name": name,
            "key_hash": key_hash,
            "key_fingerprint": key_fingerprint,
            "roles": roles,
            "expires_at": expires_at,
            "created_by": created_by,
        }
        return {
            "success": True,
            "data": {
                "id": 10,
                "name": name,
                "key_fingerprint": key_fingerprint,
                "roles": roles,
                "status": "active",
                "created_by": created_by,
                "created_at": "2026-05-19 10:00:00",
                "revoked_at": None,
                "expires_at": expires_at,
                "last_used_at": None,
            },
        }

    def list_api_keys(self, status=None, limit=50):
        self.list_payload = {"status": status, "limit": limit}
        return {
            "success": True,
            "data": [
                {
                    "id": 10,
                    "name": "chat client",
                    "key_fingerprint": "abc123",
                    "roles": ["chat"],
                    "status": status or "active",
                    "created_by": "admin",
                    "created_at": "2026-05-19 10:00:00",
                    "revoked_at": None,
                    "expires_at": None,
                    "last_used_at": None,
                }
            ],
        }

    def revoke_api_key(self, key_id):
        self.revoked_id = key_id
        if key_id == 404:
            return {"success": False, "error": "missing key"}
        return {
            "success": True,
            "data": {
                "id": key_id,
                "name": "chat client",
                "key_fingerprint": "abc123",
                "roles": ["chat"],
                "status": "revoked",
                "created_by": "admin",
                "created_at": "2026-05-19 10:00:00",
                "revoked_at": "2026-05-19 10:05:00",
                "expires_at": None,
                "last_used_at": None,
            },
        }


def _client(manager: FakeApiKeyManager) -> TestClient:
    app = FastAPI()
    app.state.api_key_provider = lambda: manager
    app.include_router(router)
    return TestClient(app)


def test_api_key_router_creates_key_and_returns_secret_once():
    manager = FakeApiKeyManager()
    client = _client(manager)

    response = client.post(
        "/api/keys",
        headers={"X-ACU-API-Key": "admin-secret"},
        json={"name": " chat client ", "roles": ["CHAT", "braincore_read"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"].startswith("acu_")
    assert payload["status"] == "active"
    assert manager.created_payload["name"] == "chat client"
    assert manager.created_payload["roles"] == ["braincore_read", "chat"]
    assert manager.created_payload["created_by"]


def test_api_key_router_rejects_invalid_roles():
    manager = FakeApiKeyManager()
    client = _client(manager)

    response = client.post(
        "/api/keys",
        json={"name": "bad client", "roles": ["unknown"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Roles invalidos: unknown"
    assert manager.created_payload is None


def test_api_key_router_lists_keys_with_filters():
    manager = FakeApiKeyManager()
    client = _client(manager)

    response = client.get("/api/keys?status=active&limit=5")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "chat client"
    assert manager.list_payload == {"status": "active", "limit": 5}


def test_api_key_router_revokes_or_returns_404():
    manager = FakeApiKeyManager()
    client = _client(manager)

    revoked = client.post("/api/keys/10/revoke")
    missing = client.post("/api/keys/404/revoke")

    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "missing key"
