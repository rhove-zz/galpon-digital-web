"""Runtime AI feature flags for controlled staging validation.

The flags in this module are process-local and fail closed. They intentionally
do not persist to storage, do not expose secret values, and expire
automatically.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.config.settings import LOCAL_ENVIRONMENTS, SECURE_ENVIRONMENTS

TRUE_VALUES = {"1", "true", "yes", "on"}
PRODUCTION_ENVIRONMENTS = {"production", "prod"}
DEFAULT_GEMINI_TTL_SECONDS = 300
MAX_GEMINI_TTL_SECONDS = 900


def _env_enabled(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in TRUE_VALUES


def _runtime_environment() -> str:
    return os.getenv("ACU_ENV", os.getenv("APP_ENV", "development")).strip().lower()


@dataclass
class _GeminiRuntimeOverride:
    enabled: bool = False
    expires_at_epoch: Optional[float] = None
    updated_at_epoch: Optional[float] = None
    updated_by: str = ""


_gemini_override = _GeminiRuntimeOverride()


def env_gemini_enabled() -> bool:
    """Return the static env-configured Gemini flag."""
    return _env_enabled("GEMINI_ENABLED", False)


def is_gemini_runtime_enabled(now: Optional[float] = None) -> bool:
    """Return effective Gemini availability for the current process."""
    if env_gemini_enabled():
        return True
    return _dynamic_gemini_enabled(now=now)


def _dynamic_gemini_enabled(now: Optional[float] = None) -> bool:
    _expire_if_needed(now=now)
    return bool(_gemini_override.enabled)


def set_gemini_runtime_override(
    enabled: bool,
    ttl_seconds: Optional[int] = None,
    updated_by: str = "",
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Enable or disable the temporary Gemini override."""
    current_time = time.time() if now is None else now
    if not enabled:
        _gemini_override.enabled = False
        _gemini_override.expires_at_epoch = None
        _gemini_override.updated_at_epoch = current_time
        _gemini_override.updated_by = updated_by
        return get_gemini_runtime_status(now=current_time)

    ttl = _normalize_ttl(ttl_seconds)
    _gemini_override.enabled = True
    _gemini_override.expires_at_epoch = current_time + ttl
    _gemini_override.updated_at_epoch = current_time
    _gemini_override.updated_by = updated_by
    return get_gemini_runtime_status(now=current_time)


def get_gemini_runtime_status(now: Optional[float] = None) -> Dict[str, Any]:
    """Return sanitized Gemini flag state."""
    current_time = time.time() if now is None else now
    _expire_if_needed(now=current_time)
    ttl_remaining = None
    if _gemini_override.expires_at_epoch is not None:
        ttl_remaining = max(0, int(_gemini_override.expires_at_epoch - current_time))

    return {
        "effective_enabled": is_gemini_runtime_enabled(now=current_time),
        "env_enabled": env_gemini_enabled(),
        "runtime_override_enabled": bool(_gemini_override.enabled),
        "expires_at_epoch": _gemini_override.expires_at_epoch,
        "ttl_remaining_seconds": ttl_remaining,
        "updated_at_epoch": _gemini_override.updated_at_epoch,
        "updated_by_fingerprint": _gemini_override.updated_by,
    }


def runtime_toggle_allowed_environment() -> bool:
    """Allow dynamic toggles only outside production."""
    env = _runtime_environment()
    return bool(env in LOCAL_ENVIRONMENTS or env in SECURE_ENVIRONMENTS) and (
        env not in PRODUCTION_ENVIRONMENTS
    )


def ai_runtime_safety_state() -> Dict[str, bool]:
    """Return non-secret safety flags that must remain disabled for Gemini smoke."""
    return {
        "tools_enabled": _env_enabled("ACU_TOOLS_ENABLED", True),
        "write_tools_enabled": _env_enabled("ACU_WRITE_TOOLS_ENABLED", False),
        "web_tools_enabled": _env_enabled("ACU_WEB_TOOLS_ENABLED", False),
        "filesystem_write_enabled": _env_enabled("ACU_FILESYSTEM_WRITE_ENABLED", False),
        "external_tools_enabled": _env_enabled("ACU_EXTERNAL_TOOLS_ENABLED", False),
    }


def ai_runtime_safety_allows_gemini() -> bool:
    """Return True only when tools and writes are disabled."""
    state = ai_runtime_safety_state()
    return not any(state.values())


def reset_gemini_runtime_override() -> None:
    """Reset process-local override for tests and rollback paths."""
    _gemini_override.enabled = False
    _gemini_override.expires_at_epoch = None
    _gemini_override.updated_at_epoch = None
    _gemini_override.updated_by = ""


def _normalize_ttl(ttl_seconds: Optional[int]) -> int:
    try:
        ttl = int(ttl_seconds or DEFAULT_GEMINI_TTL_SECONDS)
    except (TypeError, ValueError):
        ttl = DEFAULT_GEMINI_TTL_SECONDS
    return max(1, min(ttl, MAX_GEMINI_TTL_SECONDS))


def _expire_if_needed(now: Optional[float] = None) -> None:
    current_time = time.time() if now is None else now
    if (
        _gemini_override.enabled
        and _gemini_override.expires_at_epoch is not None
        and _gemini_override.expires_at_epoch <= current_time
    ):
        _gemini_override.enabled = False
        _gemini_override.expires_at_epoch = None
