"""BrainCore decision persistence repository."""

import json
from typing import Any, Dict, List, Optional, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the BrainCore decisions repository."""

    use_read_only: bool
    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class BrainDecisionRepository:
    """Persist and query BrainCore architectural decisions."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def register_brain_decision(
        self,
        title: str,
        context: str,
        decision: str,
        alternatives: List[str],
        impact: str,
        domain: str = "generic",
        status: str = "accepted",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Persist a BrainCore architectural decision record."""
        if self.connector.use_read_only:
            return {
                "success": False,
                "error": "El conector actual es de solo lectura y no puede registrar decisiones.",
            }

        if not title or not context or not decision:
            return {
                "success": False,
                "error": "Los campos title, context y decision son requeridos.",
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
                INSERT INTO brain_decisions (
                    titulo,
                    contexto,
                    decision_text,
                    alternativas,
                    impacto,
                    domain,
                    estado,
                    tags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    title,
                    context,
                    decision,
                    json.dumps(alternatives or [], ensure_ascii=False),
                    impact,
                    domain,
                    status,
                    json.dumps(tags or [], ensure_ascii=False),
                ),
            )
            decision_id = cursor.lastrowid
            self.connector.connection.commit()

            cursor.execute(
                """
                SELECT
                    id,
                    titulo AS title,
                    contexto AS context,
                    decision_text AS decision,
                    alternativas AS alternatives,
                    impacto AS impact,
                    domain,
                    estado AS status,
                    tags,
                    fecha_registro AS created_at,
                    fecha_actualizacion AS updated_at
                FROM brain_decisions
                WHERE id = %s
                """,
                (decision_id,),
            )
            row = _normalize_brain_decision_row(cursor.fetchone())
            cursor.close()

            log.info(f"Decision BrainCore registrada con id={decision_id}")
            return {"success": True, "data": row}
        except Error as exc:
            log.error(f"Error registrando decision BrainCore: {exc}")
            return {"success": False, "error": str(exc)}

    def list_brain_decisions(
        self,
        search: str = "",
        domain: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List BrainCore decisions with optional filters."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        where_clauses = []
        values: List[Any] = []

        if search:
            like_search = f"%{search.lower()}%"
            where_clauses.append(
                """
                (
                    LOWER(titulo) LIKE %s
                    OR LOWER(contexto) LIKE %s
                    OR LOWER(decision_text) LIKE %s
                    OR LOWER(impacto) LIKE %s
                )
                """
            )
            values.extend([like_search, like_search, like_search, like_search])

        if domain:
            where_clauses.append("domain = %s")
            values.append(domain)

        if status:
            where_clauses.append("estado = %s")
            values.append(status)

        query = """
            SELECT
                id,
                titulo AS title,
                contexto AS context,
                decision_text AS decision,
                alternativas AS alternatives,
                impacto AS impact,
                domain,
                estado AS status,
                tags,
                fecha_registro AS created_at,
                fecha_actualizacion AS updated_at
            FROM brain_decisions
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY fecha_registro DESC LIMIT %s"
        values.append(min(max(int(limit), 1), 100))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            rows = [_normalize_brain_decision_row(row) for row in cursor.fetchall()]
            cursor.close()
            return {"success": True, "data": rows}
        except Error as exc:
            log.error(f"Error listando decisiones BrainCore: {exc}")
            return {"success": False, "error": str(exc)}


def _normalize_brain_decision_row(
    row: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Normalize BrainCore decision JSON/date fields for API responses."""
    if not row:
        return None

    normalized = dict(row)
    normalized["alternatives"] = _loads_json_list(normalized.get("alternatives"))
    normalized["tags"] = _loads_json_list(normalized.get("tags"))
    normalized["created_at"] = str(normalized.get("created_at"))
    normalized["updated_at"] = str(normalized.get("updated_at"))
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
