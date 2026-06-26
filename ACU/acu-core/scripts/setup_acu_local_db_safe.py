"""Safe local ACU MySQL setup.

Creates or confirms only the local ACU database/user pair required for
ACU-CORE smoke tests. This script must not print credentials or connection
strings and must never use Galpon DATABASE_URL values.
"""

from __future__ import annotations

import os
import sys
from importlib import import_module


TARGET_DB = "acu_db_local"
TARGET_APP_USER = "acu_local_app"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
APP_USER_HOSTS = ("localhost", "127.0.0.1")


def emit(key: str, value: object) -> None:
    print(f"{key}={value}")


def defined(name: str) -> str:
    return "DEFINED" if os.getenv(name) else "MISSING"


def truthy_secret(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def safe_literal(value: str) -> str:
    """Return a SQL string literal for already scope-validated values."""
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


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
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        args = getattr(current, "args", ())
        if args and isinstance(args[0], int):
            return args[0]
        current = getattr(current, "__cause__", None) or getattr(current, "orig", None)
    return None


def classify_mysql_connection_error(exc: Exception) -> str:
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


def classify_mysql_setup_error(exc: Exception) -> str:
    code = mysql_error_code(exc)
    if code in {1044, 1045, 1142, 1227, 1410}:
        return "insufficient_privileges"
    text = f"{exc.__class__.__name__} {exc}".lower()
    if "access denied" in text or "privilege" in text or "grant" in text:
        return "insufficient_privileges"
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
        "ACU_API_KEYS",
        "OLLAMA_HOST",
        "OLLAMA_PORT",
        "OLLAMA_MODEL",
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
    missing = [name for name in required if not truthy_secret(name)]
    if missing:
        return fail("required_acu_local_db_variables_missing")

    mysql_host = (os.getenv("MYSQL_HOST") or "").strip().lower()
    if mysql_host not in LOCAL_HOSTS:
        return fail("mysql_host_not_local")

    mysql_database = (os.getenv("MYSQL_DATABASE") or "").strip()
    if "galpon" in mysql_database.lower() or mysql_database == "galpon_digital_db":
        return fail("mysql_database_rejected")
    if mysql_database != TARGET_DB:
        return fail("mysql_database_not_acu_db_local")

    mysql_user = (os.getenv("MYSQL_USER") or "").strip()
    if mysql_user != TARGET_APP_USER:
        return fail("mysql_user_not_acu_local_app")

    try:
        port = int(os.getenv("MYSQL_PORT", ""))
    except ValueError:
        return fail("mysql_port_invalid")
    if port <= 0 or port > 65535:
        return fail("mysql_port_invalid")

    return None


def connect(mysql_connector, *, user: str, password: str, database: str | None = None):
    kwargs = {
        "host": os.environ["MYSQL_HOST"].strip(),
        "port": int(os.environ["MYSQL_PORT"].strip()),
        "user": user,
        "password": password,
        "autocommit": True,
    }
    if database:
        kwargs["database"] = database
    return mysql_connector.connect(**kwargs)


def main() -> int:
    validation_error = validate_env()
    if validation_error is not None:
        return validation_error

    mysql_connector = load_mysql_connector()
    if mysql_connector is None:
        return fail("mysql_connector_missing", 3)
    emit("mysql_driver", "OK")
    emit("acu_db_scope", "LOCAL_ACU")

    admin_user = os.environ["ACU_LOCAL_DB_ADMIN_USER"].strip()
    admin_password = os.environ["ACU_LOCAL_DB_ADMIN_PASSWORD"]
    app_password = os.environ["MYSQL_PASSWORD"]

    try:
        admin_conn = connect(
            mysql_connector,
            user=admin_user,
            password=admin_password,
        )
    except Exception as exc:
        emit("admin_connection", "FAIL")
        return fail(classify_mysql_connection_error(exc), 4)

    try:
        cursor = admin_conn.cursor()
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS `acu_db_local` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )

        for user_host in APP_USER_HOSTS:
            cursor.execute(
                "CREATE USER IF NOT EXISTS "
                f"{safe_literal(TARGET_APP_USER)}@{safe_literal(user_host)} "
                f"IDENTIFIED BY {safe_literal(app_password)}"
            )
            cursor.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER, REFERENCES "
                "ON `acu_db_local`.* TO "
                f"{safe_literal(TARGET_APP_USER)}@{safe_literal(user_host)}"
            )
        cursor.execute("FLUSH PRIVILEGES")
        cursor.close()
        admin_conn.close()
    except Exception as exc:
        try:
            admin_conn.close()
        except Exception:
            pass
        emit("acu_db_setup", "FAIL")
        return fail(classify_mysql_setup_error(exc), 5)

    emit("acu_database_exists", "OK")
    emit("acu_user_exists", "OK")
    emit("acu_permissions", "OK")

    try:
        app_conn = connect(
            mysql_connector,
            user=TARGET_APP_USER,
            password=app_password,
            database=TARGET_DB,
        )
        app_cursor = app_conn.cursor()
        app_cursor.execute("SELECT DATABASE()")
        selected_db = app_cursor.fetchone()[0]
        app_cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE()"
        )
        total_tables = app_cursor.fetchone()[0]
        app_cursor.close()
        app_conn.close()
    except Exception:
        return fail("acu_app_connection_failed", 6)

    emit("acu_app_connection", "OK")
    emit("database_selected", "OK" if selected_db == TARGET_DB else "FAIL")
    emit("acu_total_tables", total_tables)
    emit("decision", "GO" if selected_db == TARGET_DB else "NO-GO")
    return 0 if selected_db == TARGET_DB else 7


if __name__ == "__main__":
    sys.exit(main())
