"""API authentication, authorization and key utilities for ACU."""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, Request

from src.config.settings import system_config

RoleMap = Dict[str, Set[str]]

ESSENTIAL_PUBLIC_PATHS = {
    "/",
    "/health",
    "/api/version",
    "/favicon.ico",
}

OPERATIONAL_PUBLIC_PATHS = {
    "/dashboard",
    "/docs",
    "/openapi.json",
    "/redoc",
}

ROLE_ADMIN = "admin"
ROLE_CHAT = "chat"
ROLE_BRAINCORE_READ = "braincore_read"
ROLE_BRAINCORE_WRITE = "braincore_write"
ROLE_MONITORING = "monitoring"


def is_public_path(path: str, allow_operational_public: bool = True) -> bool:
    """Return True when the route must remain public."""
    if path in ESSENTIAL_PUBLIC_PATHS:
        return True
    if not allow_operational_public:
        return False
    return (
        path in OPERATIONAL_PUBLIC_PATHS
        or path.startswith("/docs/")
        or path.startswith("/static/")
    )


def extract_api_key(request: Request) -> str:
    """Extract the configured API key from supported headers."""
    header_key = request.headers.get("x-acu-api-key", "").strip()
    if header_key:
        return header_key

    authorization = request.headers.get("authorization", "").strip()
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix) :].strip()
    return ""


def build_api_key_roles(
    api_key: Optional[str] = None,
    api_keys: Optional[Dict[str, List[str]]] = None,
) -> RoleMap:
    """Build the active API key to roles map."""
    roles_by_key: RoleMap = {}

    legacy_key = system_config.api_key if api_key is None else api_key.strip()
    if legacy_key:
        roles_by_key[legacy_key] = {ROLE_ADMIN}

    configured_keys = (
        parse_api_keys(system_config.api_keys) if api_keys is None else api_keys
    )
    for key, roles in configured_keys.items():
        normalized_key = str(key).strip()
        normalized_roles = normalize_roles(roles)
        if normalized_key and normalized_roles:
            if normalized_key in roles_by_key:
                roles_by_key[normalized_key].update(normalized_roles)
            else:
                roles_by_key[normalized_key] = normalized_roles
    return roles_by_key


def parse_api_keys(raw_value: str) -> Dict[str, List[str]]:
    """Parse ACU_API_KEYS entries formatted as key=role1,role2;key2=admin."""
    parsed: Dict[str, List[str]] = {}
    for entry in raw_value.split(";"):
        item = entry.strip()
        if not item:
            continue
        separator = "=" if "=" in item else ":"
        if separator not in item:
            continue
        key, roles_value = item.split(separator, 1)
        roles = [role.strip() for role in roles_value.split(",") if role.strip()]
        if key.strip() and roles:
            parsed[key.strip()] = roles
    return parsed


def normalize_roles(roles: List[str]) -> Set[str]:
    """Normalize configured roles."""
    return {str(role).strip().lower() for role in roles if str(role).strip()}


def roles_for_api_key(provided_key: str, api_keys: RoleMap) -> Set[str]:
    """Return roles for a provided key using constant-time key comparison."""
    if not provided_key:
        return set()
    for expected_key, roles in api_keys.items():
        if hmac.compare_digest(provided_key, expected_key):
            return roles
    return set()


def resolve_api_key(request: Request, provided_key: str) -> Dict[str, Any]:
    """Resolve roles and fingerprint from static or managed API keys."""
    static_roles = roles_for_api_key(provided_key, request.app.state.api_keys)
    if static_roles:
        return {
            "roles": static_roles,
            "fingerprint": fingerprint_key(provided_key),
        }

    if not provided_key:
        return {"roles": set(), "fingerprint": ""}

    try:
        manager = request.app.state.api_key_provider()
        if not hasattr(manager, "find_active_api_key"):
            return {
                "roles": set(),
                "fingerprint": fingerprint_key(provided_key),
            }
        result = manager.find_active_api_key(hash_key(provided_key))
        if not result.get("success") or not result.get("data"):
            return {
                "roles": set(),
                "fingerprint": fingerprint_key(provided_key),
            }
        data = result["data"]
        return {
            "roles": normalize_roles(data.get("roles", [])),
            "fingerprint": data.get("key_fingerprint") or fingerprint_key(provided_key),
        }
    except Exception:
        return {
            "roles": set(),
            "fingerprint": fingerprint_key(provided_key),
        }


def required_roles(method: str, path: str) -> Set[str]:
    """Return roles that can access a route."""
    normalized_method = method.upper()

    if path == "/chat" and normalized_method == "POST":
        return {ROLE_CHAT}

    if path == "/braincore/decisions":
        if normalized_method == "GET":
            return {ROLE_BRAINCORE_READ}
        if normalized_method == "POST":
            return {ROLE_BRAINCORE_WRITE}

    if path == "/braincore/search" and normalized_method == "POST":
        return {ROLE_BRAINCORE_READ}

    if path == "/braincore/sources" and normalized_method == "GET":
        return {ROLE_BRAINCORE_READ}

    if path == "/braincore/metrics" and normalized_method == "GET":
        return {ROLE_BRAINCORE_READ}

    if (
        path.startswith("/braincore/domains/")
        and path.endswith("/export")
        and normalized_method == "GET"
    ):
        return {ROLE_BRAINCORE_READ}

    if path.startswith("/braincore/domains/") and normalized_method == "DELETE":
        return {ROLE_BRAINCORE_WRITE}

    if path == "/system/metrics" and normalized_method == "GET":
        return {ROLE_MONITORING}

    if path == "/system/readiness" and normalized_method == "GET":
        return {ROLE_MONITORING}

    if path.startswith("/braincore/sources/") and normalized_method == "DELETE":
        return {ROLE_BRAINCORE_WRITE}

    if path == "/braincore/ingest" and normalized_method == "POST":
        return {ROLE_BRAINCORE_WRITE}

    if path == "/sessions" and normalized_method == "GET":
        return {ROLE_MONITORING}

    if path.startswith("/sessions/") and path.endswith("/context"):
        return {ROLE_MONITORING}

    if path == "/tools/executions" and normalized_method == "GET":
        return {ROLE_MONITORING}

    if path == "/tools/pending" and normalized_method == "GET":
        return {ROLE_ADMIN}

    if path.startswith("/tools/pending/") and normalized_method == "POST":
        return {ROLE_ADMIN}

    if path == "/api/access-log" and normalized_method == "GET":
        return {ROLE_MONITORING}

    if path == "/api/keys" and normalized_method in {"GET", "POST"}:
        return {ROLE_ADMIN}

    if path.startswith("/api/keys/") and path.endswith("/revoke"):
        return {ROLE_ADMIN}

    return {ROLE_ADMIN}


def has_required_role(roles: Set[str], required_roles: Set[str]) -> bool:
    """Check role permissions, including simple role inheritance."""
    if ROLE_ADMIN in roles:
        return True
    if roles.intersection(required_roles):
        return True
    if ROLE_BRAINCORE_READ in required_roles and ROLE_BRAINCORE_WRITE in roles:
        return True
    return False


def fingerprint_key(api_key: str) -> str:
    """Return a stable non-secret API key fingerprint."""
    if not api_key:
        return ""
    return hash_key(api_key)[:16]


def hash_key(api_key: str) -> str:
    """Return a stable API key hash for lookup."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Generate a high-entropy ACU API key."""
    return f"acu_{secrets.token_urlsafe(32)}"


def normalize_api_key_expires_at(expires_at: Optional[str]) -> Optional[str]:
    """Validate and normalize managed API key expiration timestamps."""
    if expires_at is None:
        return None

    raw_value = str(expires_at).strip()
    if not raw_value:
        return None

    normalized_value = raw_value.replace("Z", "+00:00")
    try:
        expires_dt = datetime.fromisoformat(normalized_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=("expires_at debe usar formato ISO 8601 o YYYY-MM-DD HH:MM:SS"),
        ) from exc

    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=timezone.utc)
    else:
        expires_dt = expires_dt.astimezone(timezone.utc)

    if expires_dt <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=422,
            detail="expires_at debe ser una fecha futura",
        )

    return expires_dt.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def valid_roles() -> Set[str]:
    """Return supported API roles."""
    return {
        ROLE_ADMIN,
        ROLE_CHAT,
        ROLE_BRAINCORE_READ,
        ROLE_BRAINCORE_WRITE,
        ROLE_MONITORING,
    }


def client_ip(request: Request) -> str:
    """Return the best available client IP address."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else ""
