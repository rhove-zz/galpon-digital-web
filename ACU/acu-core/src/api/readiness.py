"""Runtime readiness checks for exposed ACU environments."""

from typing import Any, Dict, List

from fastapi import Request

from src.api.scheduler import VALID_SCHEDULER_MODES
from src.config.settings import system_config
from src.memory.redis_manager import redis_manager


def build_system_readiness(
    request: Request,
    api_contract_version: str,
    api_stability: str,
) -> Dict[str, Any]:
    """Build a local readiness checklist for operational exposure."""
    checks: List[Dict[str, str]] = []

    def add_check(name: str, status: str, severity: str, detail: str) -> None:
        checks.append(
            {
                "name": name,
                "status": status,
                "severity": severity,
                "detail": detail,
            }
        )

    api_auth_required = bool(getattr(request.app.state, "api_auth_required", False))
    add_check(
        "api_auth_required",
        "pass" if api_auth_required else "fail",
        "critical",
        "Autenticacion API habilitada"
        if api_auth_required
        else "ACU_API_AUTH_REQUIRED debe estar habilitado para ambientes expuestos",
    )

    rate_limit_requests = int(getattr(request.app.state, "rate_limit_requests", 0) or 0)
    add_check(
        "rate_limit_enabled",
        "pass" if rate_limit_requests > 0 else "fail",
        "critical",
        f"Rate limit activo: {rate_limit_requests} requests por ventana"
        if rate_limit_requests > 0
        else "ACU_API_RATE_LIMIT_REQUESTS debe ser mayor que cero",
    )

    max_body_bytes = int(getattr(request.app.state, "max_request_body_bytes", 0) or 0)
    add_check(
        "payload_limit_enabled",
        "pass" if max_body_bytes > 0 else "fail",
        "critical",
        f"Limite de payload activo: {max_body_bytes} bytes"
        if max_body_bytes > 0
        else "ACU_API_MAX_REQUEST_BODY_BYTES debe ser mayor que cero",
    )

    cors_origins = list(getattr(request.app.state, "cors_origins", []) or [])
    wildcard_cors = "*" in cors_origins
    add_check(
        "cors_restricted",
        "fail" if wildcard_cors else "pass",
        "critical",
        "CORS permite cualquier origen; configure origenes explicitos"
        if wildcard_cors
        else (
            f"CORS restringido a {len(cors_origins)} origen(es)"
            if cors_origins
            else "CORS deshabilitado"
        ),
    )

    telegram_secret = bool(system_config.webhook_telegram_secret)
    add_check(
        "webhook_telegram_secret",
        "pass" if telegram_secret else "warning",
        "warning",
        "Secret de Telegram configurado"
        if telegram_secret
        else "ACU_TELEGRAM_WEBHOOK_SECRET no esta configurado",
    )

    slack_secret = bool(system_config.webhook_slack_signing_secret)
    add_check(
        "webhook_slack_signing_secret",
        "pass" if slack_secret else "warning",
        "warning",
        "Signing secret de Slack configurado"
        if slack_secret
        else "ACU_SLACK_SIGNING_SECRET no esta configurado",
    )

    redis_connected = bool(redis_manager.enabled and redis_manager.redis)
    add_check(
        "redis_connected",
        "pass" if redis_connected else "warning",
        "warning",
        "Redis conectado para rate limit y metricas compartidas"
        if redis_connected
        else "Redis no esta conectado; algunos agregados operaran por proceso local",
    )

    scheduler_mode = str(system_config.scheduler_mode or "").strip().lower()
    scheduler_valid = scheduler_mode in VALID_SCHEDULER_MODES
    add_check(
        "scheduler_mode",
        "pass" if scheduler_valid else "fail",
        "critical",
        f"Scheduler mode valido: {scheduler_mode}"
        if scheduler_valid
        else f"Scheduler mode invalido: {scheduler_mode}",
    )

    api_contract_stable = api_contract_version == "v1" and api_stability == "stable"
    add_check(
        "api_contract",
        "pass" if api_contract_stable else "fail",
        "critical",
        f"Contrato API {api_contract_version} {api_stability}"
        if api_contract_stable
        else "Contrato API no estable para clientes externos",
    )

    summary = {
        "passed": sum(1 for check in checks if check["status"] == "pass"),
        "warnings": sum(1 for check in checks if check["status"] == "warning"),
        "failed": sum(1 for check in checks if check["status"] == "fail"),
    }
    status = (
        "not_ready"
        if summary["failed"] > 0
        else "warning"
        if summary["warnings"] > 0
        else "ready"
    )
    return {
        "service": system_config.project_name,
        "version": system_config.version,
        "api_version": api_contract_version,
        "status": status,
        "summary": summary,
        "checks": checks,
    }
