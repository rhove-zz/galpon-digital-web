"""Admin-only AI validation routes."""

import asyncio
import re
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.api.security import extract_api_key, fingerprint_key
from src.llm.gemini_client import GeminiClient
from src.llm.runtime_flags import (
    ai_runtime_safety_allows_gemini,
    ai_runtime_safety_state,
    get_gemini_runtime_status,
    set_gemini_runtime_override,
)

router = APIRouter(prefix="/admin/ai", tags=["admin"])

SYNTHETIC_GEMINI_SMOKE_PROMPT = (
    "Responde con una frase corta indicando que el smoke Gemini controlado funciona. "
    "No uses datos reales."
)
DIRECT_SMOKE_TIMEOUT_SECONDS = 8
DIRECT_SMOKE_RATE_LIMIT_WINDOW_SECONDS = 3600
DIRECT_SMOKE_RATE_LIMIT_MAX_REQUESTS = 3
DIRECT_SMOKE_DAILY_LIMIT = 10

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_daily_attempts: list[float] = []
_audit_state: dict[str, Any] = {
    "total_attempts": 0,
    "success_count": 0,
    "failure_count": 0,
    "timeout_count": 0,
    "exception_count": 0,
    "rate_limited_count": 0,
    "safety_rejected_count": 0,
    "last_status": "none",
    "last_error_code": "",
    "last_latency_ms": None,
    "last_timeout_guard_triggered": False,
    "last_exception_guard_triggered": False,
    "last_provider_status": "not_executed",
    "last_actor_fingerprint": "",
    "last_updated_epoch": None,
}


@router.post("/gemini/smoke")
async def direct_gemini_smoke(request: Request):
    """Run one direct Gemini smoke with synthetic data and fail-closed cleanup."""
    now = time.time()
    started_at = time.perf_counter()
    actor_fingerprint = _admin_identity(request)
    if not ai_runtime_safety_allows_gemini():
        _record_smoke_audit(
            status="safety_rejected",
            error_code="AI_RUNTIME_SAFETY_REJECTED",
            actor_fingerprint=actor_fingerprint,
            latency_ms=_latency_ms(started_at),
            provider_status="not_executed",
            safety_rejected=True,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Gemini smoke requires tools and writes disabled",
                "safety": ai_runtime_safety_state(),
            },
        )

    rate_status = _check_rate_limit(actor_fingerprint, now)
    if not rate_status["allowed"]:
        _record_smoke_audit(
            status="rate_limited",
            error_code=str(rate_status["reason"]),
            actor_fingerprint=actor_fingerprint,
            latency_ms=_latency_ms(started_at),
            provider_status="not_executed",
            rate_limited=True,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Gemini admin smoke rate limit exceeded",
                "rate_limit": rate_status,
                "secret_values": "not_returned",
            },
        )

    model_client = getattr(request.app.state, "gemini_smoke_model_client", None)
    set_gemini_runtime_override(
        enabled=True,
        ttl_seconds=DIRECT_SMOKE_TIMEOUT_SECONDS + 30,
        updated_by="direct_admin_smoke",
    )
    try:
        client = GeminiClient(
            model_client=model_client,
            timeout_seconds=DIRECT_SMOKE_TIMEOUT_SECONDS,
        )
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.generate_response,
                "ACU Gemini smoke controlado con datos sinteticos.",
                SYNTHETIC_GEMINI_SMOKE_PROMPT,
                [],
                0.1,
                0.8,
            ),
            timeout=DIRECT_SMOKE_TIMEOUT_SECONDS + 2,
        )
        if not response:
            _record_smoke_audit(
                status="failed",
                error_code="GEMINI_EMPTY_OR_FAILED_RESPONSE",
                actor_fingerprint=actor_fingerprint,
                latency_ms=_latency_ms(started_at),
                provider_status="empty_or_failed_response",
            )
            return _smoke_response(
                ok=False,
                error_code="GEMINI_EMPTY_OR_FAILED_RESPONSE",
            )
        _record_smoke_audit(
            status="success",
            actor_fingerprint=actor_fingerprint,
            latency_ms=_latency_ms(started_at),
            provider_status="response_received",
        )
        return _smoke_response(ok=True, response_text=str(response))
    except asyncio.TimeoutError:
        _record_smoke_audit(
            status="timeout",
            error_code="GEMINI_TIMEOUT",
            actor_fingerprint=actor_fingerprint,
            latency_ms=_latency_ms(started_at),
            provider_status="timeout",
            timeout_guard_triggered=True,
        )
        return _smoke_response(ok=False, error_code="GEMINI_TIMEOUT")
    except Exception as exc:
        error_code = f"GEMINI_EXCEPTION_{exc.__class__.__name__}"
        _record_smoke_audit(
            status="exception",
            error_code=error_code,
            actor_fingerprint=actor_fingerprint,
            latency_ms=_latency_ms(started_at),
            provider_status="exception",
            exception_guard_triggered=True,
        )
        return _smoke_response(
            ok=False,
            error_code=error_code,
        )
    finally:
        set_gemini_runtime_override(enabled=False, updated_by="direct_admin_smoke")


@router.get("/gemini/smoke/status")
async def direct_gemini_smoke_status() -> dict[str, Any]:
    """Return sanitized process-local monitoring for the admin smoke endpoint."""
    safety = ai_runtime_safety_state()
    return {
        "endpoint": "/admin/ai/gemini/smoke",
        "scope": "GEMINI_ADMIN_DIRECT_SMOKE_ONLY",
        "admin_only": True,
        "synthetic_prompt_only": True,
        "direct_gemini_adapter": True,
        "bypassed_react_agent": True,
        "bypassed_chat_session_flow": True,
        "bypassed_tools": True,
        "bypassed_writes": True,
        "timeout_seconds": DIRECT_SMOKE_TIMEOUT_SECONDS,
        "rate_limit": _rate_policy(),
        "usage_window": _usage_status(),
        "audit": dict(_audit_state),
        "safety": safety,
        "safety_allows_gemini_smoke": ai_runtime_safety_allows_gemini(),
        "gemini_runtime": get_gemini_runtime_status(),
        "tools_enabled": bool(safety["tools_enabled"]),
        "acu_writes_enabled": bool(safety["filesystem_write_enabled"]),
        "secret_values": "not_returned",
    }


def _smoke_response(
    ok: bool,
    error_code: str = "",
    response_text: str = "",
) -> dict[str, Any]:
    safety = ai_runtime_safety_state()
    return {
        "ok": bool(ok),
        "error_code": _sanitize_code(error_code),
        "response_preview": _sanitize_preview(response_text),
        "synthetic_prompt_used": True,
        "direct_gemini_adapter": True,
        "bypassed_react_agent": True,
        "bypassed_chat_session_flow": True,
        "bypassed_tools": True,
        "bypassed_writes": True,
        "timeout_seconds": DIRECT_SMOKE_TIMEOUT_SECONDS,
        "tools_enabled": bool(safety["tools_enabled"]),
        "acu_writes_enabled": bool(safety["filesystem_write_enabled"]),
        "secret_values": "not_returned",
    }


def _sanitize_preview(text: str) -> str:
    if not text:
        return ""
    return "response_received"


def _sanitize_code(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9_]", "_", str(text).upper())[:80]


def _admin_identity(request: Request) -> str:
    return fingerprint_key(extract_api_key(request)) or "unknown"


def _rate_policy() -> dict[str, Any]:
    return {
        "window_seconds": DIRECT_SMOKE_RATE_LIMIT_WINDOW_SECONDS,
        "max_requests_per_window": DIRECT_SMOKE_RATE_LIMIT_MAX_REQUESTS,
        "max_requests_per_day": DIRECT_SMOKE_DAILY_LIMIT,
        "storage": "process_memory",
    }


def _usage_status(now: float | None = None) -> dict[str, Any]:
    current_time = time.time() if now is None else now
    _prune_daily_attempts(current_time)
    return {
        "daily_attempts_used": len(_daily_attempts),
        "daily_attempts_remaining": max(
            0,
            DIRECT_SMOKE_DAILY_LIMIT - len(_daily_attempts),
        ),
        "secret_values": "not_returned",
    }


def _check_rate_limit(actor_fingerprint: str, now: float) -> dict[str, Any]:
    bucket = _rate_buckets[actor_fingerprint]
    window_start = now - DIRECT_SMOKE_RATE_LIMIT_WINDOW_SECONDS
    bucket[:] = [item for item in bucket if item >= window_start]
    _prune_daily_attempts(now)

    window_remaining = max(0, DIRECT_SMOKE_RATE_LIMIT_MAX_REQUESTS - len(bucket))
    daily_remaining = max(0, DIRECT_SMOKE_DAILY_LIMIT - len(_daily_attempts))
    if window_remaining <= 0:
        return {
            "allowed": False,
            "reason": "WINDOW_LIMIT_EXCEEDED",
            **_rate_policy(),
            "window_attempts_used": len(bucket),
            "daily_attempts_used": len(_daily_attempts),
        }
    if daily_remaining <= 0:
        return {
            "allowed": False,
            "reason": "DAILY_LIMIT_EXCEEDED",
            **_rate_policy(),
            "window_attempts_used": len(bucket),
            "daily_attempts_used": len(_daily_attempts),
        }

    bucket.append(now)
    _daily_attempts.append(now)
    return {
        "allowed": True,
        "reason": "",
        **_rate_policy(),
        "window_attempts_used": len(bucket),
        "daily_attempts_used": len(_daily_attempts),
    }


def _record_smoke_audit(
    status: str,
    actor_fingerprint: str,
    latency_ms: int,
    error_code: str = "",
    provider_status: str = "",
    timeout_guard_triggered: bool = False,
    exception_guard_triggered: bool = False,
    rate_limited: bool = False,
    safety_rejected: bool = False,
) -> None:
    sanitized_status = _sanitize_code(status).lower()
    _audit_state["total_attempts"] = int(_audit_state["total_attempts"]) + 1
    if sanitized_status == "success":
        _audit_state["success_count"] = int(_audit_state["success_count"]) + 1
    elif rate_limited:
        _audit_state["rate_limited_count"] = (
            int(_audit_state["rate_limited_count"]) + 1
        )
    elif safety_rejected:
        _audit_state["safety_rejected_count"] = (
            int(_audit_state["safety_rejected_count"]) + 1
        )
    else:
        _audit_state["failure_count"] = int(_audit_state["failure_count"]) + 1

    if timeout_guard_triggered:
        _audit_state["timeout_count"] = int(_audit_state["timeout_count"]) + 1
    if exception_guard_triggered:
        _audit_state["exception_count"] = int(_audit_state["exception_count"]) + 1

    _audit_state["last_status"] = sanitized_status
    _audit_state["last_error_code"] = _sanitize_code(error_code)
    _audit_state["last_latency_ms"] = max(0, int(latency_ms))
    _audit_state["last_timeout_guard_triggered"] = bool(timeout_guard_triggered)
    _audit_state["last_exception_guard_triggered"] = bool(exception_guard_triggered)
    _audit_state["last_provider_status"] = _sanitize_code(provider_status).lower()
    _audit_state["last_actor_fingerprint"] = actor_fingerprint[:16]
    _audit_state["last_updated_epoch"] = int(time.time())


def _latency_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def _prune_daily_attempts(now: float) -> None:
    day_start = now - 86400
    _daily_attempts[:] = [item for item in _daily_attempts if item >= day_start]


def reset_admin_ai_smoke_monitoring() -> None:
    """Reset process-local admin smoke monitoring for tests."""
    _rate_buckets.clear()
    _daily_attempts.clear()
    _audit_state.update(
        {
            "total_attempts": 0,
            "success_count": 0,
            "failure_count": 0,
            "timeout_count": 0,
            "exception_count": 0,
            "rate_limited_count": 0,
            "safety_rejected_count": 0,
            "last_status": "none",
            "last_error_code": "",
            "last_latency_ms": None,
            "last_timeout_guard_triggered": False,
            "last_exception_guard_triggered": False,
            "last_provider_status": "not_executed",
            "last_actor_fingerprint": "",
            "last_updated_epoch": None,
        }
    )
