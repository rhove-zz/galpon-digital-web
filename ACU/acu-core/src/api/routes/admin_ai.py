"""Admin-only AI validation routes."""

import asyncio
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.llm.gemini_client import GeminiClient
from src.llm.runtime_flags import (
    ai_runtime_safety_allows_gemini,
    ai_runtime_safety_state,
    set_gemini_runtime_override,
)

router = APIRouter(prefix="/admin/ai", tags=["admin"])

SYNTHETIC_GEMINI_SMOKE_PROMPT = (
    "Responde con una frase corta indicando que el smoke Gemini controlado funciona. "
    "No uses datos reales."
)
DIRECT_SMOKE_TIMEOUT_SECONDS = 8


@router.post("/gemini/smoke")
async def direct_gemini_smoke(request: Request):
    """Run one direct Gemini smoke with synthetic data and fail-closed cleanup."""
    if not ai_runtime_safety_allows_gemini():
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Gemini smoke requires tools and writes disabled",
                "safety": ai_runtime_safety_state(),
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
            return _smoke_response(
                ok=False,
                error_code="GEMINI_EMPTY_OR_FAILED_RESPONSE",
            )
        return _smoke_response(ok=True, response_text=str(response))
    except asyncio.TimeoutError:
        return _smoke_response(ok=False, error_code="GEMINI_TIMEOUT")
    except Exception as exc:
        return _smoke_response(
            ok=False,
            error_code=f"GEMINI_EXCEPTION_{exc.__class__.__name__}",
        )
    finally:
        set_gemini_runtime_override(enabled=False, updated_by="direct_admin_smoke")


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
    clean = re.sub(r"[\r\n\t]+", " ", str(text)).strip()
    return clean[:200]


def _sanitize_code(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9_]", "_", str(text).upper())[:80]
