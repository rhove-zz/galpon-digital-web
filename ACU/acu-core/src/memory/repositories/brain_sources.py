"""BrainCore source and chunk persistence repository."""

import json
from typing import Any, Dict, List, Optional, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the BrainCore sources repository."""

    use_read_only: bool
    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class BrainSourceRepository:
    """Persist, list and delete BrainCore sources and chunks."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def upsert_brain_source(
        self,
        source_path: str,
        source_type: str,
        content_hash: str,
        metadata: Dict[str, Any],
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Persist a BrainCore source and replace its chunks."""
        if self.connector.use_read_only:
            return {
                "success": False,
                "error": "El conector actual es de solo lectura y no puede ingerir fuentes.",
            }

        if not source_path or not source_type or not content_hash:
            return {
                "success": False,
                "error": "source_path, source_type y content_hash son requeridos.",
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
                INSERT INTO brain_sources (
                    source_path,
                    source_type,
                    content_hash,
                    metadata,
                    estado
                )
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    source_type = VALUES(source_type),
                    content_hash = VALUES(content_hash),
                    metadata = VALUES(metadata),
                    estado = VALUES(estado)
                """,
                (
                    source_path,
                    source_type,
                    content_hash,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    "indexed",
                ),
            )
            self.connector.connection.commit()

            cursor.execute(
                """
                SELECT id, content_hash
                FROM brain_sources
                WHERE source_path = %s
                """,
                (source_path,),
            )
            source = cursor.fetchone()
            if not source:
                cursor.close()
                return {
                    "success": False,
                    "error": "No se pudo recuperar la fuente BrainCore indexada.",
                }

            source_id = source["id"]
            cursor.execute(
                "DELETE FROM brain_chunks WHERE source_id = %s", (source_id,)
            )

            for chunk in chunks:
                cursor.execute(
                    """
                    INSERT INTO brain_chunks (
                        source_id,
                        chunk_index,
                        chunk_hash,
                        titulo,
                        contenido,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        source_id,
                        chunk["chunk_index"],
                        chunk["chunk_hash"],
                        chunk.get("title", "Documento"),
                        chunk["content"],
                        json.dumps(chunk.get("metadata", {}), ensure_ascii=False),
                    ),
                )

            self.connector.connection.commit()
            cursor.close()
            return {
                "success": True,
                "data": {
                    "source_id": source_id,
                    "source_path": source_path,
                    "chunks_indexed": len(chunks),
                },
            }
        except Error as exc:
            log.error(f"Error ingiriendo fuente BrainCore: {exc}")
            return {"success": False, "error": str(exc)}

    def list_brain_sources(
        self,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List indexed BrainCore sources with chunk counts."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        where_clauses = []
        values: List[Any] = []
        if domain:
            where_clauses.append(
                "JSON_UNQUOTE(JSON_EXTRACT(s.metadata, '$.domain')) = %s"
            )
            values.append(domain)
        if source_type:
            where_clauses.append("s.source_type = %s")
            values.append(source_type)
        if status:
            where_clauses.append("s.estado = %s")
            values.append(status)

        query = """
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
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += """
            ORDER BY s.fecha_actualizacion DESC
            LIMIT %s
        """
        values.append(min(max(int(limit), 1), 100))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            rows = [_normalize_brain_source_row(row) for row in cursor.fetchall()]
            cursor.close()
            return {"success": True, "data": rows}
        except Error as exc:
            log.error(f"Error listando fuentes BrainCore: {exc}")
            return {"success": False, "error": str(exc)}

    def delete_brain_source(self, source_id: int) -> Dict[str, Any]:
        """Delete a BrainCore source and its chunks by source id."""
        if self.connector.use_read_only:
            return {
                "success": False,
                "error": "El conector actual es de solo lectura y no puede eliminar fuentes.",
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
                SELECT
                    id,
                    source_path,
                    source_type,
                    content_hash,
                    metadata,
                    estado AS status,
                    fecha_indexacion AS indexed_at,
                    fecha_actualizacion AS updated_at
                FROM brain_sources
                WHERE id = %s
                """,
                (source_id,),
            )
            source = cursor.fetchone()
            if not source:
                cursor.close()
                return {
                    "success": False,
                    "error": f"Fuente BrainCore no encontrada: {source_id}",
                }

            cursor.execute("DELETE FROM brain_sources WHERE id = %s", (source_id,))
            self.connector.connection.commit()
            cursor.close()

            normalized = _normalize_brain_source_row({**source, "chunks_count": 0})
            return {"success": True, "data": normalized}
        except Error as exc:
            log.error(f"Error eliminando fuente BrainCore: {exc}")
            return {"success": False, "error": str(exc)}


def _normalize_brain_source_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize BrainCore source rows for API responses."""
    normalized = dict(row)
    normalized["metadata"] = _loads_json_dict(normalized.get("metadata"))
    normalized["chunks_count"] = int(normalized.get("chunks_count") or 0)
    normalized["indexed_at"] = str(normalized.get("indexed_at"))
    normalized["updated_at"] = str(normalized.get("updated_at"))
    return normalized


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
