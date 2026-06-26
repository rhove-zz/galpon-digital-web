"""Read-only SQL execution and schema extraction repository."""

from typing import Any, Dict, Optional, Protocol

from mysql.connector import Error

from src.config.settings import mysql_config
from src.utils.logger import log
from src.utils.schemas import DatabaseSchema


class MySQLRuntimeOwner(Protocol):
    """Minimal connector surface required by the SQL runtime repository."""

    connection: Any
    schema_cache: Optional[DatabaseSchema]

    def _ensure_connection(self) -> bool:
        """Ensure there is an active MySQL connection."""


class SqlRuntimeRepository:
    """Handle schema introspection, read-only queries and prompt formatting."""

    def __init__(self, connector: MySQLRuntimeOwner):
        self.connector = connector

    def get_database_schema(self) -> Optional[DatabaseSchema]:
        """Extract and cache the dynamic database schema from information_schema."""
        if self.connector.schema_cache:
            return self.connector.schema_cache

        if not self.connector._ensure_connection():
            return None

        try:
            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME
                """,
                (mysql_config.database,),
            )
            tables = cursor.fetchall()

            schema_dict = {}
            for table_info in tables:
                table_name = table_info["TABLE_NAME"]

                cursor.execute(
                    """
                    SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                    """,
                    (mysql_config.database, table_name),
                )
                columns = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = %s
                      AND REFERENCED_TABLE_NAME IS NOT NULL
                    """,
                    (mysql_config.database, table_name),
                )
                foreign_keys = cursor.fetchall()

                schema_dict[table_name] = {
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                }

            cursor.close()

            self.connector.schema_cache = DatabaseSchema(
                database=mysql_config.database,
                tables=schema_dict,
            )

            log.info(f"Schema extraido: {len(schema_dict)} tablas detectadas")
            return self.connector.schema_cache
        except Error as exc:
            log.error(f"Error al extraer schema: {exc}")
            return None

    def execute_read_query(self, query: str) -> Dict[str, Any]:
        """Execute a SELECT query and normalize the result payload."""
        if not self.connector._ensure_connection():
            return {
                "success": False,
                "error": "No se pudo establecer conexion con MySQL.",
            }

        try:
            if not query.strip().upper().startswith("SELECT"):
                return {
                    "success": False,
                    "error": "Solo se permiten queries SELECT. Otras operaciones son prohibidas.",
                }

            cursor = self.connector.connection.cursor(dictionary=True)
            cursor.execute(query)
            result = cursor.fetchall()
            cursor.close()

            log.debug(f"Query ejecutada exitosamente: {query[:100]}...")

            return {
                "success": True,
                "data": result,
                "rows_affected": len(result),
            }
        except Error as exc:
            error_msg = str(exc)
            log.warning(f"Error en query SQL: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "suggestion": "El LLM puede usar este error para corregir la sintaxis",
            }

    def format_schema_for_prompt(self) -> str:
        """Format the cached schema as text for LLM context injection."""
        if not self.connector.schema_cache:
            return ""

        schema_text = (
            f"## SCHEMA DE BASE DE DATOS: {self.connector.schema_cache.database}\n\n"
        )

        for table_name, table_info in self.connector.schema_cache.tables.items():
            schema_text += f"### Tabla: {table_name}\n"

            columns = table_info.get("columns", [])
            schema_text += "**Columnas:**\n"
            for col in columns:
                nullable = "NULL" if col.get("IS_NULLABLE") == "YES" else "NOT NULL"
                key_info = (
                    f" [{col.get('COLUMN_KEY')}]" if col.get("COLUMN_KEY") else ""
                )
                schema_text += (
                    f"  - {col['COLUMN_NAME']}: {col['COLUMN_TYPE']} "
                    f"{nullable}{key_info}\n"
                )

            fks = table_info.get("foreign_keys", [])
            if fks:
                schema_text += "\n**Relaciones (Foreign Keys):**\n"
                for fk in fks:
                    schema_text += (
                        "  - "
                        f"{fk['COLUMN_NAME']} -> "
                        f"{fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}\n"
                    )

            schema_text += "\n"

        return schema_text
