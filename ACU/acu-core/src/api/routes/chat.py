"""Chat API routes."""

from typing import Any, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.agent_runtime import get_initialized_agent
from src.api.schemas import ChatRequest, ChatResponse, ToolExecutionResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    """Process one chat turn through the ACU agent."""
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="message no puede estar vacio")

    agent = await get_initialized_agent(
        request.app, payload.domain.strip(), payload.persona, payload.session_id
    )
    tools_manager = getattr(agent, "tools_manager", None)
    tool_log_before = _count_tool_log(tools_manager)
    iterations_before = int(getattr(agent, "total_iterations", 0))

    try:
        response_text = await agent.process_user_message(user_message)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando mensaje: {exc}",
        ) from exc

    iterations_after = int(getattr(agent, "total_iterations", iterations_before))
    tool_calls = _serialize_tool_calls(tools_manager, tool_log_before)

    return ChatResponse(
        session_id=str(getattr(agent, "session_id", "")),
        response=response_text,
        iterations=max(iterations_after - iterations_before, 0),
        tool_calls=tool_calls,
    )


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request):
    """Process one chat turn through the ACU agent with SSE streaming."""
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="message no puede estar vacio")

    agent = await get_initialized_agent(
        request.app, payload.domain.strip(), payload.persona, payload.session_id
    )

    return StreamingResponse(
        agent.process_user_message_stream(user_message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _count_tool_log(tools_manager: Any) -> int:
    """Count current tool executions if the manager exposes a log."""
    if not tools_manager or not hasattr(tools_manager, "get_execution_log"):
        return 0
    return len(tools_manager.get_execution_log())


def _serialize_tool_calls(
    tools_manager: Any,
    start_index: int,
) -> List[ToolExecutionResponse]:
    """Serialize tool executions produced by the current chat turn."""
    if not tools_manager or not hasattr(tools_manager, "get_execution_log"):
        return []

    tool_results = tools_manager.get_execution_log()[start_index:]
    serialized: List[ToolExecutionResponse] = []
    for tool_result in tool_results:
        serialized.append(
            ToolExecutionResponse(
                tool=_serialize_tool_name(getattr(tool_result, "tool", "")),
                success=bool(getattr(tool_result, "success", False)),
                result=getattr(tool_result, "result", None),
                error=getattr(tool_result, "error", None),
                execution_time_ms=float(getattr(tool_result, "execution_time_ms", 0.0)),
            )
        )
    return serialized


def _serialize_tool_name(tool: Any) -> str:
    """Return enum values as stable API strings."""
    return str(getattr(tool, "value", tool))
