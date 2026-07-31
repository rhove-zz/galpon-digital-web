"""System, dashboard and operational monitoring routes."""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from src.api.dashboard import get_dashboard_html
from src.api.readiness import build_system_readiness
from src.api.scheduler import get_scheduler_status
from src.api.schemas import (
    ApiVersionResponse,
    SystemMetricsResponse,
    SystemReadinessResponse,
)
from src.config.settings import system_config
from src.llm.gemini_client import GeminiClient
from src.memory.redis_manager import redis_manager


def create_system_router(api_contract_version: str, api_stability: str) -> APIRouter:
    """Create routes for health, dashboard, metrics and readiness."""
    router = APIRouter()

    @router.get("/", tags=["system"], include_in_schema=False)
    async def root_check():
        """Return a minimal public response for platform port checks."""
        return {
            "status": "ok",
            "service": system_config.project_name,
        }

    @router.head("/", tags=["system"], include_in_schema=False)
    async def root_head_check():
        """Return a minimal public response for platform port checks."""
        return HTMLResponse(status_code=200)

    @router.get("/health", tags=["system"])
    async def health_check():
        """Return API health and version metadata."""
        return {
            "status": "ok",
            "service": system_config.project_name,
            "version": system_config.version,
        }

    @router.get(
        "/api/version",
        response_model=ApiVersionResponse,
        tags=["system"],
    )
    async def api_version():
        """Return the published API contract version."""
        return {
            "service": system_config.project_name,
            "runtime_version": system_config.version,
            "api_version": api_contract_version,
            "stability": api_stability,
            "openapi_url": "/openapi.json",
        }

    @router.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
    async def dashboard():
        """Return the operational monitoring dashboard."""
        return HTMLResponse(get_dashboard_html())

    @router.get(
        "/system/metrics",
        response_model=SystemMetricsResponse,
        tags=["monitoring"],
    )
    async def get_system_metrics(request: Request):
        """Return system-level operational metrics for monitoring."""
        manager = request.app.state.braincore_provider()
        result = manager.get_vector_status()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        pending_tools = await redis_manager.get_all_pending_tools()
        return {
            "service": system_config.project_name,
            "version": system_config.version,
            "vector_store": result.get("data", {}),
            "api_auth_required": bool(request.app.state.api_auth_required),
            "rate_limit_enabled": bool(request.app.state.rate_limit_requests),
            "payload_limit_enabled": bool(request.app.state.max_request_body_bytes),
            "cors_enabled": bool(getattr(request.app.state, "cors_enabled", False)),
            "pending_tools": _summarize_pending_tools(pending_tools),
            "scheduler": get_scheduler_status(),
            "redis": {
                "enabled": bool(redis_manager.enabled),
                "connected": bool(redis_manager.redis),
                "backend": "redis"
                if redis_manager.enabled and redis_manager.redis
                else "local",
            },
            "webhooks": await _get_webhook_metrics(),
        }

    @router.get(
        "/system/readiness",
        response_model=SystemReadinessResponse,
        tags=["monitoring"],
    )
    async def get_system_readiness(request: Request):
        """Return runtime readiness checks for exposed environments."""
        try:
            return build_system_readiness(
                request=request,
                api_contract_version=api_contract_version,
                api_stability=api_stability,
            )
        except Exception:
            return {
                "service": system_config.project_name,
                "version": system_config.version,
                "api_version": api_contract_version,
                "status": "warning",
                "summary": {"passed": 0, "warnings": 1, "failed": 0},
                "checks": [
                    {
                        "name": "readiness_runtime",
                        "status": "warning",
                        "severity": "warning",
                        "detail": (
                            "Readiness operativo disponible con diagnostico "
                            "interno sanitizado no bloqueante"
                        ),
                    }
                ],
            }

    @router.post("/system/gemini-smoke", tags=["monitoring"])
    async def gemini_smoke():
        """Run a direct Gemini adapter smoke without ReAct, tools or writes."""
        client = GeminiClient()
        result: Dict[str, Any] = {
            "gemini_enabled": bool(client.enabled),
            "api_key_configured": bool(client.api_key_configured),
            "model": client.model,
            "timeout_seconds": client.timeout_seconds,
            "tools_executed": 0,
            "writes_executed": 0,
            "response_text_returned": False,
        }
        if not client.enabled or not client.api_key_configured:
            result["smoke_status"] = "disabled_or_missing_secret"
            return result

        response = client.generate_response(
            system_prompt=(
                "You are running a production readiness smoke. "
                "Answer with a short synthetic confirmation only. "
                "Do not use tools. Do not write data."
            ),
            user_message="R55 synthetic direct Gemini smoke. No tools. No writes.",
            conversation_history=[],
            temperature=0.0,
            top_p=0.8,
        )
        result["smoke_status"] = "ok" if response else "failed"
        result["response_present"] = bool(response)
        return result

    return router


def _summarize_pending_tools(tools: List[dict]) -> Dict[str, int]:
    """Aggregate pending tool records by HITL status."""
    summary = {
        "total": len(tools),
        "pending": 0,
        "approved": 0,
        "executed": 0,
        "failed": 0,
        "rejected": 0,
        "resumed": 0,
    }
    for tool in tools:
        status = str(tool.get("status", "")).strip().lower()
        if status in summary and status != "total":
            summary[status] += 1
    return summary


async def _get_webhook_metrics() -> Dict[str, Any]:
    """Return webhook metrics without making app startup depend on webhooks internals."""
    try:
        from src.api.webhooks import get_webhook_metrics

        return await get_webhook_metrics()
    except Exception:
        return {"total": {}, "channels": {}}
