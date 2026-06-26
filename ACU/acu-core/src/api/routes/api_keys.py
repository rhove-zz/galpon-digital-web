"""Managed API key routes."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.schemas import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyResponse
from src.api.security import (
    extract_api_key,
    fingerprint_key,
    generate_api_key,
    hash_key,
    normalize_api_key_expires_at,
    normalize_roles,
    valid_roles,
)

router = APIRouter(prefix="/api/keys", tags=["security"])


@router.post(
    "",
    response_model=ApiKeyCreateResponse,
)
async def create_api_key(payload: ApiKeyCreateRequest, request: Request):
    """Create a managed API key and return the secret once."""
    normalized_roles = sorted(normalize_roles(payload.roles))
    invalid_roles = [role for role in normalized_roles if role not in valid_roles()]
    if invalid_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Roles invalidos: {', '.join(invalid_roles)}",
        )
    expires_at = normalize_api_key_expires_at(payload.expires_at)

    raw_key = generate_api_key()
    manager = request.app.state.api_key_provider()
    result = manager.create_api_key(
        name=payload.name.strip(),
        key_hash=hash_key(raw_key),
        key_fingerprint=fingerprint_key(raw_key),
        roles=normalized_roles,
        expires_at=expires_at,
        created_by=fingerprint_key(extract_api_key(request)),
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return {**result.get("data", {}), "api_key": raw_key}


@router.get(
    "",
    response_model=List[ApiKeyResponse],
)
async def list_api_keys(
    request: Request,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """List managed API key metadata without secrets."""
    manager = request.app.state.api_key_provider()
    result = manager.list_api_keys(status=status, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", [])


@router.post(
    "/{key_id}/revoke",
    response_model=ApiKeyResponse,
)
async def revoke_api_key(key_id: int, request: Request):
    """Revoke a managed API key."""
    manager = request.app.state.api_key_provider()
    result = manager.revoke_api_key(key_id=key_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result.get("data")
