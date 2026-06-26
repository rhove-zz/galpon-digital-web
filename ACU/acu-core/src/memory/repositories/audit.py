"""Audit persistence repository."""

import json
from typing import Any, Dict, List, Optional, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the audit repository."""

    use_read_only: bool
    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class AuditRepository:
    """Persist and query tool/API audit records."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def log_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
        execution_time_ms: float,
        success: bool,
    ) -> bool:
        """Persist tool execution metadata for auditing."""
        if self.connector.use_read_only:
            return False

        if not self.connector._ensure_connection():
            return False

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                INSERT INTO tool_execution_log (
                    nombre_herramienta,
                    parametros,
                    resultado,
                    tiempo_ms,
                    exito
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    tool_name,
                    json.dumps(parameters, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False, default=str),
                    int(execution_time_ms),
                    success,
                ),
            )
            self.connector.connection.commit()
            cursor.close()
            return True
        except Error as exc:
            log.warning(f"No se pudo registrar auditoria de herramienta: {exc}")
            return False

    def log_api_access(
        self,
        method: str,
        path: str,
        status_code: int,
        key_fingerprint: str = "",
        roles: Optional[List[str]] = None,
        client_ip: str = "",
        user_agent: str = "",
        authorized: bool = False,
        duration_ms: float = 0.0,
    ) -> bool:
        """Persist API access metadata for auditing."""
        if self.connector.use_read_only:
            return False

        if not self.connector._ensure_connection():
            return False

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                INSERT INTO api_access_log (
                    method,
                    path,
                    status_code,
                    key_fingerprint,
                    roles,
                    client_ip,
                    user_agent,
                    authorized,
                    duration_ms
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    method,
                    path,
                    int(status_code),
                    key_fingerprint,
                    json.dumps(roles or [], ensure_ascii=False),
                    client_ip,
                    user_agent[:512] if user_agent else "",
                    authorized,
                    int(duration_ms),
                ),
            )
            self.connector.connection.commit()
            cursor.close()
            return True
        except Error as exc:
            log.warning(f"No se pudo registrar auditoria de acceso API: {exc}")
            return False

    def prune_tool_execution_log(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete tool execution logs older than the specified days."""
        if self.connector.use_read_only:
            return {"success": False, "error": "Read-only connector"}

        if not self.connector._ensure_connection():
            return {"success": False, "error": "No database connection"}

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                DELETE FROM tool_execution_log
                WHERE fecha_ejecucion < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s DAY)
                """,
                (older_than_days,),
            )
            rows_deleted = cursor.rowcount
            self.connector.connection.commit()
            cursor.close()
            log.info(
                f"Purgados {rows_deleted} registros antiguos de tool_execution_log"
            )
            return {"success": True, "rows_deleted": rows_deleted}
        except Error as exc:
            log.error(f"Error purgando tool_execution_log: {exc}")
            return {"success": False, "error": str(exc)}

    def prune_api_access_log(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete API access logs older than the specified days."""
        if self.connector.use_read_only:
            return {"success": False, "error": "Read-only connector"}

        if not self.connector._ensure_connection():
            return {"success": False, "error": "No database connection"}

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                DELETE FROM api_access_log
                WHERE fecha_acceso < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s DAY)
                """,
                (older_than_days,),
            )
            rows_deleted = cursor.rowcount
            self.connector.connection.commit()
            cursor.close()
            log.info(f"Purgados {rows_deleted} registros antiguos de api_access_log")
            return {"success": True, "rows_deleted": rows_deleted}
        except Error as exc:
            log.error(f"Error purgando api_access_log: {exc}")
            return {"success": False, "error": str(exc)}

    def list_tool_executions(
        self,
        tool_name: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List persisted tool execution audit rows."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        where_clauses = []
        values: List[Any] = []
        if tool_name:
            where_clauses.append("nombre_herramienta = %s")
            values.append(tool_name)
        if success is not None:
            where_clauses.append("exito = %s")
            values.append(success)

        query = """
            SELECT
                id,
                nombre_herramienta AS tool_name,
                parametros AS parameters,
                resultado AS result,
                tiempo_ms AS execution_time_ms,
                exito AS success,
                fecha_ejecucion AS executed_at
            FROM tool_execution_log
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY fecha_ejecucion DESC LIMIT %s"
        values.append(min(max(int(limit), 1), 200))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            rows = [_normalize_tool_execution_row(row) for row in cursor.fetchall()]
            cursor.close()
            return {"success": True, "data": rows}
        except Error as exc:
            log.error(f"Error listando auditoria de herramientas: {exc}")
            return {"success": False, "error": str(exc)}

    def list_api_access_log(
        self,
        path: Optional[str] = None,
        status_code: Optional[int] = None,
        authorized: Optional[bool] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List persisted API access audit rows."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        where_clauses = []
        values: List[Any] = []
        if path:
            where_clauses.append("path = %s")
            values.append(path)
        if status_code is not None:
            where_clauses.append("status_code = %s")
            values.append(int(status_code))
        if authorized is not None:
            where_clauses.append("authorized = %s")
            values.append(authorized)

        query = """
            SELECT
                id,
                method,
                path,
                status_code,
                key_fingerprint,
                roles,
                client_ip,
                user_agent,
                authorized,
                duration_ms,
                fecha_acceso AS accessed_at
            FROM api_access_log
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY fecha_acceso DESC LIMIT %s"
        values.append(min(max(int(limit), 1), 200))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            rows = [_normalize_api_access_row(row) for row in cursor.fetchall()]
            cursor.close()
            return {"success": True, "data": rows}
        except Error as exc:
            log.error(f"Error listando auditoria de acceso API: {exc}")
            return {"success": False, "error": str(exc)}


def _normalize_tool_execution_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize tool audit JSON/date fields for API responses."""
    normalized = dict(row)
    normalized["parameters"] = _loads_json_dict(normalized.get("parameters"))
    normalized["result"] = _loads_json_any(normalized.get("result"))
    normalized["success"] = bool(normalized.get("success"))
    normalized["executed_at"] = str(normalized.get("executed_at"))
    return normalized


def _normalize_api_access_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize API access audit JSON/date fields for API responses."""
    normalized = dict(row)
    normalized["roles"] = _loads_json_list(normalized.get("roles"))
    normalized["authorized"] = bool(normalized.get("authorized"))
    normalized["accessed_at"] = str(normalized.get("accessed_at"))
    return normalized


def _loads_json_list(value: Any) -> List[str]:
    """Decode a JSON list defensively."""
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return []
    return decoded if isinstance(decoded, list) else []


def _loads_json_dict(value: Any) -> Dict[str, Any]:
    """Decode a JSON object defensively."""
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _loads_json_any(value: Any) -> Any:
    """Decode JSON defensively, preserving non-JSON values."""
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value
