"""
Configuration module for ACU (Agente Cognitivo Universal).
Centralizes all environment and system settings.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

LOCAL_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}
SECURE_ENVIRONMENTS = {"staging", "production", "prod"}


def _get_bool(name: str, default: bool = False) -> bool:
    """Return a boolean environment value."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int = 0) -> int:
    """Return an integer environment value with a safe fallback."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _runtime_environment() -> str:
    """Return the normalized ACU runtime environment."""
    return os.getenv("ACU_ENV", os.getenv("APP_ENV", "development")).strip().lower()


def _default_api_auth_required() -> bool:
    """Force API auth in secure runtimes while preserving explicit local config."""
    if _runtime_environment() in SECURE_ENVIRONMENTS:
        return True
    return _get_bool("ACU_API_AUTH_REQUIRED", False)


def _default_webhooks_enabled() -> bool:
    """Keep local webhook compatibility but fail closed in secure runtimes."""
    default_enabled = _runtime_environment() not in SECURE_ENVIRONMENTS
    return _get_bool("ACU_WEBHOOKS_ENABLED", default_enabled)


@dataclass
class OllamaConfig:
    """Configuración para conexión a Ollama."""

    host: str = os.getenv("OLLAMA_HOST", "http://localhost")
    port: int = int(os.getenv("OLLAMA_PORT", 11434))
    model: str = os.getenv("OLLAMA_MODEL", "mistral")
    timeout: int = int(os.getenv("OLLAMA_TIMEOUT", 60))

    @property
    def base_url(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class MySQLConfig:
    """Configuración para conexión a MySQL."""

    host: str = os.getenv("MYSQL_HOST", "localhost")
    port: int = int(os.getenv("MYSQL_PORT", 3306))
    user: str = os.getenv("MYSQL_USER", "root")
    password: str = os.getenv("MYSQL_PASSWORD", "")
    database: str = os.getenv("MYSQL_DATABASE", "acu_db")

    # Usuario de solo lectura para consultas SQL seguras
    read_only_user: str = os.getenv("MYSQL_READ_ONLY_USER", "acu_reader")
    read_only_password: str = os.getenv("MYSQL_READ_ONLY_PASSWORD", "")


@dataclass
class VectorDBConfig:
    """Configuración para base de datos vectorial."""

    enabled: bool = os.getenv("VECTOR_SEARCH_ENABLED", "False").lower() == "true"
    engine: str = os.getenv("VECTOR_DB_ENGINE", "chromadb")  # chromadb o faiss
    persist_directory: str = os.getenv("VECTOR_DB_PATH", "./data/vectors")
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )


@dataclass
class AgentConfig:
    """Configuración del agente cognitivo."""

    max_iterations: int = int(os.getenv("AGENT_MAX_ITERATIONS", 10))
    temperature: float = float(os.getenv("AGENT_TEMPERATURE", 0.3))
    top_p: float = float(os.getenv("AGENT_TOP_P", 0.9))
    context_window: int = int(os.getenv("AGENT_CONTEXT_WINDOW", 4096))
    planning_threshold: int = 3  # Tareas con más de 3 pasos requieren plan


@dataclass
class SystemConfig:
    """Configuración del sistema general."""

    environment: str = _runtime_environment()
    debug: bool = _get_bool("DEBUG", False)
    log_level: str = os.getenv("LOG_LEVEL", "INFO" if not debug else "DEBUG")
    api_auth_required: bool = _default_api_auth_required()
    require_api_key: bool = _get_bool("ACU_REQUIRE_API_KEY", True)
    allow_insecure_local: bool = _get_bool("ACU_ALLOW_INSECURE_LOCAL", False)
    allow_operational_public_routes: bool = _get_bool(
        "ACU_ALLOW_OPERATIONAL_PUBLIC_ROUTES",
        False,
    )
    safe_mode: bool = _get_bool("ACU_SAFE_MODE", True)
    tools_enabled: bool = _get_bool("ACU_TOOLS_ENABLED", True)
    read_only_tools_enabled: bool = _get_bool("ACU_READ_ONLY_TOOLS_ENABLED", True)
    write_tools_enabled: bool = _get_bool("ACU_WRITE_TOOLS_ENABLED", False)
    external_tools_enabled: bool = _get_bool("ACU_EXTERNAL_TOOLS_ENABLED", False)
    python_sandbox_enabled: bool = _get_bool("ACU_PYTHON_SANDBOX_ENABLED", False)
    filesystem_write_enabled: bool = _get_bool("ACU_FILESYSTEM_WRITE_ENABLED", False)
    api_rest_enabled: bool = _get_bool("ACU_API_REST_ENABLED", False)
    web_tools_enabled: bool = _get_bool("ACU_WEB_TOOLS_ENABLED", False)
    audit_full_payloads: bool = _get_bool("ACU_AUDIT_FULL_PAYLOADS", False)
    audit_redact_secrets: bool = _get_bool("ACU_AUDIT_REDACT_SECRETS", True)
    webhooks_enabled: bool = _default_webhooks_enabled()
    webhook_secret_required: bool = _get_bool("ACU_WEBHOOK_SECRET_REQUIRED", True)
    allowed_tools: str = os.getenv("ACU_ALLOWED_TOOLS", "").strip()
    blocked_tools: str = os.getenv("ACU_BLOCKED_TOOLS", "").strip()
    api_key: str = os.getenv("ACU_API_KEY", "").strip()
    api_keys: str = os.getenv("ACU_API_KEYS", "").strip()
    api_cors_origins: str = os.getenv("ACU_API_CORS_ORIGINS", "").strip()
    api_cors_methods: str = os.getenv(
        "ACU_API_CORS_METHODS",
        "GET,POST,DELETE,OPTIONS",
    ).strip()
    api_cors_headers: str = os.getenv(
        "ACU_API_CORS_HEADERS",
        "Authorization,Content-Type,X-ACU-API-Key",
    ).strip()
    api_cors_allow_credentials: bool = _get_bool(
        "ACU_API_CORS_ALLOW_CREDENTIALS",
        False,
    )
    api_max_request_body_bytes: int = _get_int("ACU_API_MAX_REQUEST_BODY_BYTES", 0)
    api_rate_limit_requests: int = _get_int("ACU_API_RATE_LIMIT_REQUESTS", 0)
    api_rate_limit_window_seconds: int = _get_int(
        "ACU_API_RATE_LIMIT_WINDOW_SECONDS",
        60,
    )
    log_retention_days: int = _get_int("ACU_LOG_RETENTION_DAYS", 30)
    audit_retention_days: int = _get_int(
        "ACU_AUDIT_RETENTION_DAYS",
        log_retention_days,
    )
    conversation_retention_days: int = _get_int(
        "ACU_CONVERSATION_RETENTION_DAYS",
        log_retention_days,
    )
    scheduler_mode: str = os.getenv("ACU_SCHEDULER_MODE", "disabled").strip().lower()
    telemetry_enabled: bool = _get_bool("ACU_TELEMETRY_ENABLED", False)
    otlp_endpoint: str = os.getenv("ACU_OTLP_ENDPOINT", "http://jaeger:4318/v1/traces")
    redis_url: str = os.getenv("ACU_REDIS_URL", "redis://localhost:6379/0")
    webhook_telegram_secret: str = os.getenv("ACU_TELEGRAM_WEBHOOK_SECRET", "").strip()
    webhook_slack_signing_secret: str = os.getenv(
        "ACU_SLACK_SIGNING_SECRET", ""
    ).strip()
    webhook_slack_max_skew_seconds: int = _get_int("ACU_SLACK_MAX_SKEW_SECONDS", 300)
    webhook_allowed_telegram_chats: str = os.getenv(
        "ACU_WEBHOOK_ALLOWED_TELEGRAM_CHATS", ""
    ).strip()
    webhook_allowed_slack_users: str = os.getenv(
        "ACU_WEBHOOK_ALLOWED_SLACK_USERS", ""
    ).strip()
    braincore_sync_paths: str = os.getenv(
        "ACU_BRAINCORE_SYNC_PATHS", ""
    )  # Rutas separadas por coma
    project_name: str = "ACU"
    version: str = "1.0.0"

    @property
    def is_secure_runtime(self) -> bool:
        """Return True for staging/production-like environments."""
        return self.environment in SECURE_ENVIRONMENTS

    @property
    def is_local_runtime(self) -> bool:
        """Return True for development/test-like environments."""
        return self.environment in LOCAL_ENVIRONMENTS


# Instancias globales
ollama_config = OllamaConfig()
mysql_config = MySQLConfig()
vectordb_config = VectorDBConfig()
agent_config = AgentConfig()
system_config = SystemConfig()
