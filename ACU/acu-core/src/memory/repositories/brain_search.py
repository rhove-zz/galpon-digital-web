"""BrainCore lexical search repository."""

import json
from typing import Any, Dict, List, Optional, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the BrainCore search repository."""

    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class BrainSearchRepository:
    """Search BrainCore chunks using lexical ranking."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def search_brain_chunks(
        self,
        query_text: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Search BrainCore chunks using lexical ranking."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        search_terms = _normalize_search_terms(query_text)
        if not search_terms:
            return {"success": True, "data": []}

        where_clauses = []
        values: List[Any] = []
        for term in search_terms:
            like_term = f"%{term}%"
            where_clauses.append(
                """
                (
                    LOWER(c.titulo) LIKE %s
                    OR LOWER(c.contenido) LIKE %s
                    OR LOWER(s.source_path) LIKE %s
                )
                """
            )
            values.extend([like_term, like_term, like_term])

        if domain:
            where_clauses.append(
                "JSON_UNQUOTE(JSON_EXTRACT(s.metadata, '$.domain')) = %s"
            )
            values.append(domain)

        if source_type:
            where_clauses.append("s.source_type = %s")
            values.append(source_type)

        query = """
            SELECT
                c.id AS chunk_id,
                c.source_id,
                c.chunk_index,
                c.titulo AS title,
                c.contenido AS content,
                c.metadata AS chunk_metadata,
                s.source_path,
                s.source_type,
                s.metadata AS source_metadata,
                s.fecha_indexacion AS indexed_at
            FROM brain_chunks c
            JOIN brain_sources s ON s.id = c.source_id
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY s.fecha_indexacion DESC LIMIT %s"
        values.append(min(max(int(limit) * 5, 10), 200))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            candidates = cursor.fetchall()
            cursor.close()
            ranked_results = _rank_brain_chunks(
                candidates=candidates,
                query_text=query_text,
                search_terms=search_terms,
                limit=limit,
            )
            return {"success": True, "data": ranked_results}
        except Error as exc:
            log.error(f"Error buscando chunks BrainCore: {exc}")
            return {"success": False, "error": str(exc)}


def _normalize_search_terms(terminos: str) -> List[str]:
    """Normalize input terms for text matching."""
    normalized = [
        token.strip().lower()
        for token in terminos.replace(",", " ").split()
        if token.strip()
    ]
    if normalized:
        return normalized
    stripped = terminos.strip().lower()
    return [stripped] if stripped else []


def _rank_brain_chunks(
    candidates: List[Dict[str, Any]],
    query_text: str,
    search_terms: List[str],
    limit: int,
) -> List[Dict[str, Any]]:
    """Rank BrainCore chunks by phrase and token overlap."""
    ranked = []
    normalized_query = query_text.strip().lower()
    for candidate in candidates:
        title = str(candidate.get("title") or "")
        content = str(candidate.get("content") or "")
        source_path = str(candidate.get("source_path") or "")
        haystack = f"{title} {content} {source_path}".lower()

        phrase_bonus = 4.0 if normalized_query and normalized_query in haystack else 0.0
        token_hits = sum(1.0 for term in search_terms if term in haystack)
        token_frequency = sum(haystack.count(term) for term in search_terms)
        title_bonus = sum(2.0 for term in search_terms if term in title.lower())
        score = phrase_bonus + token_hits + (token_frequency * 0.15) + title_bonus
        if score <= 0:
            continue

        ranked.append(
            {
                "chunk_id": candidate.get("chunk_id"),
                "source_id": candidate.get("source_id"),
                "source_path": source_path,
                "source_type": candidate.get("source_type"),
                "title": title or "Documento",
                "content": _extract_text_snippet(content, search_terms),
                "similarity": round(min(score / max(len(search_terms) + 4, 4), 1.0), 3),
                "metadata": {
                    "chunk": _loads_json_dict(candidate.get("chunk_metadata")),
                    "source": _loads_json_dict(candidate.get("source_metadata")),
                },
                "indexed_at": str(candidate.get("indexed_at")),
                "_score": score,
            }
        )

    ranked.sort(key=lambda item: float(str(item.get("_score", 0))), reverse=True)
    top_results = ranked[: min(max(int(limit), 1), 20)]
    for item in top_results:
        item.pop("_score", None)
    return top_results


def _extract_text_snippet(
    content: str,
    search_terms: List[str],
    radius: int = 180,
) -> str:
    """Extract a compact snippet around the first matching term."""
    collapsed = " ".join(content.split())
    lower_content = collapsed.lower()
    positions = [
        lower_content.find(term)
        for term in search_terms
        if term and lower_content.find(term) != -1
    ]
    if not positions:
        return collapsed[: min(len(collapsed), 360)]

    start = max(min(positions) - radius, 0)
    end = min(start + 360, len(collapsed))
    snippet = collapsed[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(collapsed):
        snippet = snippet + "..."
    return snippet


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
