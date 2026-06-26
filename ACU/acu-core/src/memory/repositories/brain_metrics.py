"""BrainCore metrics persistence repository."""

from typing import Any, Dict, List, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the BrainCore metrics repository."""

    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class BrainMetricsRepository:
    """Query aggregate BrainCore metrics."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def get_brain_metrics(self) -> Dict[str, Any]:
        """Return aggregate BrainCore metrics for monitoring."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        totals_query = """
            SELECT
                (SELECT COUNT(*) FROM brain_decisions) AS decisions_count,
                COUNT(DISTINCT s.id) AS sources_count,
                COUNT(c.id) AS chunks_count,
                COUNT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(s.metadata, '$.domain'))) AS domains_count,
                MAX(s.fecha_indexacion) AS last_indexed_at,
                MAX(s.fecha_actualizacion) AS last_updated_at
            FROM brain_sources s
            LEFT JOIN brain_chunks c ON c.source_id = s.id
        """
        domains_query = """
            SELECT
                COALESCE(
                    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.metadata, '$.domain')), ''),
                    'generic'
                ) AS name,
                COUNT(DISTINCT s.id) AS sources_count,
                COUNT(c.id) AS chunks_count
            FROM brain_sources s
            LEFT JOIN brain_chunks c ON c.source_id = s.id
            GROUP BY name
            ORDER BY sources_count DESC, name ASC
            LIMIT 20
        """
        source_types_query = """
            SELECT
                COALESCE(NULLIF(s.source_type, ''), 'unknown') AS name,
                COUNT(DISTINCT s.id) AS sources_count,
                COUNT(c.id) AS chunks_count
            FROM brain_sources s
            LEFT JOIN brain_chunks c ON c.source_id = s.id
            GROUP BY name
            ORDER BY sources_count DESC, name ASC
            LIMIT 20
        """

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(totals_query)
            totals = cursor.fetchone() or {}
            cursor.execute(domains_query)
            domains = cursor.fetchall()
            cursor.execute(source_types_query)
            source_types = cursor.fetchall()
            cursor.close()
            return {
                "success": True,
                "data": _normalize_brain_metrics(
                    totals=totals,
                    domains=domains,
                    source_types=source_types,
                ),
            }
        except Error as exc:
            log.error(f"Error obteniendo metricas BrainCore: {exc}")
            return {"success": False, "error": str(exc)}


def _normalize_brain_metrics(
    totals: Dict[str, Any],
    domains: List[Dict[str, Any]],
    source_types: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Normalize BrainCore metrics rows for API responses."""
    return {
        "decisions_count": int(totals.get("decisions_count") or 0),
        "sources_count": int(totals.get("sources_count") or 0),
        "chunks_count": int(totals.get("chunks_count") or 0),
        "domains_count": int(totals.get("domains_count") or 0),
        "last_indexed_at": (
            str(totals.get("last_indexed_at"))
            if totals.get("last_indexed_at") is not None
            else None
        ),
        "last_updated_at": (
            str(totals.get("last_updated_at"))
            if totals.get("last_updated_at") is not None
            else None
        ),
        "domains": [_normalize_metric_bucket(row) for row in domains],
        "source_types": [_normalize_metric_bucket(row) for row in source_types],
    }


def _normalize_metric_bucket(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one aggregate metric bucket."""
    return {
        "name": str(row.get("name") or "unknown"),
        "sources_count": int(row.get("sources_count") or 0),
        "chunks_count": int(row.get("chunks_count") or 0),
    }
