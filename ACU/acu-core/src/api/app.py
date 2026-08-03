"""FastAPI application entrypoint for ACU."""

import os
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.dashboard import STATIC_DIR
from src.api.routes.admin_ai import router as admin_ai_router
from src.api.routes.api_keys import router as api_keys_router
from src.api.routes.ai_runtime import router as ai_runtime_router
from src.api.routes.braincore import router as braincore_router
from src.api.routes.chat import router as chat_router
from src.api.routes.monitoring import router as monitoring_router
from src.api.routes.system import create_system_router
from src.api.routes.tools import router as tools_router
from src.config.settings import system_config
from src.api.scheduler import start_scheduler, shutdown_scheduler
from src.api.security import (
    build_api_key_roles as _build_api_key_roles,
    client_ip as _client_ip,
    extract_api_key as _extract_api_key,
    fingerprint_key as _fingerprint_key,
    has_required_role as _has_required_role,
    is_public_path as _is_public_path,
    required_roles as _required_roles,
    resolve_api_key as _resolve_api_key,
)
from src.api.telemetry import setup_telemetry
from src.memory.redis_manager import redis_manager


AgentProvider = Callable[[str], Awaitable[Any]]
BrainCoreProvider = Callable[[], Any]
DatabaseProvider = Callable[[], Any]
AccessAuditProvider = Callable[[], Any]
ApiKeyProvider = Callable[[], Any]

API_CONTRACT_VERSION = "v1"
API_STABILITY = "stable"


def _hash_key(api_key: str) -> str:
    """Backward-compatible alias for historical imports from app.py."""
    from src.api.security import hash_key

    return hash_key(api_key)


async def default_agent_provider(domain: str, persona: str = "default"):
    """Load the ACU agent lazily so lightweight endpoints stay cheap."""
    from src.agent.agent_loop import get_agent

    return await get_agent(domain=domain, persona=persona)


def default_braincore_provider():
    """Load BrainCore lazily so system endpoints stay lightweight."""
    from src.braincore.manager import get_braincore_manager

    return get_braincore_manager()


def default_database_provider():
    """Load read-only database connector lazily for monitoring endpoints."""
    from src.memory.mysql_manager import get_db_connector

    return get_db_connector(use_read_only=True)


def default_access_audit_provider():
    """Load write database connector lazily for API access auditing."""
    from src.memory.mysql_manager import get_db_connector

    return get_db_connector(use_read_only=False)


def default_api_key_provider():
    """Load write database connector lazily for managed API keys."""
    from src.memory.mysql_manager import get_db_connector

    return get_db_connector(use_read_only=False)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    start_scheduler(context="api")
    await redis_manager.connect()
    yield
    shutdown_scheduler()
    await redis_manager.disconnect()


def create_app(
    agent_provider: AgentProvider = default_agent_provider,
    braincore_provider: BrainCoreProvider = default_braincore_provider,
    database_provider: DatabaseProvider = default_database_provider,
    access_audit_provider: AccessAuditProvider = default_access_audit_provider,
    api_key_provider: ApiKeyProvider = default_api_key_provider,
    api_key: Optional[str] = None,
    api_keys: Optional[Dict[str, List[str]]] = None,
    api_auth_required: Optional[bool] = None,
    cors_origins: Optional[List[str]] = None,
    max_request_body_bytes: Optional[int] = None,
    rate_limit_requests: Optional[int] = None,
    rate_limit_window_seconds: Optional[int] = None,
) -> FastAPI:
    """Create and configure the ACU API application."""
    api = FastAPI(
        title=system_config.project_name,
        version=system_config.version,
        description="API REST para el Agente Cognitivo Universal.",
        lifespan=app_lifespan,
    )
    api.openapi = lambda: _custom_openapi(api)  # type: ignore[method-assign]

    # Configure OpenTelemetry
    setup_telemetry(api)

    configured_cors_origins = (
        _parse_csv(system_config.api_cors_origins)
        if cors_origins is None
        else cors_origins
    )
    if configured_cors_origins:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=configured_cors_origins,
            allow_credentials=system_config.api_cors_allow_credentials,
            allow_methods=_parse_csv(system_config.api_cors_methods) or ["GET"],
            allow_headers=_parse_csv(system_config.api_cors_headers) or ["*"],
        )
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    from src.api.webhooks import router as webhooks_router

    api.include_router(webhooks_router)

    api.state.cors_enabled = bool(configured_cors_origins)
    api.state.cors_origins = configured_cors_origins
    api.state.agent_provider = agent_provider
    api.state.braincore_provider = braincore_provider
    api.state.database_provider = database_provider
    api.state.access_audit_provider = access_audit_provider
    api.state.api_key_provider = api_key_provider
    api.state.agent_initialized = False
    api.state.api_keys = _build_api_key_roles(api_key=api_key, api_keys=api_keys)
    api.state.secure_runtime = bool(system_config.is_secure_runtime)
    api.state.api_auth_required = _resolve_api_auth_required(api_auth_required)
    _validate_api_key_configuration(api.state.api_keys, api.state.api_auth_required)
    api.state.max_request_body_bytes = (
        system_config.api_max_request_body_bytes
        if max_request_body_bytes is None
        else int(max_request_body_bytes)
    )
    api.state.rate_limit_requests = (
        system_config.api_rate_limit_requests
        if rate_limit_requests is None
        else int(rate_limit_requests)
    )
    api.state.rate_limit_window_seconds = (
        system_config.api_rate_limit_window_seconds
        if rate_limit_window_seconds is None
        else int(rate_limit_window_seconds)
    )
    api.state.rate_limit_buckets = {}

    @api.middleware("http")
    async def add_api_contract_headers(request: Request, call_next):
        """Publish the active API contract version on every response."""
        response = await call_next(request)
        response.headers["X-ACU-API-Version"] = API_CONTRACT_VERSION
        response.headers["X-ACU-API-Stability"] = API_STABILITY
        return response

    @api.middleware("http")
    async def enforce_request_body_size(request: Request, call_next):
        """Reject requests with a Content-Length larger than the configured limit."""
        max_body_bytes = int(
            getattr(request.app.state, "max_request_body_bytes", 0) or 0
        )
        content_length = request.headers.get("content-length")
        if max_body_bytes > 0 and content_length:
            try:
                request_body_bytes = int(content_length)
            except ValueError:
                request_body_bytes = 0
            if request_body_bytes > max_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            "Request body excede el limite configurado "
                            f"de {max_body_bytes} bytes"
                        )
                    },
                )
        return await call_next(request)

    @api.middleware("http")
    async def enforce_rate_limit(request: Request, call_next):
        """Apply an in-memory or Redis-based fixed-window rate limit when configured."""
        rate_limit_response = await _rate_limit_response(request)
        if rate_limit_response:
            return rate_limit_response
        return await call_next(request)

    @api.middleware("http")
    async def enforce_api_key(request: Request, call_next):
        """Require API key and role when configured."""
        started_at = time.perf_counter()
        auth_enabled = bool(request.app.state.api_keys) or bool(
            request.app.state.api_auth_required
        )
        allow_operational_public = bool(
            system_config.allow_operational_public_routes
            and not getattr(request.app.state, "secure_runtime", False)
        )
        if (
            _is_public_path(
                request.url.path,
                allow_operational_public=allow_operational_public,
            )
            or not auth_enabled
        ):
            return await call_next(request)

        provided_key = _extract_api_key(request)
        key_identity = _resolve_api_key(request, provided_key)
        roles = key_identity["roles"]
        key_fingerprint = key_identity["fingerprint"]
        if not roles:
            response = JSONResponse(
                status_code=401,
                content={"detail": "API key requerida o invalida"},
            )
            _audit_api_access(
                request=request,
                status_code=response.status_code,
                key_fingerprint=key_fingerprint,
                roles=set(),
                authorized=False,
                duration_ms=_elapsed_ms(started_at),
            )
            return response
        required_roles = _required_roles(request.method, request.url.path)
        if not _has_required_role(roles=roles, required_roles=required_roles):
            response = JSONResponse(
                status_code=403,
                content={"detail": "Rol insuficiente para este endpoint"},
            )
            _audit_api_access(
                request=request,
                status_code=response.status_code,
                key_fingerprint=key_fingerprint,
                roles=roles,
                authorized=False,
                duration_ms=_elapsed_ms(started_at),
            )
            return response
        response = await call_next(request)
        _audit_api_access(
            request=request,
            status_code=response.status_code,
            key_fingerprint=key_fingerprint,
            roles=roles,
            authorized=True,
            duration_ms=_elapsed_ms(started_at),
        )
        return response

    api.include_router(
        create_system_router(
            api_contract_version=API_CONTRACT_VERSION,
            api_stability=API_STABILITY,
        )
    )
    api.include_router(chat_router)
    api.include_router(braincore_router)
    api.include_router(monitoring_router)
    api.include_router(api_keys_router)
    api.include_router(tools_router)
    api.include_router(ai_runtime_router)
    api.include_router(admin_ai_router)

    return api


def _parse_csv(raw_value: str) -> List[str]:
    """Parse a comma-separated configuration value."""
    return [item.strip() for item in str(raw_value or "").split(",") if item.strip()]


def _resolve_api_auth_required(api_auth_required: Optional[bool]) -> bool:
    """Return effective auth policy, failing closed for secure runtimes."""
    requested = (
        system_config.api_auth_required
        if api_auth_required is None
        else bool(api_auth_required)
    )
    if system_config.is_secure_runtime and not requested:
        raise RuntimeError(
            "ACU_API_AUTH_REQUIRED cannot be disabled in staging/production"
        )
    return bool(requested)


def _validate_api_key_configuration(
    api_keys: Dict[str, Set[str]],
    auth_required: bool,
) -> None:
    """Fail closed when secure runtimes require auth but no API key is configured."""
    if (
        system_config.is_secure_runtime
        and auth_required
        and system_config.require_api_key
        and not api_keys
    ):
        raise RuntimeError(
            "ACU_API_KEY or ACU_API_KEYS is required in staging/production"
        )


async def _rate_limit_response(request: Request) -> Optional[JSONResponse]:
    """Return a 429 response when the request exceeds the configured rate limit."""
    if request.method.upper() == "OPTIONS" or request.url.path.startswith("/static/"):
        return None

    max_requests = int(getattr(request.app.state, "rate_limit_requests", 0) or 0)
    window_seconds = int(
        getattr(request.app.state, "rate_limit_window_seconds", 60) or 60
    )
    if max_requests <= 0 or window_seconds <= 0:
        return None

    identity = _rate_limit_identity(request)

    # Usar Redis si está habilitado y conectado
    if redis_manager.enabled and redis_manager.redis:
        is_limited = await redis_manager.is_rate_limited(
            identity=identity, limit=max_requests, window=window_seconds
        )
        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Rate limit excedido (Redis). Intenta nuevamente "
                        f"en {window_seconds} segundos."
                    )
                },
                headers={"Retry-After": str(window_seconds)},
            )
        return None

    # Fallback In-Memory
    now = time.monotonic()
    buckets = request.app.state.rate_limit_buckets
    requests = buckets.setdefault(identity, [])
    cutoff = now - window_seconds
    requests[:] = [timestamp for timestamp in requests if timestamp > cutoff]

    if len(requests) >= max_requests:
        retry_after = max(1, int(window_seconds - (now - requests[0])))
        return JSONResponse(
            status_code=429,
            content={
                "detail": (
                    "Rate limit excedido. Intenta nuevamente "
                    f"en {retry_after} segundos."
                )
            },
            headers={"Retry-After": str(retry_after)},
        )

    requests.append(now)
    return None


def _rate_limit_identity(request: Request) -> str:
    """Build a rate limit identity from API key fingerprint or client IP."""
    api_key = _extract_api_key(request)
    if api_key:
        return f"key:{_fingerprint_key(api_key)}"
    return f"ip:{_client_ip(request)}"


def _audit_api_access(
    request: Request,
    status_code: int,
    key_fingerprint: str,
    roles: Set[str],
    authorized: bool,
    duration_ms: float,
) -> None:
    """Persist API access audit without interrupting the request flow."""
    if _skip_access_audit_for_read_only_staging():
        return

    try:
        connector = request.app.state.access_audit_provider()
        if not hasattr(connector, "log_api_access"):
            return
        connector.log_api_access(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            key_fingerprint=key_fingerprint,
            roles=sorted(roles),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            authorized=authorized,
            duration_ms=duration_ms,
        )
    except Exception:
        return


def _skip_access_audit_for_read_only_staging() -> bool:
    """Avoid blocking read-only secure responses on optional write-audit storage."""
    explicit_read_only = os.getenv("ACU_READ_ONLY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    production_read_only = bool(getattr(system_config, "production_read_only", False))
    return bool(
        system_config.is_secure_runtime
        and (explicit_read_only or production_read_only)
        and not system_config.write_tools_enabled
    )


def _elapsed_ms(started_at: float) -> float:
    """Return elapsed milliseconds from a perf_counter start value."""
    return (time.perf_counter() - started_at) * 1000


def _custom_openapi(api: FastAPI) -> Dict[str, Any]:
    """Return OpenAPI schema annotated with ACU contract metadata."""
    if api.openapi_schema:
        return api.openapi_schema

    openapi_schema = get_openapi(
        title=api.title,
        version=api.version,
        description=api.description,
        routes=api.routes,
    )
    info = openapi_schema.setdefault("info", {})
    info["x-acu-api-version"] = API_CONTRACT_VERSION
    info["x-acu-api-stability"] = API_STABILITY
    info["x-acu-breaking-change-policy"] = (
        "Breaking changes require a new API contract version; compatible additions "
        "remain in the active v1 surface."
    )
    openapi_schema["servers"] = [
        {
            "url": "/",
            "description": f"ACU API {API_CONTRACT_VERSION} compatibility surface",
        }
    ]
    api.openapi_schema = openapi_schema
    return api.openapi_schema


app = create_app()
