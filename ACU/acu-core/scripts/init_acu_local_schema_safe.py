"""Safe local ACU schema initializer.

Initializes only the local ACU database schema in acu_db_local. This script
never uses DATABASE_URL/STAGING_DATABASE_URL, never prints credentials, and
does not execute destructive SQL.
"""

from __future__ import annotations

import os
import socket
import sys
from importlib import import_module


TARGET_DB = "acu_db_local"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

DDL_STATEMENTS = [
    (
        "memoria_evolutiva",
        """
    CREATE TABLE IF NOT EXISTS memoria_evolutiva (
        id INT AUTO_INCREMENT PRIMARY KEY,
        categoria VARCHAR(100) NOT NULL,
        leccion_aprendida TEXT NOT NULL,
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        relevancia INT DEFAULT 1,
        veces_utilizada INT DEFAULT 0,
        INDEX idx_categoria (categoria),
        INDEX idx_fecha (fecha_registro)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "tool_execution_log",
        """
    CREATE TABLE IF NOT EXISTS tool_execution_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre_herramienta VARCHAR(100) NOT NULL,
        action_type VARCHAR(50),
        target_resource VARCHAR(512),
        payload_size_bytes INT DEFAULT 0,
        parametros JSON,
        resultado JSON,
        tiempo_ms INT,
        exito BOOLEAN,
        fecha_ejecucion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_herramienta (nombre_herramienta),
        INDEX idx_action (action_type),
        INDEX idx_fecha (fecha_ejecucion)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "api_access_log",
        """
    CREATE TABLE IF NOT EXISTS api_access_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        method VARCHAR(10) NOT NULL,
        path VARCHAR(512) NOT NULL,
        status_code INT NOT NULL,
        key_fingerprint VARCHAR(64),
        roles JSON,
        client_ip VARCHAR(64),
        user_agent VARCHAR(512),
        authorized BOOLEAN,
        duration_ms INT,
        fecha_acceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_api_access_path (path(255)),
        INDEX idx_api_access_status (status_code),
        INDEX idx_api_access_fecha (fecha_acceso)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "api_keys",
        """
    CREATE TABLE IF NOT EXISTS api_keys (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        key_hash CHAR(64) NOT NULL,
        key_fingerprint VARCHAR(64) NOT NULL,
        roles JSON NOT NULL,
        status VARCHAR(20) DEFAULT 'active',
        created_by VARCHAR(120),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        revoked_at TIMESTAMP NULL,
        expires_at TIMESTAMP NULL,
        last_used_at TIMESTAMP NULL,
        UNIQUE KEY uq_api_key_hash (key_hash),
        INDEX idx_api_key_fingerprint (key_fingerprint),
        INDEX idx_api_key_status (status),
        INDEX idx_api_key_expires (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "agent_sessions",
        """
    CREATE TABLE IF NOT EXISTS agent_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id VARCHAR(100) UNIQUE NOT NULL,
        domain VARCHAR(50),
        inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fin TIMESTAMP NULL,
        total_iteraciones INT,
        estado VARCHAR(20),
        INDEX idx_session (session_id),
        INDEX idx_fecha_inicio (inicio)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "conversation_context",
        """
    CREATE TABLE IF NOT EXISTS conversation_context (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id VARCHAR(100),
        usuario_query TEXT,
        respuesta_agente TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        pasos_utilizados INT,
        INDEX idx_session (session_id),
        INDEX idx_timestamp (timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "brain_decisions",
        """
    CREATE TABLE IF NOT EXISTS brain_decisions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        titulo VARCHAR(255) NOT NULL,
        contexto TEXT NOT NULL,
        decision_text TEXT NOT NULL,
        alternativas JSON,
        impacto TEXT,
        domain VARCHAR(100) DEFAULT 'generic',
        estado VARCHAR(30) DEFAULT 'accepted',
        tags JSON,
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_brain_domain (domain),
        INDEX idx_brain_estado (estado),
        INDEX idx_brain_fecha (fecha_registro)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "brain_sources",
        """
    CREATE TABLE IF NOT EXISTS brain_sources (
        id INT AUTO_INCREMENT PRIMARY KEY,
        source_path VARCHAR(1024) NOT NULL,
        source_type VARCHAR(50) NOT NULL,
        content_hash CHAR(64) NOT NULL,
        metadata JSON,
        estado VARCHAR(30) DEFAULT 'indexed',
        fecha_indexacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_brain_source_path (source_path(255)),
        INDEX idx_brain_source_type (source_type),
        INDEX idx_brain_source_hash (content_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
    (
        "brain_chunks",
        """
    CREATE TABLE IF NOT EXISTS brain_chunks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        source_id INT NOT NULL,
        chunk_index INT NOT NULL,
        chunk_hash CHAR(64) NOT NULL,
        titulo VARCHAR(255),
        contenido MEDIUMTEXT NOT NULL,
        metadata JSON,
        fecha_indexacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_brain_source_chunk (source_id, chunk_index),
        INDEX idx_brain_chunk_hash (chunk_hash),
        INDEX idx_brain_chunk_source (source_id),
        FULLTEXT INDEX ft_brain_chunk_content (titulo, contenido)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    ),
]

REQUIRED_TABLES = (
    "memoria_evolutiva",
    "tool_execution_log",
    "api_access_log",
    "api_keys",
    "agent_sessions",
    "conversation_context",
    "brain_decisions",
    "brain_sources",
    "brain_chunks",
)


def emit(key: str, value: object) -> None:
    print(f"{key}={value}")


def defined(name: str) -> str:
    return "DEFINED" if os.getenv(name) else "MISSING"


def fail(reason: str, code: int = 2) -> int:
    emit("preflight", "FAIL")
    emit("reason", reason)
    emit("decision", "NO-GO")
    return code


def load_mysql_connector():
    try:
        return import_module("mysql.connector")
    except Exception:
        return None


def mysql_error_code(exc: Exception) -> int | None:
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], int):
        return args[0]
    errno = getattr(exc, "errno", None)
    return int(errno) if isinstance(errno, int) else None


def classify_schema_error(exc: Exception) -> str:
    code = mysql_error_code(exc)
    if code in {1044, 1045, 1142, 1227}:
        return "insufficient_privileges"
    if code in {1064, 1067, 1071, 1170}:
        return "ddl_incompatible"
    if code in {1215, 1824, 3780}:
        return "foreign_key_or_reference_error"
    if code in {2002, 2003, 2005}:
        return "mysql_connection_lost"
    return "unknown"


def watched_variables() -> None:
    for name in (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "DATABASE_URL",
        "STAGING_DATABASE_URL",
    ):
        emit(name, defined(name))


def validate_env() -> int | None:
    watched_variables()

    if os.getenv("DATABASE_URL"):
        return fail("database_url_defined")
    if os.getenv("STAGING_DATABASE_URL"):
        return fail("staging_database_url_defined")

    required = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")
    if any(not (os.getenv(name) or "").strip() for name in required):
        return fail("mysql_variables_missing")

    host = (os.getenv("MYSQL_HOST") or "").strip().lower()
    if host not in LOCAL_HOSTS:
        return fail("mysql_host_not_local")

    database = (os.getenv("MYSQL_DATABASE") or "").strip()
    if database != TARGET_DB:
        return fail("mysql_database_not_acu_db_local")
    if "galpon" in database.lower() or database == "galpon_digital_db":
        return fail("mysql_database_rejected")

    try:
        port = int((os.getenv("MYSQL_PORT") or "").strip())
    except ValueError:
        return fail("mysql_port_invalid")
    if port <= 0 or port > 65535:
        return fail("mysql_port_invalid")

    try:
        with socket.create_connection((host, port), timeout=5):
            emit("mysql_tcp", "OK")
    except Exception:
        emit("mysql_tcp", "FAIL")
        return fail("mysql_tcp_failed")

    emit("acu_db_scope", "LOCAL_ACU")
    emit("preflight", "OK")
    return None


def connect(mysql_connector):
    return mysql_connector.connect(
        host=os.environ["MYSQL_HOST"].strip(),
        port=int(os.environ["MYSQL_PORT"].strip()),
        user=os.environ["MYSQL_USER"].strip(),
        password=os.environ["MYSQL_PASSWORD"],
        database=TARGET_DB,
        autocommit=True,
    )


def count_tables(cursor) -> int:
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"
    )
    return int(cursor.fetchone()[0] or 0)


def missing_required_tables(cursor) -> list[str]:
    cursor.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()"
    )
    existing = {str(row[0]) for row in cursor.fetchall()}
    return [table for table in REQUIRED_TABLES if table not in existing]


def main() -> int:
    validation_error = validate_env()
    if validation_error is not None:
        return validation_error

    mysql_connector = load_mysql_connector()
    if mysql_connector is None:
        return fail("mysql_connector_missing", 3)

    try:
        conn = connect(mysql_connector)
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        selected_db = str(cursor.fetchone()[0])
        if selected_db != TARGET_DB:
            cursor.close()
            conn.close()
            return fail("selected_database_not_acu_db_local", 4)

        before_count = count_tables(cursor)
        for table_name, statement in DDL_STATEMENTS:
            try:
                cursor.execute(statement)
            except Exception as exc:
                emit("schema_failed_table", table_name)
                code = mysql_error_code(exc)
                emit("schema_mysql_error_code", code if code is not None else "UNKNOWN")
                cursor.close()
                conn.close()
                return fail(classify_schema_error(exc), 5)
        after_count = count_tables(cursor)
        missing = missing_required_tables(cursor)
        cursor.close()
        conn.close()
    except Exception as exc:
        code = mysql_error_code(exc)
        emit("schema_mysql_error_code", code if code is not None else "UNKNOWN")
        return fail("schema_initialization_failed", 5)

    emit("selected_database", "OK")
    emit("schema_tables_before", before_count)
    emit("schema_tables_after", after_count)
    emit("required_tables_count", len(REQUIRED_TABLES))
    emit("required_tables_missing", len(missing))
    emit("schema_initialized", "OK" if not missing else "FAIL")
    emit("destructive_sql", "NO")
    emit("seed_data_inserted", "NO")
    emit("decision", "GO" if not missing and after_count >= len(REQUIRED_TABLES) else "NO-GO")
    return 0 if not missing and after_count >= len(REQUIRED_TABLES) else 6


if __name__ == "__main__":
    sys.exit(main())
