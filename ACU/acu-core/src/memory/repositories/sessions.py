"""Agent session and conversation context persistence repository."""

from typing import Any, Dict, List, Optional, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the sessions repository."""

    use_read_only: bool
    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class SessionsRepository:
    """Persist and query agent sessions and conversation turns."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def start_agent_session(self, session_id: str, domain: str) -> bool:
        """Persist the start of an agent session."""
        if self.connector.use_read_only:
            return False

        if not self.connector._ensure_connection():
            return False

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                INSERT INTO agent_sessions (
                    session_id,
                    domain,
                    total_iteraciones,
                    estado
                )
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE estado = VALUES(estado)
                """,
                (session_id, domain, 0, "active"),
            )
            self.connector.connection.commit()
            cursor.close()
            return True
        except Error as exc:
            log.warning(f"No se pudo iniciar sesion de agente: {exc}")
            return False

    def end_agent_session(
        self,
        session_id: str,
        total_iterations: int,
        status: str = "completed",
    ) -> bool:
        """Persist the end state of an agent session."""
        if self.connector.use_read_only:
            return False

        if not self.connector._ensure_connection():
            return False

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                UPDATE agent_sessions
                SET fin = CURRENT_TIMESTAMP,
                    total_iteraciones = %s,
                    estado = %s
                WHERE session_id = %s
                """,
                (total_iterations, status, session_id),
            )
            self.connector.connection.commit()
            cursor.close()
            return True
        except Error as exc:
            log.warning(f"No se pudo cerrar sesion de agente: {exc}")
            return False

    def log_conversation_context(
        self,
        session_id: str,
        user_query: str,
        agent_response: str,
        steps_used: int,
    ) -> bool:
        """Persist one user/agent exchange for the current session."""
        if self.connector.use_read_only:
            return False

        if not self.connector._ensure_connection():
            return False

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                INSERT INTO conversation_context (
                    session_id,
                    usuario_query,
                    respuesta_agente,
                    pasos_utilizados
                )
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, user_query, agent_response, steps_used),
            )
            self.connector.connection.commit()
            cursor.close()
            return True
        except Error as exc:
            log.warning(f"No se pudo registrar contexto conversacional: {exc}")
            return False

    def prune_conversation_context(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete persisted conversation turns older than the specified days."""
        if self.connector.use_read_only:
            return {"success": False, "error": "Read-only connector"}

        if not self.connector._ensure_connection():
            return {"success": False, "error": "No database connection"}

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                DELETE FROM conversation_context
                WHERE timestamp < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s DAY)
                """,
                (older_than_days,),
            )
            rows_deleted = cursor.rowcount
            self.connector.connection.commit()
            cursor.close()
            log.info(
                f"Purgados {rows_deleted} registros antiguos de conversation_context"
            )
            return {"success": True, "rows_deleted": rows_deleted}
        except Error as exc:
            log.error(f"Error purgando conversation_context: {exc}")
            return {"success": False, "error": str(exc)}

    def prune_agent_sessions(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete completed agent sessions older than the specified days."""
        if self.connector.use_read_only:
            return {"success": False, "error": "Read-only connector"}

        if not self.connector._ensure_connection():
            return {"success": False, "error": "No database connection"}

        try:
            cursor = self.connector.connection.cursor()
            cursor.execute(
                """
                DELETE FROM conversation_context
                WHERE session_id IN (
                    SELECT session_id
                    FROM agent_sessions
                    WHERE fin IS NOT NULL
                      AND fin < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s DAY)
                )
                """,
                (older_than_days,),
            )
            context_rows_deleted = cursor.rowcount
            cursor.execute(
                """
                DELETE FROM agent_sessions
                WHERE fin IS NOT NULL
                  AND fin < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s DAY)
                """,
                (older_than_days,),
            )
            session_rows_deleted = cursor.rowcount
            self.connector.connection.commit()
            cursor.close()
            log.info(
                "Purgadas sesiones antiguas: "
                f"{session_rows_deleted} sesiones y "
                f"{context_rows_deleted} registros de contexto asociados"
            )
            return {
                "success": True,
                "rows_deleted": session_rows_deleted,
                "context_rows_deleted": context_rows_deleted,
            }
        except Error as exc:
            log.error(f"Error purgando agent_sessions: {exc}")
            return {"success": False, "error": str(exc)}

    def list_agent_sessions(
        self,
        domain: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List persisted agent sessions."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        where_clauses = []
        values: List[Any] = []
        if domain:
            where_clauses.append("domain = %s")
            values.append(domain)
        if status:
            where_clauses.append("estado = %s")
            values.append(status)

        query = """
            SELECT
                session_id,
                domain,
                inicio AS started_at,
                fin AS ended_at,
                total_iteraciones AS total_iterations,
                estado AS status
            FROM agent_sessions
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY inicio DESC LIMIT %s"
        values.append(min(max(int(limit), 1), 100))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            rows = [_stringify_datetime_fields(row) for row in cursor.fetchall()]
            cursor.close()
            return {"success": True, "data": rows}
        except Error as exc:
            log.error(f"Error listando sesiones de agente: {exc}")
            return {"success": False, "error": str(exc)}

    def get_conversation_context(
        self,
        session_id: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List persisted conversation turns for one session."""
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
                    session_id,
                    usuario_query AS user_query,
                    respuesta_agente AS agent_response,
                    timestamp,
                    pasos_utilizados AS steps_used
                FROM conversation_context
                WHERE session_id = %s
                ORDER BY timestamp ASC
                LIMIT %s
                """,
                (session_id, min(max(int(limit), 1), 200)),
            )
            rows = [_stringify_datetime_fields(row) for row in cursor.fetchall()]
            cursor.close()
            return {"success": True, "data": rows}
        except Error as exc:
            log.error(f"Error consultando contexto conversacional: {exc}")
            return {"success": False, "error": str(exc)}


def _stringify_datetime_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert date/datetime-like values to strings for API payloads."""
    normalized = dict(row)
    for key, value in list(normalized.items()):
        if value is not None and hasattr(value, "isoformat"):
            normalized[key] = str(value)
    return normalized
