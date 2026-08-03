"""Chat API routes."""

import logging
import os
from typing import Any, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.agent_runtime import get_initialized_agent
from src.api.schemas import ChatRequest, ChatResponse, ToolExecutionResponse
from src.config.settings import ollama_config, system_config
from src.llm.cost_guard import evaluate_ai_request, record_ai_request
from src.llm.gemini_client import GeminiClient
from src.llm.runtime_flags import is_gemini_runtime_enabled
from src.tools.tools_manager import get_tools_manager
from src.utils.schemas import ToolCall, ToolType

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)
R62_MINIMAL_READ_ONLY_TOOL_ALLOWLIST = {"buscar_contexto_braincore"}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    """Process one chat turn through the ACU agent."""
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="message no puede estar vacio")

    if _should_use_direct_read_only_gemini():
        response = _direct_read_only_gemini_response(payload)
        if response is not None:
            return response
        logger.warning("ACU chat fallback activated: direct Gemini unavailable")
        return _read_only_fallback_response(payload)

    if _minimal_read_only_tools_runtime_enabled():
        response = await _direct_braincore_read_only_tool_response(payload)
        if response is not None:
            return response
        logger.warning("ACU chat fallback activated: direct BrainCore path unavailable")
        return _read_only_fallback_response(payload)

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

    gemini_enabled = is_gemini_runtime_enabled()
    local_ollama_host = str(ollama_config.host or "").strip().lower() in {
        "http://localhost",
        "http://127.0.0.1",
        "localhost",
        "127.0.0.1",
    }
    return bool(not gemini_enabled and system_config.is_secure_runtime and local_ollama_host)


def _should_use_direct_read_only_gemini() -> bool:
    """Route chat through Gemini directly when action-capable runtime is frozen."""
    return bool(
        _read_only_fallback_enabled()
        and is_gemini_runtime_enabled()
        and not _minimal_read_only_tools_runtime_enabled()
        and not system_config.web_tools_enabled
        and not system_config.filesystem_write_enabled
        and not system_config.write_tools_enabled
        and not system_config.external_tools_enabled
        and not system_config.api_rest_enabled
    )


def _minimal_read_only_tools_runtime_enabled() -> bool:
    """Return True only for the R62 one-tool read-only ReAct path."""
    allowed_tools = _configured_tool_names(getattr(system_config, "allowed_tools", ""))
    return bool(
        _read_only_fallback_enabled()
        and is_gemini_runtime_enabled()
        and bool(getattr(system_config, "tools_enabled", False))
        and bool(getattr(system_config, "read_only_tools_enabled", False))
        and allowed_tools == R62_MINIMAL_READ_ONLY_TOOL_ALLOWLIST
        and not system_config.web_tools_enabled
        and not system_config.filesystem_write_enabled
        and not system_config.write_tools_enabled
        and not system_config.external_tools_enabled
        and not system_config.api_rest_enabled
    )


def _configured_tool_names(raw_value: str) -> set[str]:
    """Parse comma-separated tool names into a normalized set."""
    return {
        item.strip()
        for item in str(raw_value or "").split(",")
        if item.strip()
    }


def _direct_read_only_gemini_response(payload: ChatRequest) -> ChatResponse | None:
    """Generate a chat response without initializing ReAct, tools or writes."""
    client = GeminiClient()
    if not client.enabled or not client.api_key_configured:
        return None

    max_output_tokens = int(getattr(client, "max_tokens", os.getenv("GEMINI_MAX_TOKENS", "1024")))
    cost_guard = evaluate_ai_request(payload.message.strip(), max_output_tokens)
    if not cost_guard.allowed:
        logger.warning("ACU chat blocked before Gemini by AI cost guard")
        return _cost_guard_blocked_response(payload)
    record_ai_request(cost_guard)

    response_text = client.generate_response(
        system_prompt=(
            "Eres ACU en modo produccion read-only. Responde de forma breve, "
            "util y segura. No uses herramientas. No escribas datos. "
            "No ejecutes acciones externas."
        ),
        user_message=payload.message.strip(),
        conversation_history=[],
        temperature=0.2,
        top_p=0.8,
        skip_cost_guard=True,
    )
    if not response_text:
        return None

    session_id = payload.session_id or f"gemini-direct:{payload.domain.strip() or 'generic'}"
    return ChatResponse(
        session_id=session_id,
        response=response_text,
        iterations=1,
        tool_calls=[],
    )


async def _direct_braincore_read_only_tool_response(
    payload: ChatRequest,
) -> ChatResponse | None:
    """Run the single approved BrainCore read-only tool without full ReAct."""
    client = GeminiClient()
    if not client.enabled or not client.api_key_configured:
        return None

    max_output_tokens = int(getattr(client, "max_tokens", os.getenv("GEMINI_MAX_TOKENS", "1024")))
    cost_guard = evaluate_ai_request(payload.message.strip(), max_output_tokens)
    if not cost_guard.allowed:
        logger.warning("ACU BrainCore path blocked before Gemini by AI cost guard")
        return _cost_guard_blocked_response(payload)
    record_ai_request(cost_guard)

    session_id = payload.session_id or f"braincore-direct:{payload.domain.strip() or 'generic'}"
    try:
        tools_manager = get_tools_manager()
        tool_call = ToolCall(
            tool=ToolType.BRAINCORE_SEARCH,
            parameters={
                "consulta": payload.message.strip(),
                "domain": payload.domain.strip() or "production",
                "top_k": 3,
            },
            reasoning="R62C direct read-only BrainCore context retrieval",
        )
        tool_result = await tools_manager.execute_tool(
            tool_call,
            session_id=session_id,
            require_approval=False,
            agent_domain=payload.domain.strip() or "production",
            agent_persona=payload.persona.strip() or "default",
        )
        serialized_tool = ToolExecutionResponse(
            tool=_serialize_tool_name(getattr(tool_result, "tool", "")),
            success=bool(getattr(tool_result, "success", False)),
            result=getattr(tool_result, "result", None),
            error=getattr(tool_result, "error", None),
            execution_time_ms=float(getattr(tool_result, "execution_time_ms", 0.0)),
        )
    except Exception as exc:
        logger.warning(
            "ACU direct BrainCore read-only tool failed safely: %s",
            exc.__class__.__name__,
        )
        serialized_tool = ToolExecutionResponse(
            tool=ToolType.BRAINCORE_SEARCH.value,
            success=False,
            result=None,
            error="BrainCore read-only tool failed safely",
            execution_time_ms=0.0,
        )
    context = _format_braincore_context(serialized_tool)
    response_text = client.generate_response(
        system_prompt=(
            "Eres ACU en modo produccion read-only con una unica herramienta "
            "permitida: buscar_contexto_braincore. Usa solo el contexto provisto. "
            "No ejecutes SQL, web, API REST, filesystem, Python, escrituras ni "
            "acciones externas. Si el contexto no alcanza, dilo de forma breve."
        ),
        user_message=(
            f"Pregunta del usuario:\n{payload.message.strip()}\n\n"
            f"Contexto BrainCore read-only:\n{context}"
        ),
        conversation_history=[],
        temperature=0.2,
        top_p=0.8,
        skip_cost_guard=True,
    )
    if not response_text:
        response_text = (
            "ACU ejecuto una consulta read-only de BrainCore, pero no pudo generar "
            "una respuesta ampliada desde Gemini. No se ejecutaron herramientas "
            "adicionales, escrituras ni acciones externas."
        )

    return ChatResponse(
        session_id=session_id,
        response=response_text,
        iterations=1,
        tool_calls=[serialized_tool],
    )


def _format_braincore_context(tool: ToolExecutionResponse) -> str:
    """Format bounded BrainCore results for the direct Gemini prompt."""
    if not tool.success:
        return f"BrainCore no devolvio contexto util: {tool.error or 'sin detalle'}"

    results = tool.result if isinstance(tool.result, list) else []
    if not results:
        return "BrainCore no encontro resultados para esta consulta."

    lines: list[str] = []
    for index, item in enumerate(results[:3], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("source_path") or "Contexto")
        content = " ".join(str(item.get("content") or "").split())
        if len(content) > 500:
            content = f"{content[:500]}..."
        lines.append(f"{index}. {title}: {content}")

    return "\n".join(lines) if lines else "BrainCore no encontro resultados utilizables."


def _cost_guard_blocked_response(payload: ChatRequest) -> ChatResponse:
    """Return a safe response when the AI cost guard blocks model execution."""
    session_id = payload.session_id or f"guard-blocked:{payload.domain.strip() or 'generic'}"
    return ChatResponse(
        session_id=session_id,
        response=(
            "ACU esta disponible en modo seguro de solo lectura. "
            "La solicitud fue detenida por controles operativos de IA. "
            "No se ejecutaron herramientas, escrituras ni acciones externas."
        ),
        iterations=0,
        tool_calls=[],
    )


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
