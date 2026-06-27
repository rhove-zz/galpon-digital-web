"""Chat API routes."""

import logging
import os
from typing import Any, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.agent_runtime import get_initialized_agent
from src.api.schemas import ChatRequest, ChatResponse, ToolExecutionResponse
from src.config.settings import ollama_config, system_config

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    """Process one chat turn through the ACU agent."""
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="message no puede estar vacio")

    if _should_short_circuit_to_fallback():
        logger.warning("ACU chat fallback activated: model runtime disabled")
        return _read_only_fallback_response(payload)

    try:
        agent = await get_initialized_agent(
            request.app, payload.domain.strip(), payload.persona, payload.session_id
        )
    except HTTPException as exc:
        if exc.status_code == 503 and _read_only_fallback_enabled():
            logger.warning("ACU chat fallback activated: agent unavailable")
            return _read_only_fallback_response(payload)
        raise
    except Exception:
        if _read_only_fallback_enabled():
            logger.warning("ACU chat fallback activated: runtime unavailable")
            return _read_only_fallback_response(payload)
        raise

    tools_manager = getattr(agent, "tools_manager", None)
    tool_log_before = _count_tool_log(tools_manager)
    iterations_before = int(getattr(agent, "total_iterations", 0))

    try:
        response_text = await agent.process_user_message(user_message)
    except Exception as exc:
        if _read_only_fallback_enabled():
            logger.warning("ACU chat fallback activated: processing unavailable")
            return _read_only_fallback_response(payload)
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


def _read_only_fallback_enabled() -> bool:
    """Return True when staging can answer safely without model/tools runtime."""
    explicit_read_only = os.getenv("ACU_READ_ONLY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return bool(
        system_config.is_secure_runtime
        and system_config.safe_mode
        and (explicit_read_only or not system_config.write_tools_enabled)
        and not system_config.external_tools_enabled
    )


def _should_short_circuit_to_fallback() -> bool:
    """Avoid slow model initialization when staging has no AI runtime enabled."""
    if not _read_only_fallback_enabled():
        return False

    gemini_enabled = os.getenv("GEMINI_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    local_ollama_host = str(ollama_config.host or "").strip().lower() in {
        "http://localhost",
        "http://127.0.0.1",
        "localhost",
        "127.0.0.1",
    }
    return bool(not gemini_enabled and system_config.is_secure_runtime and local_ollama_host)


def _read_only_fallback_response(payload: ChatRequest) -> ChatResponse:
    """Return a safe read-only response when optional AI runtime is unavailable."""
    session_id = payload.session_id or f"fallback:{payload.domain.strip() or 'generic'}"
    return ChatResponse(
        session_id=session_id,
        response=(
            "ACU esta disponible en modo seguro de solo lectura. "
            "En esta prueba staging no se pudo usar el motor cognitivo completo, "
            "por eso no se ejecutaron herramientas, escrituras ni acciones externas. "
            "Puedes repetir la consulta cuando el servicio de IA este habilitado."
        ),
        iterations=0,
        tool_calls=[],
    )
