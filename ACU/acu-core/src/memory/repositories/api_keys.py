"""Managed API key persistence repository."""

import json
from typing import Any, Dict, List, Optional, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the API key repository."""

    use_read_only: bool
    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class ApiKeyRepository:
    """Persist and retrieve managed API keys through a MySQL connector."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def create_api_key(
        self,
        name: str,
        key_hash: str,
        key_fingerprint: str,
        roles: List[str],
        expires_at: Optional[str] = None,
        created_by: str = "",
    ) -> Dict[str, Any]:
        """Persist a managed API key hash and metadata."""
        if self.connector.use_read_only:
            return {
                "success": False,
                "error": "El conector actual es de solo lectura y no puede crear claves API.",
            }

        if not name or not key_hash or not roles:
            return {"success": False, "error": "name, key_hash y roles son requeridos."}

        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion de escritura con MySQL.",
            }

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(
                """
                INSERT INTO api_keys (
                    name,
                    key_hash,
                    key_fingerprint,
                    roles,
                    status,
                    expires_at,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    key_hash,
                    key_fingerprint,
                    json.dumps(roles, ensure_ascii=False),
                    "active",
                    expires_at,
                    created_by,
                ),
            )
            key_id = cursor.lastrowid
            self.connector.connection.commit()
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    key_fingerprint,
                    roles,
                    status,
                    created_by,
                    created_at,
                    revoked_at,
                    expires_at,
                    last_used_at
                FROM api_keys
                WHERE id = %s
                """,
                (key_id,),
            )
            row = _normalize_api_key_row(cursor.fetchone())
            cursor.close()
            return {"success": True, "data": row}
        except Error as exc:
            log.error(f"Error creando clave API: {exc}")
            return {"success": False, "error": str(exc)}

    def find_active_api_key(self, key_hash: str) -> Dict[str, Any]:
        """Find one active managed API key by hash."""
        if not key_hash:
            return {"success": True, "data": None}

        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    key_fingerprint,
                    roles,
                    status,
                    created_by,
                    created_at,
                    revoked_at,
                    expires_at,
                    last_used_at
                FROM api_keys
                WHERE key_hash = %s
                  AND status = 'active'
                  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                LIMIT 1
                """,
                (key_hash,),
            )
            row = _normalize_api_key_row(cursor.fetchone())
            if row:
                cursor.execute(
                    "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (row["id"],),
                )
                self.connector.connection.commit()
            cursor.close()
            return {"success": True, "data": row}
        except Error as exc:
            log.warning(f"No se pudo buscar clave API gestionada: {exc}")
            return {"success": False, "error": str(exc)}

    def list_api_keys(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List managed API key metadata without secrets."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        where_clauses = []
        values: List[Any] = []
        if status:
            where_clauses.append("status = %s")
            values.append(status)

        query = """
            SELECT
                id,
                name,
                key_fingerprint,
                roles,
                status,
                created_by,
                created_at,
                revoked_at,
                expires_at,
                last_used_at
            FROM api_keys
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY created_at DESC LIMIT %s"
        values.append(min(max(int(limit), 1), 200))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            rows = [_normalize_api_key_row(row) for row in cursor.fetchall()]
            cursor.close()
            return {"success": True, "data": rows}
        except Error as exc:
            log.error(f"Error listando claves API: {exc}")
            return {"success": False, "error": str(exc)}

    def revoke_api_key(self, key_id: int) -> Dict[str, Any]:
        """Revoke one managed API key by id."""
        if self.connector.use_read_only:
            return {
                "success": False,
                "error": "El conector actual es de solo lectura y no puede revocar claves API.",
            }

        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion de escritura con MySQL.",
            }

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(
                """
                UPDATE api_keys
                SET status = 'revoked',
                    revoked_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (int(key_id),),
            )
            self.connector.connection.commit()
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    key_fingerprint,
                    roles,
                    status,
                    created_by,
                    created_at,
                    revoked_at,
                    expires_at,
                    last_used_at
                FROM api_keys
                WHERE id = %s
                """,
                (int(key_id),),
            )
            row = _normalize_api_key_row(cursor.fetchone())
            cursor.close()
            if not row:
                return {"success": False, "error": "Clave API no encontrada."}
            return {"success": True, "data": row}
        except Error as exc:
            log.error(f"Error revocando clave API: {exc}")
            return {"success": False, "error": str(exc)}


def _normalize_api_key_row(
    row: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Normalize managed API key JSON/date fields for API responses."""
    if not row:
        return None

    normalized = dict(row)
    normalized["roles"] = _loads_json_list(normalized.get("roles"))
    for field in ("created_at", "revoked_at", "expires_at", "last_used_at"):
        value = normalized.get(field)
        normalized[field] = str(value) if value is not None else None
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
