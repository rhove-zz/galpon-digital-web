"""Human-in-the-loop tool approval routes."""

from fastapi import APIRouter, HTTPException, Request

from src.api.agent_runtime import get_initialized_agent
from src.memory.redis_manager import redis_manager

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/pending")
async def get_pending_tools():
    """Retrieve all currently pending tools for human authorization."""
    return await redis_manager.get_all_pending_tools()


@router.post("/pending/{tool_id}/approve")
async def approve_pending_tool(tool_id: str):
    """Approve and execute a pending tool call."""
    success = await redis_manager.resolve_pending_tool(tool_id, "approved")
    if not success:
        raise HTTPException(
            status_code=404, detail="Tool call no encontrado o expirado"
        )

    from src.tools.tools_manager import get_tools_manager

    result = await get_tools_manager().execute_pending_tool(tool_id)
    return {
        "success": result.success,
        "status": result.status,
        "pending_tool_id": tool_id,
        "result": result.result,
        "error": result.error,
    }


@router.post("/pending/{tool_id}/reject")
async def reject_pending_tool(tool_id: str):
    """Reject a pending tool call."""
    success = await redis_manager.resolve_pending_tool(tool_id, "rejected")
    if not success:
        raise HTTPException(
            status_code=404, detail="Tool call no encontrado o expirado"
        )
    return {"success": True, "status": "rejected"}


@router.post("/pending/{tool_id}/resume")
async def resume_pending_tool(tool_id: str, request: Request):
    """Resume the agent conversation after an approved tool execution."""
    pending_data = await redis_manager.get_pending_tool(tool_id)
    if not pending_data:
        raise HTTPException(
            status_code=404, detail="Tool call no encontrado o expirado"
        )
    if pending_data.get("status") not in {"executed", "failed"}:
        raise HTTPException(
            status_code=409,
            detail="Tool call debe estar ejecutado antes de reanudar",
        )

    session_id = str(pending_data.get("session_id", "")).strip()
    if not session_id:
        raise HTTPException(
            status_code=409,
            detail="Tool call no tiene session_id para reanudar",
        )

    agent = await get_initialized_agent(
        request.app,
        str(pending_data.get("domain", "generic")),
        str(pending_data.get("persona", "default")),
        session_id,
    )
    response_text = await agent.resume_after_tool_approval(
        {**pending_data, "id": tool_id}
    )
    pending_data["status"] = "resumed"
    pending_data["resumed_response"] = response_text
    await redis_manager.set_pending_tool(tool_id, pending_data)
    return {
        "success": True,
        "status": "resumed",
        "pending_tool_id": tool_id,
        "session_id": session_id,
        "response": response_text,
    }
