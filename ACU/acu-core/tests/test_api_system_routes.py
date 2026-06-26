from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.system import _summarize_pending_tools, create_system_router


def test_summarize_pending_tools_counts_known_statuses_only():
    summary = _summarize_pending_tools(
        [
            {"status": "pending"},
            {"status": "executed"},
            {"status": "resumed"},
            {"status": "unknown"},
        ]
    )

    assert summary == {
        "total": 4,
        "pending": 1,
        "approved": 0,
        "executed": 1,
        "failed": 0,
        "rejected": 0,
        "resumed": 1,
    }


def test_system_router_publishes_health_and_api_version():
    app = FastAPI()
    app.include_router(
        create_system_router(api_contract_version="v1", api_stability="stable")
    )
    client = TestClient(app)

    health = client.get("/health")
    version = client.get("/api/version")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert version.status_code == 200
    assert version.json()["api_version"] == "v1"
    assert version.json()["stability"] == "stable"
