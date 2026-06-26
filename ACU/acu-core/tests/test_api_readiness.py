from types import SimpleNamespace

from src.api.readiness import build_system_readiness
from src.config.settings import system_config
from src.memory.redis_manager import redis_manager


def _request_state(**values):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**values)))


def test_build_system_readiness_fails_critical_runtime_controls():
    request = _request_state(
        api_auth_required=False,
        rate_limit_requests=0,
        max_request_body_bytes=0,
        cors_origins=["*"],
    )

    payload = build_system_readiness(
        request=request,
        api_contract_version="v1",
        api_stability="stable",
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["status"] == "not_ready"
    assert checks["api_auth_required"]["status"] == "fail"
    assert checks["rate_limit_enabled"]["status"] == "fail"
    assert checks["payload_limit_enabled"]["status"] == "fail"
    assert checks["cors_restricted"]["status"] == "fail"


def test_build_system_readiness_can_report_ready(monkeypatch):
    monkeypatch.setattr(system_config, "webhook_telegram_secret", "telegram-secret")
    monkeypatch.setattr(system_config, "webhook_slack_signing_secret", "slack-secret")
    monkeypatch.setattr(redis_manager, "enabled", True)
    monkeypatch.setattr(redis_manager, "redis", object())
    request = _request_state(
        api_auth_required=True,
        rate_limit_requests=120,
        max_request_body_bytes=1_048_576,
        cors_origins=["https://panel.example.com"],
    )

    payload = build_system_readiness(
        request=request,
        api_contract_version="v1",
        api_stability="stable",
    )

    assert payload["status"] == "ready"
    assert payload["summary"] == {"passed": 9, "warnings": 0, "failed": 0}
    assert {check["status"] for check in payload["checks"]} == {"pass"}


def test_build_system_readiness_rejects_unstable_contract():
    request = _request_state(
        api_auth_required=True,
        rate_limit_requests=120,
        max_request_body_bytes=1_048_576,
        cors_origins=[],
    )

    payload = build_system_readiness(
        request=request,
        api_contract_version="v2",
        api_stability="preview",
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["api_contract"]["status"] == "fail"
    assert payload["status"] == "not_ready"
