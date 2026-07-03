"""Admin routes for controlled AI runtime feature flags."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.security import extract_api_key, fingerprint_key
from src.llm.runtime_flags import (
    MAX_GEMINI_TTL_SECONDS,
    ai_runtime_safety_allows_gemini,
    ai_runtime_safety_state,
    get_gemini_runtime_status,
    runtime_toggle_allowed_environment,
    set_gemini_runtime_override,
)

router = APIRouter(prefix="/system/ai-runtime", tags=["system"])


class GeminiRuntimeEnableRequest(BaseModel):
    ttl_seconds: Optional[int] = Field(default=300, ge=1, le=MAX_GEMINI_TTL_SECONDS)


@router.get("/gemini")
async def get_gemini_runtime_flag():
    """Return sanitized Gemini runtime flag state."""
    return {
        "gemini": get_gemini_runtime_status(),
        "safety": ai_runtime_safety_state(),
        "secret_values": "not_returned",
    }


@router.post("/gemini/enable")
async def enable_gemini_runtime_flag(
    payload: GeminiRuntimeEnableRequest,
    request: Request,
):
    """Temporarily enable Gemini for a controlled synthetic smoke."""
    if not runtime_toggle_allowed_environment():
        raise HTTPException(
            status_code=403,
            detail="Dynamic Gemini toggle is not allowed in this environment",
        )
    if not ai_runtime_safety_allows_gemini():
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Gemini toggle requires tools and writes disabled",
                "safety": ai_runtime_safety_state(),
            },
        )
    return {
        "gemini": set_gemini_runtime_override(
            enabled=True,
            ttl_seconds=payload.ttl_seconds,
            updated_by=fingerprint_key(extract_api_key(request)),
        ),
        "safety": ai_runtime_safety_state(),
        "secret_values": "not_returned",
    }


@router.post("/gemini/disable")
async def disable_gemini_runtime_flag(request: Request):
    """Disable the process-local Gemini override without redeploy."""
    return {
        "gemini": set_gemini_runtime_override(
            enabled=False,
            updated_by=fingerprint_key(extract_api_key(request)),
        ),
        "safety": ai_runtime_safety_state(),
        "secret_values": "not_returned",
    }
