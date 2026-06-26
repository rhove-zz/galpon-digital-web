"""Safe verifier for ACU local dependencies.

This script performs only sanitized preflight checks and read-only SELECT
queries against the ACU local database when MYSQL_DATABASE is exactly
acu_db_local. It never prints credentials, API keys, connection strings, hosts,
or URLs.
"""

from __future__ import annotations

import os
import socket
import sys
from importlib import import_module


TARGET_DB = "acu_db_local"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def emit(key: str, value: object) -> None:
    print(f"{key}={value}")


def defined(name: str) -> str:
    return "DEFINED" if os.getenv(name) else "MISSING"


def emit_watched_variables() -> None:
    watched = [
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "ACU_API_KEYS",
        "OLLAMA_HOST",
        "OLLAMA_PORT",
        "OLLAMA_MODEL",
        "DATABASE_URL",
        "STAGING_DATABASE_URL",
    ]
    for name in watched:
        emit(name, defined(name))


def load_mysql_connector():
    try:
        return import_module("mysql.connector")
    except Exception:
        return None


def mysql_vars_defined() -> bool:
    return all(
        bool((os.getenv(name) or "").strip())
        for name in (
            "MYSQL_HOST",
            "MYSQL_PORT",
            "MYSQL_DATABASE",
            "MYSQL_USER",
            "MYSQL_PASSWORD",
        )
    )


def mysql_database_scope() -> str:
    database = (os.getenv("MYSQL_DATABASE") or "").strip()
    if database != TARGET_DB:
        return "FAIL"
    if "galpon" in database.lower() or database == "galpon_digital_db":
        return "FAIL"
    return "LOCAL_ACU"


def local_host_ok() -> bool:
    host = (os.getenv("MYSQL_HOST") or "").strip().lower()
    return host in LOCAL_HOSTS


def port_ok() -> bool:
    try:
        port = int((os.getenv("MYSQL_PORT") or "").strip())
    except ValueError:
        return False
    return 0 < port <= 65535


def tcp_check() -> str:
    if not local_host_ok() or not port_ok():
        return "FAIL"
    try:
        with socket.create_connection(
            (
                (os.getenv("MYSQL_HOST") or "").strip(),
                int((os.getenv("MYSQL_PORT") or "3306").strip()),
            ),
            timeout=5,
        ):
            return "OK"
    except Exception:
        return "FAIL"


def ollama_config_status() -> str:
    if not all(
        bool((os.getenv(name) or "").strip())
        for name in ("OLLAMA_HOST", "OLLAMA_PORT", "OLLAMA_MODEL")
    ):
        return "FAIL"
    try:
        port = int((os.getenv("OLLAMA_PORT") or "").strip())
    except ValueError:
        return "FAIL"
    return "OK" if 0 < port <= 65535 else "FAIL"


def redis_status() -> str:
    return "OK" if bool((os.getenv("ACU_REDIS_URL") or "").strip()) else "WARNING"


def connect(mysql_connector):
    return mysql_connector.connect(
        host=os.environ["MYSQL_HOST"].strip(),
        port=int(os.environ["MYSQL_PORT"].strip()),
        user=os.environ["MYSQL_USER"].strip(),
        password=os.environ["MYSQL_PASSWORD"],
        database=TARGET_DB,
        autocommit=True,
    )


def main() -> int:
    emit_watched_variables()

    if os.getenv("DATABASE_URL"):
        emit("ACU_DB_SCOPE", "FAIL")
        emit("MYSQL_CONNECTION", "FAIL")
        emit("ACU_TABLES_COUNT", 0)
        emit("OLLAMA_CONFIG", ollama_config_status())
        emit("REDIS_STATUS", redis_status())
        emit("reason", "database_url_defined")
        emit("decision", "NO-GO")
        return 2
    if os.getenv("STAGING_DATABASE_URL"):
        emit("ACU_DB_SCOPE", "FAIL")
        emit("MYSQL_CONNECTION", "FAIL")
        emit("ACU_TABLES_COUNT", 0)
        emit("OLLAMA_CONFIG", ollama_config_status())
        emit("REDIS_STATUS", redis_status())
        emit("reason", "staging_database_url_defined")
        emit("decision", "NO-GO")
        return 3

    scope = mysql_database_scope()
    emit("ACU_DB_SCOPE", scope)
    emit("OLLAMA_CONFIG", ollama_config_status())
    emit("REDIS_STATUS", redis_status())

    if not mysql_vars_defined():
        emit("MYSQL_CONNECTION", "FAIL")
        emit("ACU_TABLES_COUNT", 0)
        emit("reason", "mysql_variables_missing")
        emit("decision", "NO-GO")
        return 4
    if scope != "LOCAL_ACU":
        emit("MYSQL_CONNECTION", "FAIL")
        emit("ACU_TABLES_COUNT", 0)
        emit("reason", "mysql_database_scope_invalid")
        emit("decision", "NO-GO")
        return 5
    if not local_host_ok() or not port_ok():
        emit("MYSQL_CONNECTION", "FAIL")
        emit("ACU_TABLES_COUNT", 0)
        emit("reason", "mysql_host_or_port_invalid")
        emit("decision", "NO-GO")
        return 6

    emit("MYSQL_TCP", tcp_check())
    mysql_connector = load_mysql_connector()
    if mysql_connector is None:
        emit("MYSQL_CONNECTION", "FAIL")
        emit("ACU_TABLES_COUNT", 0)
        emit("reason", "mysql_connector_missing")
        emit("decision", "NO-GO")
        return 7

    try:
        conn = connect(mysql_connector)
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        selected_db = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) AS total_tables "
            "FROM information_schema.tables WHERE table_schema = DATABASE()"
        )
        total_tables = int(cursor.fetchone()[0] or 0)
        cursor.close()
        conn.close()
    except Exception:
        emit("MYSQL_CONNECTION", "FAIL")
        emit("ACU_TABLES_COUNT", 0)
        emit("reason", "mysql_connection_failed")
        emit("decision", "NO-GO")
        return 8

    connection_ok = selected_db == TARGET_DB
    emit("MYSQL_CONNECTION", "OK" if connection_ok else "FAIL")
    emit("ACU_TABLES_COUNT", total_tables)
    go = connection_ok and total_tables > 0 and ollama_config_status() == "OK"
    emit("decision", "GO" if go else "NO-GO")
    return 0 if go else 9


if __name__ == "__main__":
    sys.exit(main())
