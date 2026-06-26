"""Safe ACU chat runtime diagnostic.

Checks local Ollama and ACU MySQL read-only runtime prerequisites without
printing secrets, model names, URLs, hosts, or connection strings.
"""

from __future__ import annotations

import os
import socket
import sys
from importlib import import_module
from urllib.parse import urlparse

import requests


TARGET_DB = "acu_db_local"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def emit(key: str, value: object) -> None:
    print(f"{key}={value}")


def defined(name: str) -> str:
    return "DEFINED" if os.getenv(name) else "MISSING"


def fail(reason: str, code: int = 2) -> int:
    emit("reason", reason)
    emit("decision", "NO-GO")
    return code


def load_mysql_connector():
    try:
        return import_module("mysql.connector")
    except Exception:
        return None


def watched_variables() -> None:
    for name in (
        "OLLAMA_HOST",
        "OLLAMA_PORT",
        "OLLAMA_MODEL",
        "OLLAMA_TIMEOUT",
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_READ_ONLY_USER",
        "MYSQL_READ_ONLY_PASSWORD",
        "DATABASE_URL",
        "STAGING_DATABASE_URL",
    ):
        emit(name, defined(name))


def db_scope() -> str:
    database = (os.getenv("MYSQL_DATABASE") or "").strip()
    if database == TARGET_DB and "galpon" not in database.lower():
        return "LOCAL_ACU"
    return "FAIL"


def mysql_host_local() -> bool:
    return (os.getenv("MYSQL_HOST") or "").strip().lower() in LOCAL_HOSTS


def mysql_port_valid() -> bool:
    try:
        port = int((os.getenv("MYSQL_PORT") or "").strip())
    except ValueError:
        return False
    return 0 < port <= 65535


def mysql_tcp_status() -> str:
    if not mysql_host_local() or not mysql_port_valid():
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


def mysql_read_only_status(mysql_connector) -> str:
    if not (os.getenv("MYSQL_READ_ONLY_USER") or "").strip():
        return "FAIL"
    if not (os.getenv("MYSQL_READ_ONLY_PASSWORD") or "").strip():
        return "FAIL"
    try:
        conn = mysql_connector.connect(
            host=os.environ["MYSQL_HOST"].strip(),
            port=int(os.environ["MYSQL_PORT"].strip()),
            user=os.environ["MYSQL_READ_ONLY_USER"].strip(),
            password=os.environ["MYSQL_READ_ONLY_PASSWORD"],
            database=TARGET_DB,
            autocommit=True,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        selected_db = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"
        )
        total_tables = int(cursor.fetchone()[0] or 0)
        cursor.close()
        conn.close()
    except Exception:
        return "FAIL"
    emit("mysql_read_only_database_scope", "LOCAL_ACU" if selected_db == TARGET_DB else "FAIL")
    emit("mysql_read_only_tables_count", total_tables)
    return "OK" if selected_db == TARGET_DB and total_tables > 0 else "FAIL"


def ollama_base_url_status() -> tuple[str, str]:
    host = (os.getenv("OLLAMA_HOST") or "").strip()
    port = (os.getenv("OLLAMA_PORT") or "").strip()
    if not host or not port:
        return "FAIL", ""
    try:
        parsed = urlparse(host)
        if parsed.scheme not in {"http", "https"}:
            return "FAIL", ""
        if (parsed.hostname or "").strip().lower() not in LOCAL_HOSTS:
            return "FAIL", ""
        parsed_port = int(port)
    except Exception:
        return "FAIL", ""
    if parsed_port <= 0 or parsed_port > 65535:
        return "FAIL", ""
    return "OK", f"{host}:{parsed_port}"


def ollama_status() -> tuple[str, str, int]:
    base_status, base_url = ollama_base_url_status()
    if base_status != "OK":
        return "FAIL", "FAIL", 0
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
    except Exception:
        return "FAIL", "FAIL", 0
    if response.status_code != 200:
        return "FAIL", "FAIL", 0
    try:
        models = response.json().get("models", [])
    except Exception:
        return "OK", "FAIL", 0
    configured = (os.getenv("OLLAMA_MODEL") or "").strip()
    model_names = {str(model.get("name") or "") for model in models}
    model_ok = configured in model_names if configured else False
    return "OK", "OK" if model_ok else "FAIL", len(model_names)


def main() -> int:
    watched_variables()

    if os.getenv("DATABASE_URL"):
        emit("acu_db_scope", "FAIL")
        return fail("database_url_defined")
    if os.getenv("STAGING_DATABASE_URL"):
        emit("acu_db_scope", "FAIL")
        return fail("staging_database_url_defined")

    emit("acu_db_scope", db_scope())
    if db_scope() != "LOCAL_ACU":
        emit("mysql_read_only_connection", "FAIL")
        emit("ollama_connection", "FAIL")
        emit("ollama_model_available", "FAIL")
        return fail("mysql_database_scope_invalid")

    emit("mysql_tcp", mysql_tcp_status())
    mysql_connector = load_mysql_connector()
    if mysql_connector is None:
        emit("mysql_read_only_connection", "FAIL")
        emit("ollama_connection", "FAIL")
        emit("ollama_model_available", "FAIL")
        return fail("mysql_connector_missing")

    read_only = mysql_read_only_status(mysql_connector)
    emit("mysql_read_only_connection", read_only)
    ollama_conn, model_status, model_count = ollama_status()
    emit("ollama_connection", ollama_conn)
    emit("ollama_model_available", model_status)
    emit("ollama_models_count", model_count)

    go = read_only == "OK" and ollama_conn == "OK" and model_status == "OK"
    emit("decision", "GO" if go else "NO-GO")
    return 0 if go else 10


if __name__ == "__main__":
    sys.exit(main())
