"""Evolutionary memory lessons persistence repository."""

from typing import Any, Dict, List, Protocol

from mysql.connector import Error

from src.utils.logger import log


class MySQLConnectionOwner(Protocol):
    """Minimal connector surface required by the lessons repository."""

    use_read_only: bool
    connection: Any

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class LessonsRepository:
    """Persist and query lessons in memoria_evolutiva."""

    def __init__(self, connector: MySQLConnectionOwner):
        self.connector = connector

    def register_lesson(
        self,
        categoria: str,
        descripcion: str,
        relevancia: int = 1,
    ) -> Dict[str, Any]:
        """Insert a new memory lesson into memoria_evolutiva."""
        if self.connector.use_read_only:
            return {
                "success": False,
                "error": "El conector actual es de solo lectura y no puede registrar lecciones.",
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
                INSERT INTO memoria_evolutiva (categoria, leccion_aprendida, relevancia)
                VALUES (%s, %s, %s)
                """,
                (categoria, descripcion, relevancia),
            )
            lesson_id = cursor.lastrowid
            self.connector.connection.commit()

            cursor.execute(
                """
                SELECT id, categoria, leccion_aprendida, fecha_registro, relevancia, veces_utilizada
                FROM memoria_evolutiva
                WHERE id = %s
                """,
                (lesson_id,),
            )
            lesson = cursor.fetchone()
            cursor.close()

            log.info(f"Leccion registrada en memoria_evolutiva con id={lesson_id}")
            return {"success": True, "data": lesson}
        except Error as exc:
            log.error(f"Error registrando leccion: {exc}")
            return {"success": False, "error": str(exc)}

    def query_lessons(self, terminos: str, limit: int = 5) -> Dict[str, Any]:
        """Search lessons by category and body text."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        search_terms = _normalize_search_terms(terminos)
        if not search_terms:
            return {"success": True, "data": []}

        where_clauses = []
        values: List[Any] = []
        for term in search_terms:
            like_term = f"%{term}%"
            where_clauses.append("LOWER(categoria) LIKE %s")
            values.append(like_term)
            where_clauses.append("LOWER(leccion_aprendida) LIKE %s")
            values.append(like_term)

        query = """
            SELECT id, categoria, leccion_aprendida, fecha_registro, relevancia, veces_utilizada
            FROM memoria_evolutiva
        """
        if where_clauses:
            query += " WHERE " + " OR ".join(where_clauses)
        query += " ORDER BY relevancia DESC, fecha_registro DESC LIMIT %s"
        values.append(max(limit * 5, 10))

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query, tuple(values))
            candidates = cursor.fetchall()
            cursor.close()

            ranked_results = _rank_lessons(candidates, search_terms)[:limit]
            return {"success": True, "data": ranked_results}
        except Error as exc:
            log.error(f"Error consultando lecciones: {exc}")
            return {"success": False, "error": str(exc)}

    def increment_lesson_usage(self, lesson_ids: List[int]) -> bool:
        """Increment veces_utilizada for the provided lesson ids."""
        if self.connector.use_read_only or not lesson_ids:
            return False

        if not self.connector._ensure_connection():
            return False

        try:
            cursor = self.connector.connection.cursor()
            cursor.executemany(
                """
                UPDATE memoria_evolutiva
                SET veces_utilizada = veces_utilizada + 1
                WHERE id = %s
                """,
                [(lesson_id,) for lesson_id in lesson_ids],
            )
            self.connector.connection.commit()
            cursor.close()
            return True
        except Error as exc:
            log.warning(f"No se pudo actualizar el uso de lecciones: {exc}")
            return False


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


def _rank_lessons(
    lessons: List[Dict[str, Any]],
    search_terms: List[str],
) -> List[Dict[str, Any]]:
    """Rank lessons by match quality and relevance."""
    ranked = []
    for lesson in lessons:
        categoria = str(lesson.get("categoria", "")).lower()
        body = str(lesson.get("leccion_aprendida", "")).lower()
        haystack = f"{categoria} {body}"

        token_hits = sum(1 for term in search_terms if term in haystack)
        token_frequency = sum(haystack.count(term) for term in search_terms)
        category_bonus = sum(2 for term in search_terms if term in categoria)
        score = (
            token_hits
            + category_bonus
            + (token_frequency * 0.25)
            + (lesson.get("relevancia", 0) * 0.1)
        )

        if score <= 0:
            continue

        ranked.append(
            {
                "id": lesson.get("id"),
                "categoria": lesson.get("categoria"),
                "leccion": lesson.get("leccion_aprendida"),
                "fecha": str(lesson.get("fecha_registro")),
                "relevancia": lesson.get("relevancia"),
                "veces_utilizada": lesson.get("veces_utilizada"),
                "score": round(score, 3),
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked
