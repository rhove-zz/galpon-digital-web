"""Monitoring routes for sessions and audit logs."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.schemas import (
    AgentSessionResponse,
    ApiAccessLogResponse,
    ConversationTurnResponse,
    ToolAuditResponse,
)

router = APIRouter(tags=["monitoring"])


@router.get(
    "/sessions",
    response_model=List[AgentSessionResponse],
)
async def list_sessions(
    request: Request,
    domain: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    """List persisted agent sessions."""
    db = request.app.state.database_provider()
    result = db.list_agent_sessions(domain=domain, status=status, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", [])


@router.get(
    "/sessions/{session_id}/context",
    response_model=List[ConversationTurnResponse],
)
async def get_session_context(
    session_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
):
    """List persisted conversation turns for a session."""
    db = request.app.state.database_provider()
    result = db.get_conversation_context(session_id=session_id, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", [])


@router.get(
    "/tools/executions",
    response_model=List[ToolAuditResponse],
)
async def list_tool_executions(
    request: Request,
    tool_name: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """List persisted tool execution audit rows."""
    db = request.app.state.database_provider()
    result = db.list_tool_executions(
        tool_name=tool_name,
        success=success,
        limit=limit,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", [])


@router.get(
    "/api/access-log",
    response_model=List[ApiAccessLogResponse],
)
async def list_api_access_log(
    request: Request,
    path: Optional[str] = None,
    status_code: Optional[int] = Query(default=None, ge=100, le=599),
    authorized: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """List persisted API access audit rows."""
    db = request.app.state.database_provider()
    result = db.list_api_access_log(
        path=path,
        status_code=status_code,
        authorized=authorized,
        limit=limit,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", [])
