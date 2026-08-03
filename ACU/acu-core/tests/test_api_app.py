import asyncio
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from src.api import webhooks
from src.api.app import create_app, _skip_access_audit_for_read_only_staging
from src.config.settings import system_config
from src.memory.redis_manager import redis_manager
from src.utils.schemas import ToolResult, ToolType


def test_health_endpoint_returns_service_metadata():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-acu-api-version"] == "v1"
    assert response.headers["x-acu-api-stability"] == "stable"
    assert response.json() == {
        "status": "ok",
        "service": system_config.project_name,
        "version": system_config.version,
    }


def test_api_version_endpoint_and_openapi_publish_contract_metadata():
    client = TestClient(create_app(api_key="secret-key"))

    headers = {"X-ACU-API-Key": "secret-key"}
    version_response = client.get("/api/version", headers=headers)
    openapi_response = client.get("/openapi.json", headers=headers)

    assert version_response.status_code == 200
    assert version_response.headers["x-acu-api-version"] == "v1"
    assert version_response.json() == {
        "service": system_config.project_name,
        "runtime_version": system_config.version,
        "api_version": "v1",
        "stability": "stable",
        "openapi_url": "/openapi.json",
    }
    assert openapi_response.status_code == 200
    openapi = openapi_response.json()
    assert openapi["info"]["x-acu-api-version"] == "v1"
    assert openapi["info"]["x-acu-api-stability"] == "stable"
    assert "x-acu-breaking-change-policy" in openapi["info"]
    assert "/api/version" in openapi["paths"]
    assert openapi["components"]["schemas"]["ApiVersionResponse"]["required"] == [
        "service",
        "runtime_version",
        "api_version",
        "stability",
        "openapi_url",
    ]


def test_dashboard_endpoint_returns_monitoring_html():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "ACU Monitor" in html
    assert 'href="/static/dashboard.css"' in html
    assert 'src="/static/dashboard.js"' in html
    assert 'id="chatMessage"' in html
    assert "Chunks BrainCore" in html
    assert 'id="ingestPath"' in html
    assert 'id="brainSearchQuery"' in html
    assert 'id="apiKeyName"' in html
    assert 'id="vectorStatus"' in html
    assert 'id="securityStatus"' in html
    assert 'id="hitlStatus"' in html
    assert 'id="schedulerStatus"' in html
    assert 'id="webhookStatusMetric"' in html
    assert "Human-in-the-Loop" in html

    css_response = client.get("/static/dashboard.css")
    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert ".status-grid" in css_response.text
    assert ".hitl-section" in css_response.text
    assert ".hitl-resumed" in css_response.text
    assert ".hitl-rejected" in css_response.text

    js_response = client.get("/static/dashboard.js")
    assert js_response.status_code == 200
    assert "javascript" in js_response.headers["content-type"]
    js = js_response.text
    assert "/chat" in js
    assert "/sessions" in js
    assert "/tools/executions" in js
    assert "/braincore/decisions" in js
    assert "/braincore/sources" in js
    assert "/braincore/metrics" in js
    assert "/system/metrics" in js
    assert "/braincore/ingest" in js
    assert "/braincore/search" in js
    assert 'method: "POST"' in js
    assert 'method: "DELETE"' in js
    assert "data-delete-source" in js
    assert "/api/keys?limit=50" in js
    assert "/api/keys" in js
    assert "data-revoke-key" in js
    assert "/api/access-log" in js
    assert "API key requerida o invalida" in js
    assert "Rol insuficiente" in js
    assert "Rate limit excedido" in js
    assert "Retry-After" in js
    assert "appendChatTurn" in js
    assert "toolDetails" in js
    assert "pending_tools" in js
    assert "scheduler" in js
    assert "webhooks" in js
    assert "hitlStatusBadge" in js
    assert "resumeTool" in js
    assert "hitlOutcome" in js
    assert "copyCreatedApiKey" in js
    assert "navigator.clipboard" in js


def test_cors_can_be_enabled_for_configured_origins():
    client = TestClient(create_app(cors_origins=["http://ui.local"]))

    response = client.options(
        "/chat",
        headers={
            "Origin": "http://ui.local",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://ui.local"
    assert "POST" in response.headers["access-control-allow-methods"]


class FakeToolsManager:
    def __init__(self):
        self.execution_log = []

    def get_execution_log(self):
        return self.execution_log


class FakeAgent:
    def __init__(self, initialize_result=True):
        self.initialize_result = initialize_result
        self.initialize_calls = 0
        self.processed_messages = []
        self.session_id = "test-session"
        self.total_iterations = 0
        self.tools_manager = FakeToolsManager()

    async def initialize(self, session_id=None):
        self.initialize_calls += 1
        self.system_prompt = "dummy"
        if session_id:
            self.session_id = session_id
        return self.initialize_result

    async def process_user_message(self, message):
        self.processed_messages.append(message)
        self.total_iterations += 2
        self.tools_manager.execution_log.append(
            ToolResult(
                tool=ToolType.SQL_READ,
                success=True,
                result=[{"ok": True}],
                error=None,
                execution_time_ms=12.5,
            )
        )
        return "respuesta api"

    async def resume_after_tool_approval(self, pending_tool):
        self.resumed_pending_tool = pending_tool
        return "respuesta reanudada"


def test_chat_endpoint_processes_message_and_returns_structured_response():
    fake_agent = FakeAgent()

    async def provider(domain, **kwargs):
        assert domain == "generic"
        return fake_agent

    client = TestClient(create_app(agent_provider=provider))

    response = client.post("/chat", json={"message": " hola "})

    assert response.status_code == 200
    assert fake_agent.initialize_calls == 1
    assert fake_agent.processed_messages == ["hola"]
    assert response.json() == {
        "session_id": "test-session",
        "response": "respuesta api",
        "iterations": 2,
        "tool_calls": [
            {
                "tool": "ejecutar_sql_lectura",
                "success": True,
                "result": [{"ok": True}],
                "error": None,
                "execution_time_ms": 12.5,
            }
        ],
    }


def test_payload_limit_rejects_oversized_requests_before_agent_execution():
    fake_agent = FakeAgent()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(create_app(agent_provider=provider, max_request_body_bytes=10))

    response = client.post("/chat", json={"message": "hola mundo"})

    assert response.status_code == 413
    assert "limite configurado" in response.json()["detail"]
    assert fake_agent.initialize_calls == 0


def test_rate_limit_rejects_requests_after_configured_threshold():
    client = TestClient(create_app(rate_limit_requests=2, rate_limit_window_seconds=60))

    first_response = client.get("/health")
    second_response = client.get("/health")
    third_response = client.get("/health")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 429
    assert "Rate limit excedido" in third_response.json()["detail"]
    assert third_response.headers["retry-after"]


def test_rate_limit_uses_api_key_identity_when_present():
    client = TestClient(create_app(rate_limit_requests=1, rate_limit_window_seconds=60))

    first_key_response = client.get(
        "/health",
        headers={"X-ACU-API-Key": "key-a"},
    )
    second_key_response = client.get(
        "/health",
        headers={"X-ACU-API-Key": "key-a"},
    )
    other_key_response = client.get(
        "/health",
        headers={"X-ACU-API-Key": "key-b"},
    )

    assert first_key_response.status_code == 200
    assert second_key_response.status_code == 429
    assert other_key_response.status_code == 200


def test_api_key_protects_operational_endpoints_when_configured():
    fake_agent = FakeAgent()
    access_audit = FakeAccessAudit()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(
        create_app(
            agent_provider=provider,
            access_audit_provider=lambda: access_audit,
            api_key="secret-key",
        )
    )

    response = client.post("/chat", json={"message": "hola"})

    assert response.status_code == 401
    assert response.json()["detail"] == "API key requerida o invalida"
    assert fake_agent.initialize_calls == 0
    assert access_audit.entries[0]["status_code"] == 401
    assert access_audit.entries[0]["authorized"] is False


def test_api_key_accepts_custom_header():
    fake_agent = FakeAgent()
    access_audit = FakeAccessAudit()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(
        create_app(
            agent_provider=provider,
            access_audit_provider=lambda: access_audit,
            api_key="secret-key",
        )
    )

    response = client.post(
        "/chat",
        json={"message": "hola"},
        headers={"X-ACU-API-Key": "secret-key"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "respuesta api"
    assert access_audit.entries[0]["status_code"] == 200
    assert access_audit.entries[0]["roles"] == ["admin"]
    assert access_audit.entries[0]["key_fingerprint"]


def test_api_key_accepts_bearer_header_and_keeps_public_routes_open():
    fake_agent = FakeAgent()
    access_audit = FakeAccessAudit()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(
        create_app(
            agent_provider=provider,
            access_audit_provider=lambda: access_audit,
            api_key="secret-key",
        )
    )

    assert client.get("/health").status_code == 200
    assert client.get("/dashboard").status_code == 401
    assert client.get("/api/version").status_code == 401
    assert client.get("/openapi.json").status_code == 401

    response = client.post(
        "/chat",
        json={"message": "hola"},
        headers={"Authorization": "Bearer secret-key"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "test-session"
    assert len(access_audit.entries) == 4


def test_secure_runtime_requires_api_key_configuration(monkeypatch):
    monkeypatch.setattr(system_config, "environment", "staging")
    monkeypatch.setattr(system_config, "api_auth_required", True)
    monkeypatch.setattr(system_config, "require_api_key", True)

    with pytest.raises(RuntimeError, match="ACU_API_KEY or ACU_API_KEYS"):
        create_app(api_key="", api_keys={})


def test_secure_runtime_cannot_disable_api_auth(monkeypatch):
    monkeypatch.setattr(system_config, "environment", "production")
    monkeypatch.setattr(system_config, "require_api_key", True)

    with pytest.raises(RuntimeError, match="cannot be disabled"):
        create_app(api_key="secure-key", api_auth_required=False)


def test_secure_runtime_protects_dashboard_docs_and_openapi(monkeypatch):
    monkeypatch.setattr(system_config, "environment", "staging")
    monkeypatch.setattr(system_config, "api_auth_required", True)
    monkeypatch.setattr(system_config, "require_api_key", True)
    access_audit = FakeAccessAudit()
    client = TestClient(
        create_app(
            access_audit_provider=lambda: access_audit,
            api_key="secure-key",
        )
    )

    assert client.get("/health").status_code == 200
    assert client.get("/dashboard").status_code == 401
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/docs").status_code == 401
    assert client.get("/static/dashboard.css").status_code == 401
    accepted = client.get("/dashboard", headers={"X-ACU-API-Key": "secure-key"})
    assert accepted.status_code == 200


def test_operational_public_routes_require_explicit_local_opt_in(monkeypatch):
    monkeypatch.setattr(system_config, "environment", "development")
    monkeypatch.setattr(system_config, "allow_operational_public_routes", False)
    client = TestClient(create_app(api_key="secret-key"))

    assert client.get("/health").status_code == 200
    assert client.get("/system/readiness").status_code == 200
    assert client.get("/dashboard").status_code == 401
    assert client.get("/docs").status_code == 401
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/api/version").status_code == 401

    monkeypatch.setattr(system_config, "allow_operational_public_routes", True)
    local_client = TestClient(create_app(api_key="secret-key"))

    assert local_client.get("/dashboard").status_code == 200
    assert local_client.get("/docs").status_code == 200
    assert local_client.get("/openapi.json").status_code == 200


def test_role_limited_key_allows_chat_but_forbids_monitoring():
    fake_agent = FakeAgent()
    db = FakeMonitoringDB()
    access_audit = FakeAccessAudit()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(
        create_app(
            agent_provider=provider,
            database_provider=lambda: db,
            access_audit_provider=lambda: access_audit,
            api_key="",
            api_keys={"chat-key": ["chat"]},
        )
    )

    chat_response = client.post(
        "/chat",
        json={"message": "hola"},
        headers={"X-ACU-API-Key": "chat-key"},
    )
    sessions_response = client.get(
        "/sessions",
        headers={"X-ACU-API-Key": "chat-key"},
    )

    assert chat_response.status_code == 200
    assert sessions_response.status_code == 403
    assert sessions_response.json()["detail"] == "Rol insuficiente para este endpoint"
    assert db.sessions_payload is None
    assert access_audit.entries[-1]["status_code"] == 403
    assert access_audit.entries[-1]["roles"] == ["chat"]


def test_monitoring_role_allows_monitoring_endpoints():
    db = FakeMonitoringDB()
    braincore = FakeBrainCoreManager()
    access_audit = FakeAccessAudit()
    client = TestClient(
        create_app(
            braincore_provider=lambda: braincore,
            database_provider=lambda: db,
            access_audit_provider=lambda: access_audit,
            api_key="",
            api_keys={"monitor-key": ["monitoring"]},
        )
    )

    response = client.get(
        "/sessions",
        headers={"X-ACU-API-Key": "monitor-key"},
    )
    system_response = client.get(
        "/system/metrics",
        headers={"X-ACU-API-Key": "monitor-key"},
    )

    assert response.status_code == 200
    assert response.json()[0]["session_id"] == "session-1"
    assert access_audit.entries[0]["path"] == "/sessions"
    assert system_response.status_code == 200
    assert system_response.json()["vector_store"]["engine"] == "faiss"


def test_system_readiness_reports_not_ready_for_insecure_runtime():
    client = TestClient(
        create_app(
            api_auth_required=False,
            rate_limit_requests=0,
            max_request_body_bytes=0,
            cors_origins=["*"],
        )
    )

    response = client.get("/system/readiness")

    assert response.status_code == 200
    payload = response.json()
    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["status"] == "not_ready"
    assert payload["summary"]["failed"] >= 4
    assert checks["api_auth_required"]["status"] == "fail"
    assert checks["rate_limit_enabled"]["status"] == "fail"
    assert checks["payload_limit_enabled"]["status"] == "fail"
    assert checks["cors_restricted"]["status"] == "fail"


def test_system_readiness_reports_ready_for_security_baseline(monkeypatch):
    monkeypatch.setattr(system_config, "webhook_telegram_secret", "telegram-secret")
    monkeypatch.setattr(system_config, "webhook_slack_signing_secret", "slack-secret")
    monkeypatch.setattr(redis_manager, "enabled", True)
    monkeypatch.setattr(redis_manager, "redis", object())
    client = TestClient(
        create_app(
            api_auth_required=True,
            api_key="",
            api_keys={"monitor-key": ["monitoring"]},
            rate_limit_requests=120,
            max_request_body_bytes=1_048_576,
            cors_origins=["https://panel.example.com"],
        )
    )

    response = client.get(
        "/system/readiness",
        headers={"X-ACU-API-Key": "monitor-key"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["summary"] == {"passed": 9, "warnings": 0, "failed": 0}
    assert {check["status"] for check in payload["checks"]} == {"pass"}


def test_system_readiness_remains_public_for_platform_smoke():
    access_audit = FakeAccessAudit()
    client = TestClient(
        create_app(
            access_audit_provider=lambda: access_audit,
            api_key="",
            api_keys={
                "chat-key": ["chat"],
                "monitor-key": ["monitoring"],
            },
        )
    )

    public_response = client.get("/system/readiness")
    chat_key_response = client.get(
        "/system/readiness",
        headers={"X-ACU-API-Key": "chat-key"},
    )
    monitoring_key_response = client.get(
        "/system/readiness",
        headers={"X-ACU-API-Key": "monitor-key"},
    )

    assert public_response.status_code == 200
    assert chat_key_response.status_code == 200
    assert monitoring_key_response.status_code == 200
    assert public_response.json()["api_version"] == "v1"
    assert access_audit.entries == []


def test_access_audit_skips_when_secure_production_read_only(monkeypatch):
    monkeypatch.delenv("ACU_READ_ONLY", raising=False)
    monkeypatch.setattr(system_config, "environment", "production")
    monkeypatch.setattr(system_config, "production_read_only", True)
    monkeypatch.setattr(system_config, "write_tools_enabled", False)

    assert _skip_access_audit_for_read_only_staging() is True


def test_access_audit_does_not_skip_when_write_tools_enabled(monkeypatch):
    monkeypatch.setenv("ACU_READ_ONLY", "true")
    monkeypatch.setattr(system_config, "environment", "production")
    monkeypatch.setattr(system_config, "production_read_only", True)
    monkeypatch.setattr(system_config, "write_tools_enabled", True)

    assert _skip_access_audit_for_read_only_staging() is False


def test_hitl_pending_endpoints_require_admin_role():
    redis_manager.redis = None
    redis_manager.enabled = False
    redis_manager._local_pending_tools.clear()
    access_audit = FakeAccessAudit()
    client = TestClient(
        create_app(
            access_audit_provider=lambda: access_audit,
            api_key="",
            api_keys={
                "monitor-key": ["monitoring"],
                "admin-key": ["admin"],
            },
        )
    )

    rejected_list = client.get(
        "/tools/pending",
        headers={"X-ACU-API-Key": "monitor-key"},
    )
    accepted_list = client.get(
        "/tools/pending",
        headers={"X-ACU-API-Key": "admin-key"},
    )
    rejected_action = client.post(
        "/tools/pending/missing/reject",
        headers={"X-ACU-API-Key": "monitor-key"},
    )
    accepted_action = client.post(
        "/tools/pending/missing/reject",
        headers={"X-ACU-API-Key": "admin-key"},
    )

    assert rejected_list.status_code == 403
    assert accepted_list.status_code == 200
    assert accepted_list.json() == []
    assert rejected_action.status_code == 403
    assert accepted_action.status_code == 404
    assert access_audit.entries[0]["path"] == "/tools/pending"
    assert access_audit.entries[0]["status_code"] == 403
    assert access_audit.entries[-1]["path"] == "/tools/pending/missing/reject"
    assert access_audit.entries[-1]["status_code"] == 404


def test_braincore_roles_separate_read_and_write_permissions():
    braincore = FakeBrainCoreManager()
    access_audit = FakeAccessAudit()
    client = TestClient(
        create_app(
            braincore_provider=lambda: braincore,
            access_audit_provider=lambda: access_audit,
            api_key="",
            api_keys={
                "brain-read": ["braincore_read"],
                "brain-write": ["braincore_write"],
            },
        )
    )

    search_response = client.post(
        "/braincore/search",
        json={"query": "fastapi", "domain": "acu"},
        headers={"X-ACU-API-Key": "brain-read"},
    )
    sources_response = client.get(
        "/braincore/sources",
        headers={"X-ACU-API-Key": "brain-read"},
    )
    metrics_response = client.get(
        "/braincore/metrics",
        headers={"X-ACU-API-Key": "brain-read"},
    )
    export_response = client.get(
        "/braincore/domains/acu/export",
        headers={"X-ACU-API-Key": "brain-read"},
    )
    forbidden_ingest_response = client.post(
        "/braincore/ingest",
        json={"path": "wiki", "domain": "acu"},
        headers={"X-ACU-API-Key": "brain-read"},
    )
    forbidden_delete_response = client.delete(
        "/braincore/sources/3",
        headers={"X-ACU-API-Key": "brain-read"},
    )
    forbidden_domain_delete_response = client.delete(
        "/braincore/domains/acu",
        params={"confirm": "acu"},
        headers={"X-ACU-API-Key": "brain-read"},
    )
    allowed_ingest_response = client.post(
        "/braincore/ingest",
        json={"path": "wiki", "domain": "acu"},
        headers={"X-ACU-API-Key": "brain-write"},
    )
    allowed_domain_delete_response = client.delete(
        "/braincore/domains/acu",
        params={"confirm": "acu"},
        headers={"X-ACU-API-Key": "brain-write"},
    )

    assert search_response.status_code == 200
    assert sources_response.status_code == 200
    assert metrics_response.status_code == 200
    assert export_response.status_code == 200
    assert forbidden_ingest_response.status_code == 403
    assert forbidden_delete_response.status_code == 403
    assert forbidden_domain_delete_response.status_code == 403
    assert allowed_ingest_response.status_code == 200
    assert allowed_domain_delete_response.status_code == 200
    assert [entry["status_code"] for entry in access_audit.entries] == [
        200,
        200,
        200,
        200,
        403,
        403,
        403,
        200,
        200,
    ]


def test_legacy_api_key_keeps_admin_when_also_present_in_role_map():
    fake_agent = FakeAgent()
    db = FakeMonitoringDB()
    access_audit = FakeAccessAudit()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(
        create_app(
            agent_provider=provider,
            database_provider=lambda: db,
            access_audit_provider=lambda: access_audit,
            api_key="shared-key",
            api_keys={"shared-key": ["chat"]},
        )
    )

    response = client.get(
        "/sessions",
        headers={"X-ACU-API-Key": "shared-key"},
    )

    assert response.status_code == 200
    assert response.json()[0]["session_id"] == "session-1"


def test_admin_can_create_list_and_revoke_managed_api_keys():
    key_manager = FakeManagedApiKeys()
    client = TestClient(
        create_app(
            api_key_provider=lambda: key_manager,
            api_key="admin-secret",
        )
    )

    create_response = client.post(
        "/api/keys",
        json={
            "name": "chat client",
            "roles": ["chat"],
            "expires_at": "2999-06-01 00:00:00",
        },
        headers={"X-ACU-API-Key": "admin-secret"},
    )
    list_response = client.get(
        "/api/keys",
        headers={"X-ACU-API-Key": "admin-secret"},
    )
    revoke_response = client.post(
        "/api/keys/10/revoke",
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    assert create_response.status_code == 200
    assert create_response.json()["api_key"].startswith("acu_")
    assert create_response.json()["roles"] == ["chat"]
    assert key_manager.created_payload["name"] == "chat client"
    assert key_manager.created_payload["key_hash"]
    assert key_manager.created_payload["expires_at"] == "2999-06-01 00:00:00"
    assert list_response.status_code == 200
    assert list_response.json()[0]["key_fingerprint"] == "abc123"
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"
    assert key_manager.revoked_key_id == 10


def test_managed_api_key_can_authorize_requests_when_auth_required():
    fake_agent = FakeAgent()
    key_manager = FakeManagedApiKeys()

    async def provider(domain, **kwargs):
        return fake_agent

    raw_key = "acu_runtime_key"
    from src.api.app import _fingerprint_key, _hash_key

    key_manager.active_key_hash = _hash_key(raw_key)
    key_manager.active_record = {
        "id": 10,
        "name": "chat client",
        "key_fingerprint": _fingerprint_key(raw_key),
        "roles": ["chat"],
        "status": "active",
        "created_by": "admin",
        "created_at": "2026-05-14 10:00:00",
        "revoked_at": None,
        "expires_at": None,
        "last_used_at": None,
    }
    client = TestClient(
        create_app(
            agent_provider=provider,
            api_key_provider=lambda: key_manager,
            api_key="",
            api_keys={},
            api_auth_required=True,
        )
    )

    response = client.post(
        "/chat",
        json={"message": "hola"},
        headers={"X-ACU-API-Key": raw_key},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "respuesta api"


def test_api_key_functional_journey_create_use_revoke_then_rejects():
    fake_agent = FakeAgent()
    key_manager = FakeManagedApiKeys()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(
        create_app(
            agent_provider=provider,
            api_key_provider=lambda: key_manager,
            api_key="admin-secret",
            api_auth_required=True,
        )
    )

    created = client.post(
        "/api/keys",
        json={"name": "journey chat", "roles": ["chat"]},
        headers={"X-ACU-API-Key": "admin-secret"},
    )
    raw_key = created.json()["api_key"]

    allowed = client.post(
        "/chat",
        json={"message": "hola"},
        headers={"X-ACU-API-Key": raw_key},
    )
    revoked = client.post(
        "/api/keys/10/revoke",
        headers={"X-ACU-API-Key": "admin-secret"},
    )
    rejected = client.post(
        "/chat",
        json={"message": "hola otra vez"},
        headers={"X-ACU-API-Key": raw_key},
    )

    assert created.status_code == 200
    assert created.json()["roles"] == ["chat"]
    assert allowed.status_code == 200
    assert allowed.json()["response"] == "respuesta api"
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert rejected.status_code == 401


def test_admin_api_key_creation_rejects_invalid_expires_at():
    key_manager = FakeManagedApiKeys()
    client = TestClient(
        create_app(
            api_key_provider=lambda: key_manager,
            api_key="admin-secret",
        )
    )

    response = client.post(
        "/api/keys",
        json={
            "name": "chat client",
            "roles": ["chat"],
            "expires_at": "no-es-fecha",
        },
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    assert response.status_code == 422
    assert "expires_at" in response.json()["detail"]
    assert key_manager.created_payload is None


def test_admin_api_key_creation_rejects_past_expires_at():
    key_manager = FakeManagedApiKeys()
    client = TestClient(
        create_app(
            api_key_provider=lambda: key_manager,
            api_key="admin-secret",
        )
    )

    response = client.post(
        "/api/keys",
        json={
            "name": "chat client",
            "roles": ["chat"],
            "expires_at": "2000-01-01 00:00:00",
        },
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "expires_at debe ser una fecha futura"
    assert key_manager.created_payload is None


def test_admin_api_key_creation_normalizes_iso_expires_at():
    key_manager = FakeManagedApiKeys()
    client = TestClient(
        create_app(
            api_key_provider=lambda: key_manager,
            api_key="admin-secret",
        )
    )

    response = client.post(
        "/api/keys",
        json={
            "name": "chat client",
            "roles": ["chat"],
            "expires_at": "2099-06-01T05:30:00Z",
        },
        headers={"X-ACU-API-Key": "admin-secret"},
    )

    assert response.status_code == 200
    assert key_manager.created_payload["expires_at"] == "2099-06-01 05:30:00"


def test_chat_endpoint_initializes_agent_only_once():
    fake_agent = FakeAgent()

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(create_app(agent_provider=provider))

    assert client.post("/chat", json={"message": "uno"}).status_code == 200
    assert client.post("/chat", json={"message": "dos"}).status_code == 200

    assert fake_agent.initialize_calls == 1
    assert fake_agent.processed_messages == ["uno", "dos"]


def test_chat_endpoint_returns_503_when_agent_initialization_fails():
    fake_agent = FakeAgent(initialize_result=False)

    async def provider(domain, **kwargs):
        return fake_agent

    client = TestClient(create_app(agent_provider=provider))

    response = client.post("/chat", json={"message": "hola"})

    assert response.status_code == 503
    assert "inicializar" in response.json()["detail"]


class FakeBrainCoreManager:
    def __init__(self):
        self.register_payload = None
        self.list_payload = None
        self.sources_payload = None
        self.deleted_source_id = None
        self.export_payload = None
        self.deleted_domain_payload = None

    def register_decision(
        self,
        title,
        context,
        decision,
        alternatives,
        impact,
        domain,
        status,
        tags,
    ):
        self.register_payload = {
            "title": title,
            "context": context,
            "decision": decision,
            "alternatives": alternatives,
            "impact": impact,
            "domain": domain,
            "status": status,
            "tags": tags,
        }
        return {
            "success": True,
            "data": {
                "id": 7,
                "created_at": "2026-05-14 10:00:00",
                "updated_at": "2026-05-14 10:00:00",
                **self.register_payload,
            },
        }

    def list_decisions(self, search="", domain=None, status=None, limit=20):
        self.list_payload = {
            "search": search,
            "domain": domain,
            "status": status,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "id": 7,
                    "title": "Usar FastAPI",
                    "context": "Necesitamos API REST",
                    "decision": "Exponer ACU via FastAPI",
                    "alternatives": ["Flask"],
                    "impact": "Permite clientes externos",
                    "domain": "acu",
                    "status": "accepted",
                    "tags": ["api"],
                    "created_at": "2026-05-14 10:00:00",
                    "updated_at": "2026-05-14 10:00:00",
                }
            ],
        }

    def ingest_path(self, path, source_type="auto", domain="generic"):
        self.ingest_payload = {
            "path": path,
            "source_type": source_type,
            "domain": domain,
        }
        return {
            "success": True,
            "data": {
                "path": path,
                "files_found": 2,
                "sources_indexed": 2,
                "chunks_indexed": 5,
                "vector_indexed": True,
                "skipped_sources": 0,
                "errors": [],
            },
        }

    def list_sources(
        self,
        domain=None,
        source_type=None,
        status=None,
        limit=20,
    ):
        self.sources_payload = {
            "domain": domain,
            "source_type": source_type,
            "status": status,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "id": 3,
                    "source_path": "wiki/api.md",
                    "source_type": "markdown",
                    "content_hash": "abc123",
                    "metadata": {"domain": "acu"},
                    "status": "indexed",
                    "chunks_count": 4,
                    "indexed_at": "2026-05-14 10:00:00",
                    "updated_at": "2026-05-14 10:05:00",
                }
            ],
        }

    def get_metrics(self):
        return {
            "success": True,
            "data": {
                "decisions_count": 2,
                "sources_count": 3,
                "chunks_count": 12,
                "domains_count": 2,
                "last_indexed_at": "2026-05-14 10:00:00",
                "last_updated_at": "2026-05-14 10:05:00",
                "domains": [{"name": "acu", "sources_count": 2, "chunks_count": 8}],
                "source_types": [
                    {"name": "markdown", "sources_count": 3, "chunks_count": 12}
                ],
            },
        }

    def get_vector_status(self):
        return {
            "success": True,
            "data": {
                "enabled": True,
                "available": True,
                "engine": "faiss",
                "persist_directory": "data/vectors",
                "embedding_model": "test-model",
                "collection_name": "braincore_chunks",
                "index_path": "data/vectors/braincore_faiss.index",
                "metadata_path": "data/vectors/braincore_faiss_metadata.json",
                "index_exists": True,
                "metadata_exists": True,
                "records_count": 12,
                "cached": False,
                "status": "ready",
                "error": None,
            },
        }

    def export_domain(self, domain, include_chunks=True):
        self.export_payload = {
            "domain": domain,
            "include_chunks": include_chunks,
        }
        return {
            "success": True,
            "data": {
                "domain": domain,
                "decisions_count": 1,
                "sources_count": 1,
                "chunks_count": 1 if include_chunks else 4,
                "decisions": [{"id": 7, "domain": domain}],
                "sources": [{"id": 3, "source_path": "wiki/api.md"}],
                "chunks": [{"id": 9, "source_id": 3}] if include_chunks else [],
            },
        }

    def delete_domain(self, domain, delete_decisions=False):
        self.deleted_domain_payload = {
            "domain": domain,
            "delete_decisions": delete_decisions,
        }
        return {
            "success": True,
            "data": {
                "domain": domain,
                "sources_deleted": 2,
                "chunks_deleted": 8,
                "decisions_deleted": 1 if delete_decisions else 0,
                "vector_sources_deleted": 2,
                "deleted_source_paths": ["wiki/api.md", "wiki/ops.md"],
            },
        }

    def delete_source(self, source_id):
        self.deleted_source_id = source_id
        return {
            "success": True,
            "data": {
                "source_id": source_id,
                "source_path": "wiki/api.md",
                "deleted": True,
                "vector_deleted": True,
            },
        }

    def search_context(
        self,
        query,
        domain=None,
        source_type=None,
        top_k=5,
    ):
        self.search_payload = {
            "query": query,
            "domain": domain,
            "source_type": source_type,
            "top_k": top_k,
        }
        return {
            "success": True,
            "data": [
                {
                    "chunk_id": 1,
                    "source_id": 10,
                    "source_path": "wiki/api.md",
                    "source_type": "markdown",
                    "title": "Arquitectura API",
                    "content": "FastAPI expone ACU como puente REST.",
                    "similarity": 0.92,
                    "metadata": {"source": {"domain": "acu"}},
                    "indexed_at": "2026-05-14 10:00:00",
                }
            ],
        }


class StatefulBrainCoreManager(FakeBrainCoreManager):
    def __init__(self):
        super().__init__()
        self.indexed_sources = []
        self.indexed_chunks = []
        self.deleted_domains = set()

    def ingest_path(self, path, source_type="auto", domain="generic"):
        self.ingest_payload = {
            "path": path,
            "source_type": source_type,
            "domain": domain,
        }
        normalized_type = "markdown" if source_type == "auto" else source_type
        self.deleted_domains.discard(domain)
        self.indexed_sources = [
            {
                "id": 3,
                "source_path": f"{path}/api.md",
                "source_type": normalized_type,
                "content_hash": "abc123",
                "metadata": {"domain": domain},
                "status": "indexed",
                "chunks_count": 1,
                "indexed_at": "2026-05-14 10:00:00",
                "updated_at": "2026-05-14 10:05:00",
            }
        ]
        self.indexed_chunks = [
            {
                "chunk_id": 9,
                "source_id": 3,
                "source_path": f"{path}/api.md",
                "source_type": normalized_type,
                "title": "Arquitectura API",
                "content": "FastAPI expone ACU como puente REST.",
                "similarity": 0.94,
                "metadata": {"source": {"domain": domain}},
                "indexed_at": "2026-05-14 10:00:00",
            }
        ]
        return {
            "success": True,
            "data": {
                "path": path,
                "files_found": 1,
                "sources_indexed": 1,
                "chunks_indexed": 1,
                "vector_indexed": True,
                "skipped_sources": 0,
                "errors": [],
            },
        }

    def list_sources(
        self,
        domain=None,
        source_type=None,
        status=None,
        limit=20,
    ):
        self.sources_payload = {
            "domain": domain,
            "source_type": source_type,
            "status": status,
            "limit": limit,
        }
        if domain in self.deleted_domains:
            return {"success": True, "data": []}
        data = [
            source
            for source in self.indexed_sources
            if (domain is None or source["metadata"].get("domain") == domain)
            and (source_type is None or source["source_type"] == source_type)
            and (status is None or source["status"] == status)
        ]
        return {"success": True, "data": data[:limit]}

    def export_domain(self, domain, include_chunks=True):
        self.export_payload = {
            "domain": domain,
            "include_chunks": include_chunks,
        }
        if domain in self.deleted_domains:
            return {
                "success": True,
                "data": {
                    "domain": domain,
                    "decisions_count": 0,
                    "sources_count": 0,
                    "chunks_count": 0,
                    "decisions": [],
                    "sources": [],
                    "chunks": [],
                },
            }
        sources = [
            source
            for source in self.indexed_sources
            if source["metadata"].get("domain") == domain
        ]
        chunks = [
            chunk
            for chunk in self.indexed_chunks
            if chunk["metadata"]["source"].get("domain") == domain
        ]
        return {
            "success": True,
            "data": {
                "domain": domain,
                "decisions_count": 1,
                "sources_count": len(sources),
                "chunks_count": len(chunks),
                "decisions": [{"id": 7, "domain": domain}],
                "sources": sources,
                "chunks": chunks if include_chunks else [],
            },
        }

    def delete_domain(self, domain, delete_decisions=False):
        self.deleted_domain_payload = {
            "domain": domain,
            "delete_decisions": delete_decisions,
        }
        sources = [
            source
            for source in self.indexed_sources
            if source["metadata"].get("domain") == domain
        ]
        source_ids = {source["id"] for source in sources}
        chunks = [
            chunk for chunk in self.indexed_chunks if chunk["source_id"] in source_ids
        ]
        self.deleted_domains.add(domain)
        self.indexed_sources = [
            source
            for source in self.indexed_sources
            if source["metadata"].get("domain") != domain
        ]
        self.indexed_chunks = [
            chunk
            for chunk in self.indexed_chunks
            if chunk["source_id"] not in source_ids
        ]
        return {
            "success": True,
            "data": {
                "domain": domain,
                "sources_deleted": len(sources),
                "chunks_deleted": len(chunks),
                "decisions_deleted": 1 if delete_decisions else 0,
                "vector_sources_deleted": len(sources),
                "deleted_source_paths": [source["source_path"] for source in sources],
            },
        }

    def search_context(
        self,
        query,
        domain=None,
        source_type=None,
        top_k=5,
    ):
        self.search_payload = {
            "query": query,
            "domain": domain,
            "source_type": source_type,
            "top_k": top_k,
        }
        if domain in self.deleted_domains:
            return {"success": True, "data": []}
        data = [
            chunk
            for chunk in self.indexed_chunks
            if (domain is None or chunk["metadata"]["source"].get("domain") == domain)
            and (source_type is None or chunk["source_type"] == source_type)
        ]
        return {"success": True, "data": data[:top_k]}


def test_braincore_decision_endpoint_registers_adr():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.post(
        "/braincore/decisions",
        json={
            "title": "Usar FastAPI",
            "context": "Necesitamos API REST",
            "decision": "Exponer ACU via FastAPI",
            "alternatives": ["Flask"],
            "impact": "Permite clientes externos",
            "domain": "acu",
            "status": "accepted",
            "tags": ["api"],
        },
    )

    assert response.status_code == 200
    assert braincore.register_payload["title"] == "Usar FastAPI"
    assert response.json()["id"] == 7
    assert response.json()["alternatives"] == ["Flask"]


def test_braincore_decisions_endpoint_lists_adrs():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.get(
        "/braincore/decisions",
        params={
            "search": "fastapi",
            "domain": "acu",
            "status": "accepted",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert braincore.list_payload == {
        "search": "fastapi",
        "domain": "acu",
        "status": "accepted",
        "limit": 5,
    }
    assert response.json()[0]["title"] == "Usar FastAPI"


def test_braincore_ingest_endpoint_indexes_path():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.post(
        "/braincore/ingest",
        json={
            "path": "wiki",
            "source_type": "auto",
            "domain": "acu",
        },
    )

    assert response.status_code == 200
    assert braincore.ingest_payload == {
        "path": "wiki",
        "source_type": "auto",
        "domain": "acu",
    }
    assert response.json() == {
        "path": "wiki",
        "files_found": 2,
        "sources_indexed": 2,
        "chunks_indexed": 5,
        "vector_indexed": True,
        "skipped_sources": 0,
        "errors": [],
    }


def test_braincore_sources_endpoint_lists_indexed_sources():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.get(
        "/braincore/sources",
        params={
            "domain": "acu",
            "source_type": "markdown",
            "status": "indexed",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert braincore.sources_payload == {
        "domain": "acu",
        "source_type": "markdown",
        "status": "indexed",
        "limit": 5,
    }
    assert response.json() == [
        {
            "id": 3,
            "source_path": "wiki/api.md",
            "source_type": "markdown",
            "content_hash": "abc123",
            "metadata": {"domain": "acu"},
            "status": "indexed",
            "chunks_count": 4,
            "indexed_at": "2026-05-14 10:00:00",
            "updated_at": "2026-05-14 10:05:00",
        }
    ]


def test_braincore_metrics_endpoint_returns_aggregate_counts():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.get("/braincore/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "decisions_count": 2,
        "sources_count": 3,
        "chunks_count": 12,
        "domains_count": 2,
        "last_indexed_at": "2026-05-14 10:00:00",
        "last_updated_at": "2026-05-14 10:05:00",
        "domains": [{"name": "acu", "sources_count": 2, "chunks_count": 8}],
        "source_types": [{"name": "markdown", "sources_count": 3, "chunks_count": 12}],
    }


def test_braincore_domain_export_endpoint_returns_snapshot():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.get(
        "/braincore/domains/acu/export",
        params={"include_chunks": False},
    )

    assert response.status_code == 200
    assert braincore.export_payload == {
        "domain": "acu",
        "include_chunks": False,
    }
    assert response.json() == {
        "domain": "acu",
        "decisions_count": 1,
        "sources_count": 1,
        "chunks_count": 4,
        "decisions": [{"id": 7, "domain": "acu"}],
        "sources": [{"id": 3, "source_path": "wiki/api.md"}],
        "chunks": [],
    }


def test_braincore_domain_delete_requires_confirmation_and_deletes_domain():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    rejected = client.delete("/braincore/domains/acu", params={"confirm": "wrong"})
    accepted = client.delete(
        "/braincore/domains/acu",
        params={"confirm": "acu", "delete_decisions": True},
    )

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert braincore.deleted_domain_payload == {
        "domain": "acu",
        "delete_decisions": True,
    }
    assert accepted.json() == {
        "domain": "acu",
        "sources_deleted": 2,
        "chunks_deleted": 8,
        "decisions_deleted": 1,
        "vector_sources_deleted": 2,
        "deleted_source_paths": ["wiki/api.md", "wiki/ops.md"],
    }


def test_braincore_functional_journey_ingest_search_export_delete_domain():
    braincore = StatefulBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    ingest = client.post(
        "/braincore/ingest",
        json={
            "path": "wiki",
            "source_type": "auto",
            "domain": "acu",
        },
    )
    sources_before_delete = client.get(
        "/braincore/sources",
        params={
            "domain": "acu",
            "source_type": "markdown",
            "status": "indexed",
        },
    )
    search = client.post(
        "/braincore/search",
        json={
            "query": "fastapi rest",
            "domain": "acu",
            "source_type": "markdown",
            "top_k": 5,
        },
    )
    export = client.get(
        "/braincore/domains/acu/export",
        params={"include_chunks": True},
    )
    delete = client.delete(
        "/braincore/domains/acu",
        params={"confirm": "acu", "delete_decisions": True},
    )
    sources_after_delete = client.get(
        "/braincore/sources",
        params={"domain": "acu"},
    )
    search_after_delete = client.post(
        "/braincore/search",
        json={"query": "fastapi rest", "domain": "acu", "top_k": 5},
    )

    assert ingest.status_code == 200
    assert ingest.json()["sources_indexed"] == 1
    assert sources_before_delete.status_code == 200
    assert sources_before_delete.json()[0]["source_path"] == "wiki/api.md"
    assert search.status_code == 200
    assert search.json()["results"][0]["content"] == (
        "FastAPI expone ACU como puente REST."
    )
    assert export.status_code == 200
    assert export.json()["sources_count"] == 1
    assert export.json()["chunks_count"] == 1
    assert export.json()["chunks"][0]["chunk_id"] == 9
    assert delete.status_code == 200
    assert delete.json() == {
        "domain": "acu",
        "sources_deleted": 1,
        "chunks_deleted": 1,
        "decisions_deleted": 1,
        "vector_sources_deleted": 1,
        "deleted_source_paths": ["wiki/api.md"],
    }
    assert sources_after_delete.status_code == 200
    assert sources_after_delete.json() == []
    assert search_after_delete.status_code == 200
    assert search_after_delete.json() == {"query": "fastapi rest", "results": []}


def test_system_metrics_endpoint_returns_runtime_status():
    braincore = FakeBrainCoreManager()
    redis_manager._local_pending_tools.clear()
    webhooks._reset_webhook_metrics()
    client = TestClient(
        create_app(
            braincore_provider=lambda: braincore,
            cors_origins=["http://ui.local"],
            max_request_body_bytes=1000,
            rate_limit_requests=5,
        )
    )

    response = client.get("/system/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "service": system_config.project_name,
        "version": system_config.version,
        "vector_store": {
            "enabled": True,
            "available": True,
            "engine": "faiss",
            "persist_directory": "data/vectors",
            "embedding_model": "test-model",
            "collection_name": "braincore_chunks",
            "index_path": "data/vectors/braincore_faiss.index",
            "metadata_path": "data/vectors/braincore_faiss_metadata.json",
            "index_exists": True,
            "metadata_exists": True,
            "records_count": 12,
            "cached": False,
            "status": "ready",
            "error": None,
        },
        "api_auth_required": False,
        "rate_limit_enabled": True,
        "payload_limit_enabled": True,
        "cors_enabled": True,
        "pending_tools": {
            "total": 0,
            "pending": 0,
            "approved": 0,
            "executed": 0,
            "failed": 0,
            "rejected": 0,
            "resumed": 0,
        },
        "scheduler": {
            "mode": system_config.scheduler_mode,
            "valid_mode": system_config.scheduler_mode
            in {"disabled", "api", "worker", "all"},
            "running": False,
            "jobs_count": 0,
            "jobs": [],
        },
        "redis": {
            "enabled": redis_manager.enabled,
            "connected": bool(redis_manager.redis),
            "backend": "redis"
            if redis_manager.enabled and redis_manager.redis
            else "local",
        },
        "webhooks": {
            "total": {
                "received": 0,
                "accepted": 0,
                "rejected": 0,
                "ignored": 0,
                "processed": 0,
                "failed": 0,
                "last_event_at": None,
                "last_error": None,
            },
            "channels": {
                "telegram": {
                    "received": 0,
                    "accepted": 0,
                    "rejected": 0,
                    "ignored": 0,
                    "processed": 0,
                    "failed": 0,
                    "last_event_at": None,
                    "last_error": None,
                },
                "slack": {
                    "received": 0,
                    "accepted": 0,
                    "rejected": 0,
                    "ignored": 0,
                    "processed": 0,
                    "failed": 0,
                    "last_event_at": None,
                    "last_error": None,
                },
            },
        },
    }


def test_braincore_source_endpoint_deletes_indexed_source():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.delete("/braincore/sources/3")

    assert response.status_code == 200
    assert braincore.deleted_source_id == 3
    assert response.json() == {
        "source_id": 3,
        "source_path": "wiki/api.md",
        "deleted": True,
        "vector_deleted": True,
    }


def test_braincore_search_endpoint_returns_context_results():
    braincore = FakeBrainCoreManager()
    client = TestClient(create_app(braincore_provider=lambda: braincore))

    response = client.post(
        "/braincore/search",
        json={
            "query": "fastapi rest",
            "domain": "acu",
            "source_type": "markdown",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert braincore.search_payload == {
        "query": "fastapi rest",
        "domain": "acu",
        "source_type": "markdown",
        "top_k": 3,
    }
    assert response.json() == {
        "query": "fastapi rest",
        "results": [
            {
                "chunk_id": 1,
                "source_id": 10,
                "source_path": "wiki/api.md",
                "source_type": "markdown",
                "title": "Arquitectura API",
                "content": "FastAPI expone ACU como puente REST.",
                "similarity": 0.92,
                "metadata": {"source": {"domain": "acu"}},
                "indexed_at": "2026-05-14 10:00:00",
            }
        ],
    }


class FakeMonitoringDB:
    def __init__(self):
        self.sessions_payload = None
        self.context_payload = None
        self.tools_payload = None
        self.api_access_payload = None

    def list_agent_sessions(self, domain=None, status=None, limit=20):
        self.sessions_payload = {
            "domain": domain,
            "status": status,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "session_id": "session-1",
                    "domain": "acu",
                    "started_at": "2026-05-14 10:00:00",
                    "ended_at": None,
                    "total_iterations": 3,
                    "status": "active",
                }
            ],
        }

    def get_conversation_context(self, session_id, limit=50):
        self.context_payload = {
            "session_id": session_id,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "id": 1,
                    "session_id": session_id,
                    "user_query": "hola",
                    "agent_response": "respuesta",
                    "timestamp": "2026-05-14 10:00:00",
                    "steps_used": 2,
                }
            ],
        }

    def list_tool_executions(self, tool_name=None, success=None, limit=50):
        self.tools_payload = {
            "tool_name": tool_name,
            "success": success,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "id": 1,
                    "tool_name": "buscar_contexto_braincore",
                    "parameters": {"consulta": "fastapi"},
                    "result": {"success": True},
                    "execution_time_ms": 12,
                    "success": True,
                    "executed_at": "2026-05-14 10:00:00",
                }
            ],
        }

    def list_api_access_log(
        self,
        path=None,
        status_code=None,
        authorized=None,
        limit=50,
    ):
        self.api_access_payload = {
            "path": path,
            "status_code": status_code,
            "authorized": authorized,
            "limit": limit,
        }
        return {
            "success": True,
            "data": [
                {
                    "id": 1,
                    "method": "POST",
                    "path": "/chat",
                    "status_code": 200,
                    "key_fingerprint": "abc123",
                    "roles": ["chat"],
                    "client_ip": "127.0.0.1",
                    "user_agent": "testclient",
                    "authorized": True,
                    "duration_ms": 14,
                    "accessed_at": "2026-05-14 10:00:00",
                }
            ],
        }


class FakeAccessAudit:
    def __init__(self):
        self.entries = []

    def log_api_access(
        self,
        method,
        path,
        status_code,
        key_fingerprint="",
        roles=None,
        client_ip="",
        user_agent="",
        authorized=False,
        duration_ms=0.0,
    ):
        self.entries.append(
            {
                "method": method,
                "path": path,
                "status_code": status_code,
                "key_fingerprint": key_fingerprint,
                "roles": roles or [],
                "client_ip": client_ip,
                "user_agent": user_agent,
                "authorized": authorized,
                "duration_ms": duration_ms,
            }
        )
        return True


class FakeManagedApiKeys:
    def __init__(self):
        self.created_payload = None
        self.revoked_key_id = None
        self.active_key_hash = None
        self.active_record = None
        self.records_by_hash = {}
        self.records_by_id = {}

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
        record = {
            "id": 10,
            "name": name,
            "key_fingerprint": key_fingerprint,
            "roles": roles,
            "status": "active",
            "created_by": created_by,
            "created_at": "2026-05-14 10:00:00",
            "revoked_at": None,
            "expires_at": expires_at,
            "last_used_at": None,
        }
        self.records_by_hash[key_hash] = record
        self.records_by_id[record["id"]] = record
        return {
            "success": True,
            "data": record,
        }

    def find_active_api_key(self, key_hash):
        if self.active_key_hash and key_hash == self.active_key_hash:
            return {"success": True, "data": self.active_record}
        record = self.records_by_hash.get(key_hash)
        if record and record["status"] == "active":
            return {"success": True, "data": record}
        return {"success": True, "data": None}

    def list_api_keys(self, status=None, limit=50):
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
                    "created_at": "2026-05-14 10:00:00",
                    "revoked_at": None,
                    "expires_at": None,
                    "last_used_at": None,
                }
            ],
        }

    def revoke_api_key(self, key_id):
        self.revoked_key_id = key_id
        record = self.records_by_id.get(key_id)
        if record:
            record["status"] = "revoked"
            record["revoked_at"] = "2026-05-14 11:00:00"
            return {"success": True, "data": record}
        return {
            "success": True,
            "data": {
                "id": key_id,
                "name": "chat client",
                "key_fingerprint": "abc123",
                "roles": ["chat"],
                "status": "revoked",
                "created_by": "admin",
                "created_at": "2026-05-14 10:00:00",
                "revoked_at": "2026-05-14 11:00:00",
                "expires_at": None,
                "last_used_at": None,
            },
        }


def test_sessions_endpoint_lists_agent_sessions():
    db = FakeMonitoringDB()
    client = TestClient(create_app(database_provider=lambda: db))

    response = client.get(
        "/sessions",
        params={"domain": "acu", "status": "active", "limit": 5},
    )

    assert response.status_code == 200
    assert db.sessions_payload == {
        "domain": "acu",
        "status": "active",
        "limit": 5,
    }
    assert response.json()[0]["session_id"] == "session-1"


def test_session_context_endpoint_lists_turns():
    db = FakeMonitoringDB()
    client = TestClient(create_app(database_provider=lambda: db))

    response = client.get("/sessions/session-1/context", params={"limit": 10})

    assert response.status_code == 200
    assert db.context_payload == {"session_id": "session-1", "limit": 10}
    assert response.json()[0]["user_query"] == "hola"


def test_tool_executions_endpoint_lists_audit_rows():
    db = FakeMonitoringDB()
    client = TestClient(create_app(database_provider=lambda: db))

    response = client.get(
        "/tools/executions",
        params={
            "tool_name": "buscar_contexto_braincore",
            "success": True,
            "limit": 7,
        },
    )

    assert response.status_code == 200
    assert db.tools_payload == {
        "tool_name": "buscar_contexto_braincore",
        "success": True,
        "limit": 7,
    }
    assert response.json()[0]["parameters"] == {"consulta": "fastapi"}


def test_api_access_log_endpoint_lists_access_audit_rows():
    db = FakeMonitoringDB()
    client = TestClient(create_app(database_provider=lambda: db))

    response = client.get(
        "/api/access-log",
        params={
            "path": "/chat",
            "status_code": 200,
            "authorized": True,
            "limit": 9,
        },
    )

    assert response.status_code == 200
    assert db.api_access_payload == {
        "path": "/chat",
        "status_code": 200,
        "authorized": True,
        "limit": 9,
    }
    assert response.json()[0]["roles"] == ["chat"]


def test_resume_pending_tool_requires_executed_status():
    redis_manager.redis = None
    redis_manager.enabled = False
    redis_manager._local_pending_tools.clear()
    asyncio.run(
        redis_manager.set_pending_tool(
            "tool-pending",
            {
                "tool": "peticion_api_rest",
                "parameters": {},
                "session_id": "session-1",
                "status": "pending",
            },
        )
    )
    client = TestClient(create_app())

    response = client.post("/tools/pending/tool-pending/resume")

    assert response.status_code == 409


def test_resume_pending_tool_uses_session_context_and_marks_resumed():
    redis_manager.redis = None
    redis_manager.enabled = False
    redis_manager._local_pending_tools.clear()
    asyncio.run(
        redis_manager.set_pending_tool(
            "tool-executed",
            {
                "tool": "peticion_api_rest",
                "parameters": {"url": "https://example.test"},
                "session_id": "session-resume",
                "domain": "ops",
                "persona": "devsecops",
                "status": "executed",
                "result": {"success": True, "result": {"status_code": 200}},
            },
        )
    )
    fake_agent = FakeAgent()

    async def provider(domain, **kwargs):
        assert domain == "ops"
        assert kwargs["persona"] == "devsecops"
        return fake_agent

    client = TestClient(create_app(agent_provider=provider))

    response = client.post("/tools/pending/tool-executed/resume")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "status": "resumed",
        "pending_tool_id": "tool-executed",
        "session_id": "session-resume",
        "response": "respuesta reanudada",
    }
    assert fake_agent.initialize_calls == 1
    assert fake_agent.session_id == "session-resume"
    assert fake_agent.resumed_pending_tool["id"] == "tool-executed"

    pending = asyncio.run(redis_manager.get_pending_tool("tool-executed"))
    assert pending["status"] == "resumed"
    assert pending["resumed_response"] == "respuesta reanudada"


def test_hitl_functional_journey_reject_approve_execute_and_resume(monkeypatch):
    redis_manager.redis = None
    redis_manager.enabled = False
    redis_manager._local_pending_tools.clear()
    fake_agent = FakeAgent()

    class FakePendingToolsManager:
        async def execute_pending_tool(self, tool_id):
            pending_tool = await redis_manager.get_pending_tool(tool_id)
            assert pending_tool["status"] == "approved"
            pending_tool["status"] = "executed"
            pending_tool["result"] = {
                "tool": ToolType.API_REST.value,
                "success": True,
                "result": {"status_code": 200},
                "error": None,
                "execution_time_ms": 1.0,
                "status": "executed",
                "pending_tool_id": tool_id,
            }
            await redis_manager.set_pending_tool(tool_id, pending_tool)
            return ToolResult(
                tool=ToolType.API_REST,
                success=True,
                result={"status_code": 200},
                error=None,
                execution_time_ms=1.0,
                status="executed",
                pending_tool_id=tool_id,
            )

    async def provider(domain, **kwargs):
        assert domain == "ops"
        assert kwargs["persona"] == "devsecops"
        return fake_agent

    from src.tools import tools_manager as tools_manager_module

    monkeypatch.setattr(
        tools_manager_module,
        "get_tools_manager",
        lambda: FakePendingToolsManager(),
    )
    asyncio.run(
        redis_manager.set_pending_tool(
            "tool-reject",
            {
                "tool": ToolType.API_REST.value,
                "parameters": {"url": "https://reject.example"},
                "session_id": "session-reject",
                "domain": "ops",
                "persona": "devsecops",
                "status": "pending",
            },
        )
    )
    asyncio.run(
        redis_manager.set_pending_tool(
            "tool-approve",
            {
                "tool": ToolType.API_REST.value,
                "parameters": {"url": "https://approve.example"},
                "session_id": "session-approve",
                "domain": "ops",
                "persona": "devsecops",
                "status": "pending",
            },
        )
    )
    client = TestClient(create_app(agent_provider=provider))

    pending_before = client.get("/tools/pending")
    rejected = client.post("/tools/pending/tool-reject/reject")
    premature_resume = client.post("/tools/pending/tool-reject/resume")
    approved = client.post("/tools/pending/tool-approve/approve")
    resumed = client.post("/tools/pending/tool-approve/resume")
    metrics = client.get("/system/metrics")

    assert pending_before.status_code == 200
    assert {tool["id"] for tool in pending_before.json()} == {
        "tool-reject",
        "tool-approve",
    }
    assert rejected.status_code == 200
    assert rejected.json() == {"success": True, "status": "rejected"}
    assert premature_resume.status_code == 409
    assert approved.status_code == 200
    assert approved.json() == {
        "success": True,
        "status": "executed",
        "pending_tool_id": "tool-approve",
        "result": {"status_code": 200},
        "error": None,
    }
    assert resumed.status_code == 200
    assert resumed.json() == {
        "success": True,
        "status": "resumed",
        "pending_tool_id": "tool-approve",
        "session_id": "session-approve",
        "response": "respuesta reanudada",
    }
    assert fake_agent.session_id == "session-approve"
    assert fake_agent.resumed_pending_tool["result"]["success"] is True

    rejected_tool = asyncio.run(redis_manager.get_pending_tool("tool-reject"))
    resumed_tool = asyncio.run(redis_manager.get_pending_tool("tool-approve"))
    assert rejected_tool["status"] == "rejected"
    assert resumed_tool["status"] == "resumed"
    assert metrics.status_code == 200
    assert metrics.json()["pending_tools"] == {
        "total": 2,
        "pending": 0,
        "approved": 0,
        "executed": 0,
        "failed": 0,
        "rejected": 1,
        "resumed": 1,
    }


def _slack_signature(secret: str, timestamp: str, body: bytes) -> str:
    base = b"v0:" + timestamp.encode("utf-8") + b":" + body
    return "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()


def test_telegram_webhook_requires_configured_secret(monkeypatch):
    async def fake_process(*args, **kwargs):
        return None

    webhooks._reset_webhook_metrics()
    monkeypatch.setattr(webhooks, "_process_webhook_message", fake_process)
    monkeypatch.setattr(system_config, "webhook_telegram_secret", "telegram-secret")
    monkeypatch.setattr(system_config, "webhook_allowed_telegram_chats", "")
    client = TestClient(create_app())

    payload = {"message": {"text": "hola", "chat": {"id": "chat-1"}}}

    rejected = client.post("/webhooks/telegram", json=payload)
    accepted = client.post(
        "/webhooks/telegram",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "ok"}


def test_webhooks_fail_closed_without_secret_in_secure_runtime(monkeypatch):
    monkeypatch.setattr(system_config, "environment", "staging")
    monkeypatch.setattr(system_config, "api_auth_required", True)
    monkeypatch.setattr(system_config, "require_api_key", True)
    monkeypatch.setattr(system_config, "webhook_telegram_secret", "")
    monkeypatch.setattr(system_config, "webhook_slack_signing_secret", "")
    client = TestClient(create_app(api_key="secure-key"))
    headers = {"X-ACU-API-Key": "secure-key"}

    telegram_response = client.post(
        "/webhooks/telegram",
        json={"message": {"text": "hola", "chat": {"id": "chat-1"}}},
        headers=headers,
    )
    slack_response = client.post(
        "/webhooks/slack",
        json={"event": {"type": "message", "text": "hola", "user": "user-1"}},
        headers=headers,
    )

    assert telegram_response.status_code == 503
    assert slack_response.status_code == 503


def test_system_metrics_includes_webhook_counters(monkeypatch):
    async def fake_process(*args, **kwargs):
        webhooks._record_webhook_metric("telegram", "processed")

    webhooks._reset_webhook_metrics()
    monkeypatch.setattr(webhooks, "_process_webhook_message", fake_process)
    monkeypatch.setattr(system_config, "webhook_telegram_secret", "telegram-secret")
    monkeypatch.setattr(system_config, "webhook_allowed_telegram_chats", "")
    client = TestClient(create_app(braincore_provider=lambda: FakeBrainCoreManager()))

    payload = {"message": {"text": "hola", "chat": {"id": "chat-1"}}}

    rejected = client.post("/webhooks/telegram", json=payload)
    accepted = client.post(
        "/webhooks/telegram",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
    )
    metrics = client.get("/system/metrics")

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert metrics.status_code == 200
    webhooks_payload = metrics.json()["webhooks"]
    assert webhooks_payload["total"]["received"] == 2
    assert webhooks_payload["total"]["accepted"] == 1
    assert webhooks_payload["total"]["rejected"] == 1
    assert webhooks_payload["total"]["processed"] == 1
    assert webhooks_payload["channels"]["telegram"]["last_error"] == (
        "Invalid Telegram webhook secret"
    )


def test_system_metrics_prefers_shared_webhook_counters(monkeypatch):
    async def fake_shared_metrics(channels):
        return {
            "telegram": {
                "received": 7,
                "accepted": 5,
                "rejected": 2,
                "ignored": 0,
                "processed": 4,
                "failed": 1,
                "last_event_at": 123.4,
                "last_error": "shared error",
            },
            "slack": {
                "received": 3,
                "accepted": 3,
                "rejected": 0,
                "ignored": 0,
                "processed": 2,
                "failed": 0,
                "last_event_at": 124.4,
                "last_error": None,
            },
        }

    webhooks._reset_webhook_metrics()
    webhooks._record_webhook_metric("telegram", "received")
    monkeypatch.setattr(redis_manager, "get_webhook_metrics", fake_shared_metrics)
    client = TestClient(create_app(braincore_provider=lambda: FakeBrainCoreManager()))

    metrics = client.get("/system/metrics")

    assert metrics.status_code == 200
    webhooks_payload = metrics.json()["webhooks"]
    assert webhooks_payload["total"]["received"] == 10
    assert webhooks_payload["total"]["accepted"] == 8
    assert webhooks_payload["total"]["rejected"] == 2
    assert webhooks_payload["total"]["processed"] == 6
    assert webhooks_payload["total"]["failed"] == 1
    assert webhooks_payload["channels"]["telegram"]["received"] == 7
    assert webhooks_payload["channels"]["telegram"]["last_error"] == "shared error"


def test_telegram_webhook_enforces_allowed_chats(monkeypatch):
    webhooks._reset_webhook_metrics()
    monkeypatch.setattr(system_config, "webhook_telegram_secret", "telegram-secret")
    monkeypatch.setattr(system_config, "webhook_allowed_telegram_chats", "chat-ok")
    client = TestClient(create_app())

    response = client.post(
        "/webhooks/telegram",
        json={"message": {"text": "hola", "chat": {"id": "chat-blocked"}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
    )

    assert response.status_code == 403


def test_slack_webhook_validates_signature_and_replay_window(monkeypatch):
    async def fake_process(*args, **kwargs):
        return None

    secret = "slack-secret"
    webhooks._reset_webhook_metrics()
    monkeypatch.setattr(webhooks, "_process_webhook_message", fake_process)
    monkeypatch.setattr(system_config, "webhook_slack_signing_secret", secret)
    monkeypatch.setattr(system_config, "webhook_slack_max_skew_seconds", 300)
    monkeypatch.setattr(system_config, "webhook_allowed_slack_users", "")
    client = TestClient(create_app())

    body = json.dumps(
        {"event": {"type": "message", "text": "hola", "user": "U123"}},
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = str(int(time.time()))
    valid_headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": _slack_signature(secret, timestamp, body),
        "Content-Type": "application/json",
    }

    bad_signature = client.post(
        "/webhooks/slack",
        content=body,
        headers={**valid_headers, "X-Slack-Signature": "v0=bad"},
    )
    accepted = client.post("/webhooks/slack", content=body, headers=valid_headers)
    stale_timestamp = str(int(time.time()) - 999)
    stale = client.post(
        "/webhooks/slack",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": stale_timestamp,
            "X-Slack-Signature": _slack_signature(secret, stale_timestamp, body),
            "Content-Type": "application/json",
        },
    )

    assert bad_signature.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "ok"}
    assert stale.status_code == 401


def test_slack_webhook_enforces_allowed_users(monkeypatch):
    secret = "slack-secret"
    webhooks._reset_webhook_metrics()
    monkeypatch.setattr(system_config, "webhook_slack_signing_secret", secret)
    monkeypatch.setattr(system_config, "webhook_slack_max_skew_seconds", 300)
    monkeypatch.setattr(system_config, "webhook_allowed_slack_users", "U-allowed")
    client = TestClient(create_app())

    body = json.dumps(
        {"event": {"type": "message", "text": "hola", "user": "U-blocked"}},
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = str(int(time.time()))

    response = client.post(
        "/webhooks/slack",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": _slack_signature(secret, timestamp, body),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 403
