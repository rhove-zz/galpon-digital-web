"""Safe diagnostic for ACU local MySQL admin connectivity.

This script only validates sanitized preflight, connects with the ACU local
admin credentials, executes SELECT 1, and inspects current-user grants without
printing credentials or raw grant text. It does not create, alter, or drop
databases/users.
"""

from __future__ import annotations

import os
import socket
import sys
from importlib import import_module


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
TARGET_DB = "acu_db_local"


def emit(key: str, value: object) -> None:
    print(f"{key}={value}")


def defined(name: str) -> str:
    return "DEFINED" if os.getenv(name) else "MISSING"


def fail(reason: str, code: int = 2) -> int:
    emit("diagnostic", "FAIL")
    emit("reason", reason)
    emit("decision", "NO-GO")
    return code


def load_mysql_connector():
    try:
        return import_module("mysql.connector")
    except Exception:
        return None


def mysql_error_code(exc: Exception) -> int | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        args = getattr(current, "args", ())
        if args and isinstance(args[0], int):
            return args[0]
        current = getattr(current, "__cause__", None) or getattr(current, "orig", None)
    return None


def classify_connection_error(exc: Exception) -> str:
    code = mysql_error_code(exc)
    if code == 1045:
        return "admin_user_or_password_invalid"
    if code in {2002, 2003, 2005}:
        return "host_port_unreachable"

    text = f"{exc.__class__.__name__} {exc}".lower()
    if "access denied" in text:
        return "admin_user_or_password_invalid"
    if "connection refused" in text or "can't connect" in text:
        return "host_port_unreachable"
    if "timed out" in text or "timeout" in text:
        return "mysql_not_running"
    return "unknown"


def validate_env() -> int | None:
    watched = [
        "ACU_LOCAL_DB_ADMIN_USER",
        "ACU_LOCAL_DB_ADMIN_PASSWORD",
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "DATABASE_URL",
        "STAGING_DATABASE_URL",
    ]
    for name in watched:
        emit(name, defined(name))

    if os.getenv("DATABASE_URL"):
        return fail("database_url_defined")
    if os.getenv("STAGING_DATABASE_URL"):
        return fail("staging_database_url_defined")

    required = [
        "ACU_LOCAL_DB_ADMIN_USER",
        "ACU_LOCAL_DB_ADMIN_PASSWORD",
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
    ]
    if any(not (os.getenv(name) or "").strip() for name in required):
        return fail("required_acu_admin_variables_missing")

    mysql_host = (os.getenv("MYSQL_HOST") or "").strip().lower()
    if mysql_host not in LOCAL_HOSTS:
        return fail("mysql_host_not_local")

    mysql_database = (os.getenv("MYSQL_DATABASE") or "").strip()
    if mysql_database != TARGET_DB or "galpon" in mysql_database.lower():
        return fail("mysql_database_rejected")

    try:
        port = int(os.getenv("MYSQL_PORT", ""))
    except ValueError:
        return fail("mysql_port_invalid")
    if port <= 0 or port > 65535:
        return fail("mysql_port_invalid")
    return None


def tcp_check() -> str:
    host = (os.getenv("MYSQL_HOST") or "").strip()
    port = int(os.getenv("MYSQL_PORT") or "3306")
    try:
        with socket.create_connection((host, port), timeout=5):
            return "OK"
    except Exception:
        return "FAIL"


def connect(mysql_connector):
    return mysql_connector.connect(
        host=os.environ["MYSQL_HOST"].strip(),
        port=int(os.environ["MYSQL_PORT"].strip()),
        user=os.environ["ACU_LOCAL_DB_ADMIN_USER"].strip(),
        password=os.environ["ACU_LOCAL_DB_ADMIN_PASSWORD"],
        autocommit=True,
    )


def inspect_grants(cursor) -> str:
    try:
        cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
        rows = cursor.fetchall()
    except Exception:
        return "NO_VERIFICADO"

    grants = " ".join(str(row[0]).upper() for row in rows if row)
    if "ALL PRIVILEGES" in grants or "GRANT OPTION" in grants:
        return "OK"
    required_markers = ("CREATE", "CREATE USER", "GRANT")
    if all(marker in grants for marker in required_markers):
        return "OK"
    if "CREATE" in grants and "WITH GRANT OPTION" in grants:
        return "OK"
    return "FAIL"


def main() -> int:
    validation_error = validate_env()
    if validation_error is not None:
        return validation_error

    mysql_connector = load_mysql_connector()
    if mysql_connector is None:
        return fail("mysql_connector_missing", 3)
    emit("mysql_driver", "OK")
    emit("tcp_local", tcp_check())

    try:
        conn = connect(mysql_connector)
    except Exception as exc:
        emit("admin_connection", "FAIL")
        return fail(classify_connection_error(exc), 4)

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        value = cursor.fetchone()[0]
        emit("admin_connection", "OK")
        emit("select_1", "OK" if value == 1 else "FAIL")
        emit("admin_privileges", inspect_grants(cursor))
        cursor.close()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return fail("admin_select_or_privilege_check_failed", 5)

    emit("diagnostic", "OK")
    emit("decision", "GO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
