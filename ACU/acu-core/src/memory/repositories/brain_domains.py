"""BrainCore domain export and delete repository."""

import json
from typing import Any, Dict, List, Optional, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the BrainCore domain repository."""

    use_read_only: bool
    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class BrainDomainRepository:
    """Export and delete BrainCore records by domain."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def export_brain_domain(
        self,
        domain: str,
        include_chunks: bool = True,
    ) -> Dict[str, Any]:
        """Export BrainCore records for a single domain."""
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
                WHERE domain = %s
                ORDER BY fecha_registro DESC
                """,
                (domain,),
            )
            decisions = [
                _normalize_brain_decision_row(row) for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.source_path,
                    s.source_type,
                    s.content_hash,
                    s.metadata,
                    s.estado AS status,
                    s.fecha_indexacion AS indexed_at,
                    s.fecha_actualizacion AS updated_at,
                    COALESCE(c.chunks_count, 0) AS chunks_count
                FROM brain_sources s
                LEFT JOIN (
                    SELECT source_id, COUNT(*) AS chunks_count
                    FROM brain_chunks
                    GROUP BY source_id
                ) c ON c.source_id = s.id
                WHERE JSON_UNQUOTE(JSON_EXTRACT(s.metadata, '$.domain')) = %s
                ORDER BY s.fecha_actualizacion DESC
                """,
                (domain,),
            )
            sources = [_normalize_brain_source_row(row) for row in cursor.fetchall()]
            chunks = []
            if include_chunks:
                cursor.execute(
                    """
                    SELECT
                        c.id,
                        c.source_id,
                        c.chunk_index,
                        c.chunk_hash,
                        c.titulo AS title,
                        c.contenido AS content,
                        c.metadata,
                        c.fecha_indexacion AS indexed_at,
                        s.source_path,
                        s.source_type
                    FROM brain_chunks c
                    JOIN brain_sources s ON s.id = c.source_id
                    WHERE JSON_UNQUOTE(JSON_EXTRACT(s.metadata, '$.domain')) = %s
                    ORDER BY s.source_path ASC, c.chunk_index ASC
                    """,
                    (domain,),
                )
                chunks = [
                    _normalize_brain_chunk_export_row(row) for row in cursor.fetchall()
                ]
            cursor.close()
            return {
                "success": True,
                "data": {
                    "domain": domain,
                    "decisions_count": len(decisions),
                    "sources_count": len(sources),
                    "chunks_count": len(chunks)
                    if include_chunks
                    else sum(source.get("chunks_count", 0) for source in sources),
                    "decisions": decisions,
                    "sources": sources,
                    "chunks": chunks,
                },
            }
        except Error as exc:
            log.error(f"Error exportando dominio BrainCore: {exc}")
            return {"success": False, "error": str(exc)}

    def delete_brain_domain(
        self,
        domain: str,
        delete_decisions: bool = False,
    ) -> Dict[str, Any]:
        """Delete all BrainCore sources for one domain and optional decisions."""
        if self.connector.use_read_only:
            return {
                "success": False,
                "error": "El conector actual es de solo lectura y no puede eliminar dominios.",
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
                SELECT id, source_path
                FROM brain_sources
                WHERE JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.domain')) = %s
                ORDER BY id ASC
                """,
                (domain,),
            )
            sources = cursor.fetchall()
            source_ids = [source["id"] for source in sources]
            source_paths = [str(source["source_path"]) for source in sources]
            chunks_deleted = 0
            sources_deleted = 0
            if source_ids:
                placeholders = ", ".join(["%s"] * len(source_ids))
                cursor.execute(
                    f"""
                    DELETE FROM brain_chunks
                    WHERE source_id IN ({placeholders})
                    """,
                    tuple(source_ids),
                )
                chunks_deleted = cursor.rowcount
                cursor.execute(
                    f"""
                    DELETE FROM brain_sources
                    WHERE id IN ({placeholders})
                    """,
                    tuple(source_ids),
                )
                sources_deleted = cursor.rowcount

            decisions_deleted = 0
            if delete_decisions:
                cursor.execute(
                    """
                    DELETE FROM brain_decisions
                    WHERE domain = %s
                    """,
                    (domain,),
                )
                decisions_deleted = cursor.rowcount

            self.connector.connection.commit()
            cursor.close()
            return {
                "success": True,
                "data": {
                    "domain": domain,
                    "sources_deleted": sources_deleted,
                    "chunks_deleted": chunks_deleted,
                    "decisions_deleted": decisions_deleted,
                    "vector_sources_deleted": 0,
                    "deleted_source_paths": source_paths,
                },
            }
        except Error as exc:
            log.error(f"Error eliminando dominio BrainCore: {exc}")
            return {"success": False, "error": str(exc)}


def _normalize_brain_decision_row(
    row: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Normalize JSON/date fields for BrainCore API responses."""
    if not row:
        return None

    normalized = dict(row)
    normalized["alternatives"] = _loads_json_list(normalized.get("alternatives"))
    normalized["tags"] = _loads_json_list(normalized.get("tags"))
    normalized["created_at"] = str(normalized.get("created_at"))
    normalized["updated_at"] = str(normalized.get("updated_at"))
    return normalized


def _normalize_brain_source_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize BrainCore source rows for API responses."""
    normalized = dict(row)
    normalized["metadata"] = _loads_json_dict(normalized.get("metadata"))
    normalized["chunks_count"] = int(normalized.get("chunks_count") or 0)
    normalized["indexed_at"] = str(normalized.get("indexed_at"))
    normalized["updated_at"] = str(normalized.get("updated_at"))
    return normalized


def _normalize_brain_chunk_export_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize BrainCore chunk rows for domain exports."""
    normalized = dict(row)
    normalized["metadata"] = _loads_json_dict(normalized.get("metadata"))
    normalized["indexed_at"] = str(normalized.get("indexed_at"))
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
