# run_local_acu.py
"""
Launcher local seguro para ACU-CORE.

Uso:
    python run_local_acu.py

Reglas:
- No usar TiDB.
- No usar STAGING_DATABASE_URL.
- No guardar secretos reales en este archivo.
- ACU corre local en 127.0.0.1:8013.
- ACU opera en modo read-only.
"""

import hashlib
import os
from urllib.parse import urlparse

import uvicorn


def set_default_env() -> None:
    """
    Define variables locales seguras para ACU.
    Usa setdefault para no sobrescribir variables ya definidas en la terminal.
    """

    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("ACU_ENV", "local")

    os.environ.setdefault("ACU_READ_ONLY", "true")
    os.environ.setdefault("CHAT_PERSISTENCE_ENABLED", "false")
    os.environ.setdefault("TOOLS_WRITE_ENABLED", "false")
    os.environ.setdefault("TOOLS_EXTERNAL_ENABLED", "false")
    os.environ.setdefault("TOOLS_CRITICAL_ENABLED", "false")

    os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "").strip()
    if ollama_base_url and (
        not os.environ.get("OLLAMA_HOST", "").strip()
        or not os.environ.get("OLLAMA_PORT", "").strip()
    ):
        parsed = urlparse(ollama_base_url)
        if parsed.scheme and parsed.hostname:
            os.environ.setdefault("OLLAMA_HOST", f"{parsed.scheme}://{parsed.hostname}")
            os.environ.setdefault("OLLAMA_PORT", str(parsed.port or 11434))
    os.environ.setdefault("ACU_REDIS_URL", "")

    os.environ.pop("STAGING_DATABASE_URL", None)
    os.environ.pop("DATABASE_URL", None)

    os.environ.setdefault("ACU_HOST", "127.0.0.1")
    os.environ.setdefault("ACU_PORT", "8013")

    os.environ.setdefault("ACU_API_AUTH_REQUIRED", "true")
    os.environ.setdefault("ACU_API_RATE_LIMIT_REQUESTS", "120")
    os.environ.setdefault("ACU_API_RATE_LIMIT_WINDOW_SECONDS", "60")
    os.environ.setdefault("ACU_API_MAX_REQUEST_BODY_BYTES", "1048576")

    api_key = os.environ.get("ACU_API_KEY", "").strip()
    if api_key and not os.environ.get("ACU_API_KEYS", "").strip():
        os.environ["ACU_API_KEYS"] = (
            f"{api_key}=admin,chat,monitoring,braincore_read"
        )

    os.environ.setdefault("ACU_SCHEDULER_MODE", "disabled")
    os.environ.setdefault("ACU_TELEMETRY_ENABLED", "false")


def _state(name: str) -> str:
    return "DEFINED" if os.environ.get(name, "").strip() else "MISSING"


def _fingerprint_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        return "MISSING"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def print_safe_summary() -> None:
    """
    Imprime solo variables no sensibles.
    No imprime API keys, passwords, DATABASE_URL ni tokens.
    """

    safe_keys = [
        "APP_ENV",
        "ACU_ENV",
        "ACU_READ_ONLY",
        "CHAT_PERSISTENCE_ENABLED",
        "TOOLS_WRITE_ENABLED",
        "TOOLS_EXTERNAL_ENABLED",
        "TOOLS_CRITICAL_ENABLED",
        "OLLAMA_BASE_URL",
        "OLLAMA_HOST",
        "OLLAMA_PORT",
        "OLLAMA_MODEL",
        "ACU_REDIS_URL",
        "ACU_HOST",
        "ACU_PORT",
        "ACU_API_AUTH_REQUIRED",
        "ACU_API_RATE_LIMIT_REQUESTS",
        "ACU_API_RATE_LIMIT_WINDOW_SECONDS",
        "ACU_API_MAX_REQUEST_BODY_BYTES",
        "ACU_SCHEDULER_MODE",
        "ACU_TELEMETRY_ENABLED",
    ]

    print("\n=== ACU-CORE LOCAL LAUNCHER ===")
    for key in safe_keys:
        print(f"{key}={os.environ.get(key, 'MISSING')}")

    print("STAGING_DATABASE_URL=MISSING/REMOVED")
    print("DATABASE_URL=MISSING/REMOVED")
    print(f"ACU_API_KEY={_state('ACU_API_KEY')}")
    print(f"ACU_API_KEYS={_state('ACU_API_KEYS')}")
    print(f"ACU_API_KEY_FINGERPRINT={_fingerprint_env('ACU_API_KEY')}")
    print(f"ACU_API_KEYS_FINGERPRINT={_fingerprint_env('ACU_API_KEYS')}")
    print(f"ACU_REQUIRE_API_KEY={os.environ.get('ACU_REQUIRE_API_KEY', 'true')}")
    print("Secrets: NOT PRINTED")
    print("===============================\n")


if __name__ == "__main__":
    set_default_env()
    print_safe_summary()

    host = os.environ.get("ACU_HOST", "127.0.0.1")
    port = int(os.environ.get("ACU_PORT", "8013"))

    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        log_level="debug",
        reload=False,
        workers=1,
    )
