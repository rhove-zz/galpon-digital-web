"""
MySQL database connection and schema management.
Handles dynamic schema injection, read-only SQL execution, and memory persistence.
"""

from typing import Any, Dict, List, Optional

import mysql.connector
from mysql.connector import Error

from src.config.settings import mysql_config
from src.memory.repositories.audit import AuditRepository
from src.memory.repositories.api_keys import ApiKeyRepository
from src.memory.repositories.brain_decisions import BrainDecisionRepository
from src.memory.repositories.brain_domains import BrainDomainRepository
from src.memory.repositories.brain_metrics import BrainMetricsRepository
from src.memory.repositories.brain_search import BrainSearchRepository
from src.memory.repositories.brain_sources import BrainSourceRepository
from src.memory.repositories.lessons import LessonsRepository
from src.memory.repositories.sessions import SessionsRepository
from src.memory.repositories.sql_runtime import SqlRuntimeRepository
from src.utils.logger import log
from src.utils.schemas import DatabaseSchema


class MySQLConnector:
    """
    Manages MySQL connections and operations.
    - Dynamic schema extraction
    - Safe read-only queries
    - Evolutionary memory persistence
    """

    def __init__(self, use_read_only: bool = True):
        """
        Initialize MySQL connector.

        Args:
            use_read_only: Use read-only credentials if True
        """
        self.use_read_only = use_read_only
        self.connection: Any = None
        self.schema_cache: Optional[DatabaseSchema] = None

    def _build_config(self) -> Dict[str, Any]:
        """Build connector configuration from environment settings."""
        return {
            "host": mysql_config.host,
            "port": mysql_config.port,
            "user": (
                mysql_config.read_only_user if self.use_read_only else mysql_config.user
            ),
            "password": (
                mysql_config.read_only_password
                if self.use_read_only
                else mysql_config.password
            ),
            "database": mysql_config.database,
            "autocommit": True,
        }

    def is_connected(self) -> bool:
        """Check whether the underlying MySQL connection is active."""
        return bool(self.connection and self.connection.is_connected())

    def connect(self) -> bool:
        """Establish connection to MySQL."""
        if self.is_connected():
            return True

        try:
            self.connection = mysql.connector.connect(**self._build_config())
            log.info(
                f"Conexion exitosa a MySQL: {mysql_config.host}:{mysql_config.port}"
            )
            return True
        except Error as exc:
            log.error(f"Error de conexion MySQL: {exc}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.is_connected():
            self.connection.close()
            log.info("Conexion MySQL cerrada")

    def _ensure_connection(self) -> bool:
        """Connect on demand if the current connection is missing or closed."""
        return self.connect()

    def get_database_schema(self) -> Optional[DatabaseSchema]:
        """
        Extract dynamic database schema from information_schema.

        Returns:
            DatabaseSchema object or None if extraction fails
        """
        return SqlRuntimeRepository(self).get_database_schema()

    def execute_read_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a read-only SQL query with error handling.

        Args:
            query: SQL SELECT query

        Returns:
            Dict with 'success', 'data' (or 'error' if failed)
        """
        return SqlRuntimeRepository(self).execute_read_query(query=query)

    def register_lesson(
        self,
        categoria: str,
        descripcion: str,
        relevancia: int = 1,
    ) -> Dict[str, Any]:
        """
        Insert a new memory lesson into memoria_evolutiva.

        Returns:
            Dict with inserted id and timestamp on success.
        """
        return LessonsRepository(self).register_lesson(
            categoria=categoria,
            descripcion=descripcion,
            relevancia=relevancia,
        )

    def query_lessons(self, terminos: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search lessons by category and body text.

        Args:
            terminos: Search terms
            limit: Maximum number of lessons to return
        """
        return LessonsRepository(self).query_lessons(terminos=terminos, limit=limit)

    def increment_lesson_usage(self, lesson_ids: List[int]) -> bool:
        """Increment veces_utilizada for the provided lesson ids."""
        return LessonsRepository(self).increment_lesson_usage(lesson_ids=lesson_ids)

    def log_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
        execution_time_ms: float,
        success: bool,
    ) -> bool:
        """Persist tool execution metadata for auditing."""
        return AuditRepository(self).log_tool_execution(
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            execution_time_ms=execution_time_ms,
            success=success,
        )

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
        return AuditRepository(self).log_api_access(
            method=method,
            path=path,
            status_code=status_code,
            key_fingerprint=key_fingerprint,
            roles=roles,
            client_ip=client_ip,
            user_agent=user_agent,
            authorized=authorized,
            duration_ms=duration_ms,
        )

    def prune_tool_execution_log(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete tool execution logs older than the specified days."""
        return AuditRepository(self).prune_tool_execution_log(
            older_than_days=older_than_days
        )

    def prune_api_access_log(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete API access logs older than the specified days."""
        return AuditRepository(self).prune_api_access_log(
            older_than_days=older_than_days
        )

    def prune_conversation_context(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete persisted conversation turns older than the specified days."""
        return SessionsRepository(self).prune_conversation_context(
            older_than_days=older_than_days
        )

    def prune_agent_sessions(self, older_than_days: int = 30) -> Dict[str, Any]:
        """Delete completed agent sessions older than the specified days."""
        return SessionsRepository(self).prune_agent_sessions(
            older_than_days=older_than_days
        )

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
        return ApiKeyRepository(self).create_api_key(
            name=name,
            key_hash=key_hash,
            key_fingerprint=key_fingerprint,
            roles=roles,
            expires_at=expires_at,
            created_by=created_by,
        )

    def find_active_api_key(self, key_hash: str) -> Dict[str, Any]:
        """Find one active managed API key by hash."""
        return ApiKeyRepository(self).find_active_api_key(key_hash=key_hash)

    def list_api_keys(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List managed API key metadata without secrets."""
        return ApiKeyRepository(self).list_api_keys(status=status, limit=limit)

    def revoke_api_key(self, key_id: int) -> Dict[str, Any]:
        """Revoke one managed API key by id."""
        return ApiKeyRepository(self).revoke_api_key(key_id=key_id)

    def start_agent_session(self, session_id: str, domain: str) -> bool:
        """Persist the start of an agent session."""
        return SessionsRepository(self).start_agent_session(
            session_id=session_id,
            domain=domain,
        )

    def end_agent_session(
        self,
        session_id: str,
        total_iterations: int,
        status: str = "completed",
    ) -> bool:
        """Persist the end state of an agent session."""
        return SessionsRepository(self).end_agent_session(
            session_id=session_id,
            total_iterations=total_iterations,
            status=status,
        )

    def log_conversation_context(
        self,
        session_id: str,
        user_query: str,
        agent_response: str,
        steps_used: int,
    ) -> bool:
        """Persist one user/agent exchange for the current session."""
        return SessionsRepository(self).log_conversation_context(
            session_id=session_id,
            user_query=user_query,
            agent_response=agent_response,
            steps_used=steps_used,
        )

    def list_agent_sessions(
        self,
        domain: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List persisted agent sessions."""
        return SessionsRepository(self).list_agent_sessions(
            domain=domain,
            status=status,
            limit=limit,
        )

    def get_conversation_context(
        self,
        session_id: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List persisted conversation turns for one session."""
        return SessionsRepository(self).get_conversation_context(
            session_id=session_id,
            limit=limit,
        )

    def list_tool_executions(
        self,
        tool_name: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List persisted tool execution audit rows."""
        return AuditRepository(self).list_tool_executions(
            tool_name=tool_name,
            success=success,
            limit=limit,
        )

    def list_api_access_log(
        self,
        path: Optional[str] = None,
        status_code: Optional[int] = None,
        authorized: Optional[bool] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List persisted API access audit rows."""
        return AuditRepository(self).list_api_access_log(
            path=path,
            status_code=status_code,
            authorized=authorized,
            limit=limit,
        )

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
        return BrainDecisionRepository(self).register_brain_decision(
            title=title,
            context=context,
            decision=decision,
            alternatives=alternatives,
            impact=impact,
            domain=domain,
            status=status,
            tags=tags,
        )

    def list_brain_decisions(
        self,
        search: str = "",
        domain: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List BrainCore decisions with optional filters."""
        return BrainDecisionRepository(self).list_brain_decisions(
            search=search,
            domain=domain,
            status=status,
            limit=limit,
        )

    def upsert_brain_source(
        self,
        source_path: str,
        source_type: str,
        content_hash: str,
        metadata: Dict[str, Any],
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Persist a BrainCore source and replace its chunks."""
        return BrainSourceRepository(self).upsert_brain_source(
            source_path=source_path,
            source_type=source_type,
            content_hash=content_hash,
            metadata=metadata,
            chunks=chunks,
        )

    def list_brain_sources(
        self,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List indexed BrainCore sources with chunk counts."""
        return BrainSourceRepository(self).list_brain_sources(
            domain=domain,
            source_type=source_type,
            status=status,
            limit=limit,
        )

    def get_brain_metrics(self) -> Dict[str, Any]:
        """Return aggregate BrainCore metrics for monitoring."""
        return BrainMetricsRepository(self).get_brain_metrics()

    def delete_brain_source(self, source_id: int) -> Dict[str, Any]:
        """Delete a BrainCore source and its chunks by source id."""
        return BrainSourceRepository(self).delete_brain_source(source_id=source_id)

    def export_brain_domain(
        self,
        domain: str,
        include_chunks: bool = True,
    ) -> Dict[str, Any]:
        """Export BrainCore records for a single domain."""
        return BrainDomainRepository(self).export_brain_domain(
            domain=domain,
            include_chunks=include_chunks,
        )

    def delete_brain_domain(
        self,
        domain: str,
        delete_decisions: bool = False,
    ) -> Dict[str, Any]:
        """Delete all BrainCore sources for one domain and optional decisions."""
        return BrainDomainRepository(self).delete_brain_domain(
            domain=domain,
            delete_decisions=delete_decisions,
        )

    def search_brain_chunks(
        self,
        query_text: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Search BrainCore chunks using lexical ranking."""
        return BrainSearchRepository(self).search_brain_chunks(
            query_text=query_text,
            domain=domain,
            source_type=source_type,
            limit=limit,
        )

    def format_schema_for_prompt(self) -> str:
        """
        Format database schema as text for injection in system prompt.

        Returns:
            Formatted schema string for LLM context
        """
        return SqlRuntimeRepository(self).format_schema_for_prompt()


_db_connectors: Dict[str, MySQLConnector] = {}


def get_db_connector(use_read_only: bool = True) -> MySQLConnector:
    """Get or create a singleton database connector per access mode."""
    connector_key = "read_only" if use_read_only else "read_write"
    if connector_key not in _db_connectors:
        _db_connectors[connector_key] = MySQLConnector(use_read_only=use_read_only)
    return _db_connectors[connector_key]
