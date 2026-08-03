"""Fail-closed AI cost and request guard.

The guard is intentionally conservative and secret-free. It stores only daily
usage counters and estimated cost metadata, never prompts, responses or keys.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.config.settings import system_config
from src.utils.logger import log


@dataclass
class CostGuardDecision:
    """Result of a pre-model cost guard evaluation."""

    allowed: bool
    enabled: bool
    mode: str
    reason: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_request_cost_usd: float
    requests_used_today: int
    estimated_cost_used_today_usd: float
    state_file_available: bool


def evaluate_ai_request(user_message: str, max_output_tokens: int) -> CostGuardDecision:
    """Evaluate whether an AI request is allowed before model execution."""
    enabled = bool(getattr(system_config, "ai_cost_guard_enabled", False))
    mode = _guard_mode()
    estimated_input_tokens = _estimate_tokens(user_message)
    estimated_output_tokens = max(int(max_output_tokens or 0), 0)
    state = _load_today_state()
    state_file_available = state is not None
    state = state or _empty_state()
    estimated_request_cost = _estimate_request_cost(
        estimated_input_tokens,
        estimated_output_tokens,
    )

    decision = CostGuardDecision(
        allowed=True,
        enabled=enabled,
        mode=mode,
        reason="guard_disabled" if not enabled else "allowed",
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        estimated_request_cost_usd=estimated_request_cost,
        requests_used_today=int(state.get("requests", 0)),
        estimated_cost_used_today_usd=float(state.get("estimated_cost_usd", 0.0)),
        state_file_available=state_file_available,
    )
    if not enabled:
        return decision

    block_reason = _first_block_reason(decision)
    if block_reason:
        decision.reason = block_reason
        decision.allowed = mode != "block"
    return decision


def record_ai_request(decision: CostGuardDecision) -> None:
    """Record an allowed AI request attempt without storing payloads."""
    if not decision.enabled:
        return

    state = _load_today_state() or _empty_state()
    state["requests"] = int(state.get("requests", 0)) + 1
    state["estimated_cost_usd"] = round(
        float(state.get("estimated_cost_usd", 0.0)) + decision.estimated_request_cost_usd,
        8,
    )
    state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def _first_block_reason(decision: CostGuardDecision) -> str | None:
    input_limit = int(getattr(system_config, "ai_input_token_limit", 0) or 0)
    output_limit = int(getattr(system_config, "ai_output_token_limit", 0) or 0)
    request_limit = int(getattr(system_config, "ai_daily_request_limit", 0) or 0)
    daily_cost_limit = float(getattr(system_config, "ai_daily_cost_limit_usd", 0.0) or 0.0)

    if input_limit > 0 and decision.estimated_input_tokens > input_limit:
        return "input_token_limit_exceeded"
    if output_limit > 0 and decision.estimated_output_tokens > output_limit:
        return "output_token_limit_exceeded"
    if request_limit > 0 and decision.requests_used_today >= request_limit:
        return "daily_request_limit_exceeded"
    if (
        daily_cost_limit > 0
        and decision.estimated_request_cost_usd > 0
        and decision.estimated_cost_used_today_usd + decision.estimated_request_cost_usd
        > daily_cost_limit
    ):
        return "daily_cost_limit_exceeded"
    return None


def _estimate_tokens(text: str) -> int:
    stripped = (text or "").strip()
    if not stripped:
        return 0
    return max(1, math.ceil(len(stripped) / 4))


def _estimate_request_cost(input_tokens: int, output_tokens: int) -> float:
    per_1k = float(getattr(system_config, "ai_estimated_cost_per_1k_tokens_usd", 0.0) or 0.0)
    if per_1k <= 0:
        return 0.0
    return round(((input_tokens + output_tokens) / 1000.0) * per_1k, 8)


def _guard_mode() -> str:
    mode = str(getattr(system_config, "ai_cost_guard_mode", "block") or "block").lower()
    return mode if mode in {"block", "warn"} else "block"


def _state_file() -> Path:
    configured = str(getattr(system_config, "ai_cost_guard_state_file", "") or "").strip()
    if configured:
        return Path(configured)
    return Path("data") / "ai_cost_guard_state.json"


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _empty_state() -> Dict[str, Any]:
    return {
        "date_utc": _today_key(),
        "requests": 0,
        "estimated_cost_usd": 0.0,
    }


def _load_today_state() -> Dict[str, Any] | None:
    path = _state_file()
    try:
        if not path.exists():
            return _empty_state()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("date_utc") != _today_key():
            return _empty_state()
        return raw
    except Exception as exc:
        log.warning(f"AI cost guard state unavailable: {exc.__class__.__name__}")
        return None


def _save_state(state: Dict[str, Any]) -> None:
    path = _state_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        log.warning(f"AI cost guard state write failed safely: {exc.__class__.__name__}")
