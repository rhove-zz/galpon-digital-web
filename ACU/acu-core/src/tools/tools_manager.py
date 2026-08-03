"""
Tools manager for ACU Agent.
Defines and executes available tools:
- ejecutar_sql_lectura: SQL read queries
- buscar_documentos: optional vector search with lexical fallback
- buscar_contexto_braincore: search BrainCore agentic memory
- registrar_leccion: store learned lessons in MySQL
- consultar_lecciones_aprendidas: query learned lessons from MySQL
"""

import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import markdownify

from src.braincore.manager import BrainCoreManager, get_braincore_manager
from src.config.settings import system_config, vectordb_config
from src.memory.mysql_manager import get_db_connector
from src.memory.redis_manager import redis_manager
from src.utils.logger import log
from src.utils.schemas import ToolCall, ToolResult, ToolType


class ToolsManager:
    """
    Central manager for all agent tools.
    Orchestrates tool execution with error handling and logging.
    """

    SEARCHABLE_EXTENSIONS = {".md", ".txt", ".sql"}
    VECTOR_COLLECTION_NAME = "acu_project_documents"
    SKIP_DIRECTORIES = {
        "__pycache__",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        "venv",
        ".venv",
    }
    SENSITIVE_TOOLS = {ToolType.PYTHON_SANDBOX, ToolType.API_REST, ToolType.FILE_SYSTEM}
    READ_ONLY_TOOLS = {
        ToolType.SQL_READ,
        ToolType.VECTOR_SEARCH,
        ToolType.BRAINCORE_SEARCH,
        ToolType.READ_SHARED_MEMORY,
    }
    WRITE_TOOLS = {
        ToolType.REGISTER_LESSON,
        ToolType.QUERY_LESSONS,
        ToolType.WRITE_SHARED_MEMORY,
        ToolType.DELEGATE_TASK,
    }
    EXTERNAL_TOOLS = {
        ToolType.WEB_READ,
        ToolType.WEB_SEARCH,
        ToolType.API_REST,
    }
    SAFE_MODE_BLOCKED_TOOLS = {
        ToolType.REGISTER_LESSON,
        ToolType.QUERY_LESSONS,
        ToolType.WEB_READ,
        ToolType.WEB_SEARCH,
        ToolType.API_REST,
        ToolType.FILE_SYSTEM,
        ToolType.PYTHON_SANDBOX,
        ToolType.DELEGATE_TASK,
        ToolType.WRITE_SHARED_MEMORY,
    }
    AUDIT_SENSITIVE_KEYS = {
        "authorization",
        "cookie",
        "headers",
        "password",
        "request_body",
        "request_headers",
        "secret",
        "token",
        "x-api-key",
        "x-acu-api-key",
    }

    def __init__(self):
        """Initialize tools manager."""
        self.db_connector = get_db_connector(use_read_only=True)
        self.write_connector = get_db_connector(use_read_only=False)
        self.braincore_manager = (
            BrainCoreManager(db_connector=self.db_connector)
            if system_config.production_read_only
            else get_braincore_manager()
        )
        self.execution_log: List[ToolResult] = []
        self.project_root = Path(__file__).resolve().parents[2]
        self._document_index: List[Dict[str, str]] = []
        self.vector_config = vectordb_config
        self.vector_search_enabled = vectordb_config.enabled
        self._vector_collection = None

    async def execute_tool(
        self,
        tool_call: ToolCall,
        session_id: str = "default_session",
        require_approval: bool = True,
        agent_domain: str = "generic",
        agent_persona: str = "default",
    ) -> ToolResult:
        """
        Execute a tool call and return result.

        Args:
            tool_call: Structured tool invocation
            session_id: The session ID of the caller agent

        Returns:
            ToolResult with execution details
        """
        start_time = time.time()
        tool_name = tool_call.tool

        try:
            log.info(f"Ejecutando herramienta: {tool_name}")

            block_reason = self._tool_policy_block_reason(tool_name)
            if block_reason:
                execution_time_ms = (time.time() - start_time) * 1000
                tool_result = ToolResult(
                    tool=tool_name,
                    success=False,
                    result=None,
                    error=block_reason,
                    execution_time_ms=execution_time_ms,
                    status="blocked_by_policy",
                )
                self.execution_log.append(tool_result)
                self._audit_tool_execution(
                    tool_call=tool_call,
                    raw_result={
                        "success": False,
                        "error": block_reason,
                        "status": "blocked_by_policy",
                    },
                    execution_time_ms=execution_time_ms,
                    success=False,
                )
                return tool_result

            if require_approval and tool_name in self.SENSITIVE_TOOLS:
                tool_id = str(uuid.uuid4())
                await redis_manager.set_pending_tool(
                    tool_id,
                    {
                        "tool": tool_name.value,
                        "parameters": tool_call.parameters,
                        "reasoning": tool_call.reasoning,
                        "session_id": session_id,
                        "domain": agent_domain,
                        "persona": agent_persona,
                        "status": "pending",
                        "timestamp": time.time(),
                    },
                )
                log.info(f"Herramienta {tool_name} pendiente de aprobacion [{tool_id}]")

                execution_time_ms = (time.time() - start_time) * 1000
                result = {
                    "success": False,
                    "error": "Herramienta pendiente de aprobacion humana",
                    "status": "pending_approval",
                    "pending_tool_id": tool_id,
                }
                error_message = str(result["error"])
                tool_result = ToolResult(
                    tool=tool_name,
                    success=False,
                    result=None,
                    error=error_message,
                    execution_time_ms=execution_time_ms,
                    status="pending_approval",
                    pending_tool_id=tool_id,
                )
                self.execution_log.append(tool_result)
                self._audit_tool_execution(
                    tool_call=tool_call,
                    raw_result=result,
                    execution_time_ms=execution_time_ms,
                    success=False,
                )
                return tool_result

            if tool_name == ToolType.SQL_READ:
                result = await self._execute_sql_read(tool_call.parameters)
            elif tool_name == ToolType.VECTOR_SEARCH:
                result = await self._buscar_documentos(tool_call.parameters)
            elif tool_name == ToolType.BRAINCORE_SEARCH:
                result = await self._buscar_contexto_braincore(tool_call.parameters)
            elif tool_name == ToolType.REGISTER_LESSON:
                result = await self._registrar_leccion(tool_call.parameters)
            elif tool_name == ToolType.QUERY_LESSONS:
                result = await self._consultar_lecciones_aprendidas(
                    tool_call.parameters
                )
            elif tool_name == ToolType.WEB_READ:
                result = await self._leer_pagina_web(tool_call.parameters)
            elif tool_name == ToolType.WEB_SEARCH:
                result = await self._buscar_web(tool_call.parameters)
            elif tool_name == ToolType.API_REST:
                result = await self._peticion_api_rest(tool_call.parameters)
            elif tool_name == ToolType.FILE_SYSTEM:
                result = await self._gestionar_archivos(tool_call.parameters)
            elif tool_name == ToolType.PYTHON_SANDBOX:
                result = await self._ejecutar_python(tool_call.parameters)
            elif tool_name == ToolType.DELEGATE_TASK:
                result = await self._delegar_tarea(tool_call.parameters, session_id)
            elif tool_name == ToolType.WRITE_SHARED_MEMORY:
                result = await self._escribir_memoria_compartida(
                    tool_call.parameters, session_id
                )
            elif tool_name == ToolType.READ_SHARED_MEMORY:
                result = await self._leer_memoria_compartida(
                    tool_call.parameters, session_id
                )
            else:
                result = {
                    "success": False,
                    "error": f"Herramienta desconocida: {tool_name}",
                }

            execution_time_ms = (time.time() - start_time) * 1000
            result_success = bool(result.get("success", False))
            result_error = result.get("error")
            tool_result = ToolResult(
                tool=tool_name,
                success=result_success,
                result=result.get("data") if result_success else None,
                error=str(result_error)
                if not result_success and result_error
                else None,
                execution_time_ms=execution_time_ms,
            )

            self.execution_log.append(tool_result)
            self._audit_tool_execution(
                tool_call=tool_call,
                raw_result=result,
                execution_time_ms=execution_time_ms,
                success=tool_result.success,
            )
            return tool_result
        except Exception as exc:
            log.error(f"Error ejecutando herramienta: {exc}")
            execution_time_ms = (time.time() - start_time) * 1000
            tool_result = ToolResult(
                tool=tool_call.tool,
                success=False,
                result=None,
                error=str(exc),
                execution_time_ms=execution_time_ms,
            )
            self.execution_log.append(tool_result)
            self._audit_tool_execution(
                tool_call=tool_call,
                raw_result={"success": False, "error": str(exc)},
                execution_time_ms=execution_time_ms,
                success=False,
            )
            return tool_result

    async def execute_pending_tool(self, tool_id: str) -> ToolResult:
        """Execute a previously approved sensitive tool without re-queuing HITL."""
        pending_data = await redis_manager.get_pending_tool(tool_id)
        if not pending_data:
            return ToolResult(
                tool=ToolType.API_REST,
                success=False,
                result=None,
                error="Tool call no encontrado o expirado",
                execution_time_ms=0.0,
                status="not_found",
                pending_tool_id=tool_id,
            )

        if pending_data.get("status") != "approved":
            tool_value = str(pending_data.get("tool", ToolType.API_REST.value))
            return ToolResult(
                tool=ToolType(tool_value),
                success=False,
                result=None,
                error="Tool call no aprobado",
                execution_time_ms=0.0,
                status=str(pending_data.get("status", "pending")),
                pending_tool_id=tool_id,
            )

        tool_call = ToolCall(
            tool=ToolType(str(pending_data["tool"])),
            parameters=pending_data.get("parameters", {}),
            reasoning=pending_data.get("reasoning"),
        )
        result = await self.execute_tool(
            tool_call,
            session_id=str(pending_data.get("session_id", "default_session")),
            require_approval=False,
            agent_domain=str(pending_data.get("domain", "generic")),
            agent_persona=str(pending_data.get("persona", "default")),
        )
        final_status = "executed" if result.success else "failed"
        pending_data["status"] = final_status
        pending_data["result"] = result.model_dump(mode="json")
        await redis_manager.set_pending_tool(tool_id, pending_data)
        result.status = final_status
        result.pending_tool_id = tool_id
        return result

    def _audit_tool_execution(
        self,
        tool_call: ToolCall,
        raw_result: Dict[str, Any],
        execution_time_ms: float,
        success: bool,
    ) -> None:
        """Persist tool execution metadata without affecting tool flow."""
        if system_config.production_read_only:
            log.debug("Auditoria de herramienta omitida por ACU_PRODUCTION_READ_ONLY")
            return
        try:
            audited = self.write_connector.log_tool_execution(
                tool_name=str(tool_call.tool.value),
                parameters=self._sanitize_audit_payload(tool_call.parameters),
                result=self._sanitize_audit_payload(raw_result),
                execution_time_ms=execution_time_ms,
                success=success,
            )
            if not audited:
                log.debug("Auditoria de herramienta no persistida")
        except Exception as exc:
            log.warning(f"No se pudo auditar ejecucion de herramienta: {exc}")

    def _tool_policy_block_reason(self, tool_name: ToolType) -> Optional[str]:
        """Return a safe denial reason when the tool is blocked by policy."""
        if not system_config.tools_enabled:
            return "Herramientas bloqueadas por ACU_TOOLS_ENABLED"

        if tool_name in self.READ_ONLY_TOOLS and not system_config.read_only_tools_enabled:
            return "Herramienta read-only bloqueada por ACU_READ_ONLY_TOOLS_ENABLED"

        if tool_name in self.WRITE_TOOLS and not system_config.write_tools_enabled:
            return "Herramienta write bloqueada por ACU_WRITE_TOOLS_ENABLED"

        if tool_name in self.EXTERNAL_TOOLS and not system_config.external_tools_enabled:
            return "Herramienta externa bloqueada por ACU_EXTERNAL_TOOLS_ENABLED"

        if tool_name == ToolType.PYTHON_SANDBOX and not system_config.python_sandbox_enabled:
            return "Python sandbox bloqueado por ACU_PYTHON_SANDBOX_ENABLED"

        if tool_name == ToolType.FILE_SYSTEM and not system_config.filesystem_write_enabled:
            return "Filesystem write bloqueado por ACU_FILESYSTEM_WRITE_ENABLED"

        if tool_name == ToolType.API_REST and not system_config.api_rest_enabled:
            return "API REST bloqueada por ACU_API_REST_ENABLED"

        if tool_name in {ToolType.WEB_READ, ToolType.WEB_SEARCH} and not system_config.web_tools_enabled:
            return "Web tools bloqueadas por ACU_WEB_TOOLS_ENABLED"

        explicitly_blocked = self._configured_tool_set(system_config.blocked_tools)
        if tool_name in explicitly_blocked:
            return "Herramienta bloqueada por politica ACU_BLOCKED_TOOLS"

        explicitly_allowed = self._configured_tool_set(system_config.allowed_tools)
        if explicitly_allowed and tool_name not in explicitly_allowed:
            return "Herramienta no incluida en ACU_ALLOWED_TOOLS"

        if system_config.safe_mode and tool_name in self.SAFE_MODE_BLOCKED_TOOLS:
            return "Herramienta bloqueada por ACU_SAFE_MODE"

        return None

    def _configured_tool_set(self, raw_value: str) -> set[ToolType]:
        """Parse a comma-separated tool allow/block list."""
        configured_tools: set[ToolType] = set()
        for item in str(raw_value or "").split(","):
            value = item.strip()
            if not value:
                continue
            try:
                configured_tools.add(ToolType(value))
            except ValueError:
                log.warning("Configuracion de herramienta ignorada por valor invalido")
        return configured_tools

    def _sanitize_audit_payload(self, payload: Any, key: str = "", depth: int = 0) -> Any:
        """Redact secrets and bound payload size before persisting audit data."""
        if system_config.audit_full_payloads and not system_config.audit_redact_secrets:
            return payload

        normalized_key = key.lower()
        if system_config.audit_redact_secrets and (
            normalized_key in self.AUDIT_SENSITIVE_KEYS or any(
            marker in normalized_key
            for marker in ("password", "secret", "token", "authorization")
            )
        ):
            return "[REDACTED]"

        if not system_config.audit_full_payloads and depth >= 4:
            return "[TRUNCATED]"

        if isinstance(payload, dict):
            return {
                str(item_key): self._sanitize_audit_payload(
                    item_value,
                    key=str(item_key),
                    depth=depth + 1,
                )
                for item_key, item_value in payload.items()
            }

        if isinstance(payload, list):
            if system_config.audit_full_payloads:
                return [
                    self._sanitize_audit_payload(item, key=key, depth=depth + 1)
                    for item in payload
                ]
            return [
                self._sanitize_audit_payload(item, key=key, depth=depth + 1)
                for item in payload[:20]
            ]

        if isinstance(payload, str):
            if system_config.audit_full_payloads:
                return payload
            return payload if len(payload) <= 500 else f"{payload[:500]}...[TRUNCATED]"

        return payload

    async def _execute_sql_read(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute SQL read query.

        Tool signature: ejecutar_sql_lectura(query_sql: str)
        """
        query = str(parameters.get("query_sql", "")).strip()
        if not query:
            return {"success": False, "error": "Parametro 'query_sql' requerido"}

        log.debug(f"SQL Query: {query[:200]}...")
        return self.db_connector.execute_read_query(query)

    async def _buscar_documentos(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search project documents using optional vector search and lexical fallback.

        Tool signature: buscar_documentos(consulta_semantica: str, top_k: int = 5)
        """
        query = str(parameters.get("consulta_semantica", "")).strip()
        top_k = self._safe_top_k(parameters.get("top_k", 5))

        if not query:
            return {
                "success": False,
                "error": "Parametro 'consulta_semantica' requerido",
            }

        if not self._document_index:
            self._document_index = self._build_document_index()

        if not self._document_index:
            return {
                "success": False,
                "error": "No se encontraron documentos indexables en el proyecto.",
            }

        vector_results = self._search_documents_vector(query, top_k)
        if vector_results is not None:
            log.debug(
                f"Busqueda vectorial documental '{query}' -> "
                f"{len(vector_results)} resultados"
            )
            return {"success": True, "data": vector_results}

        search_terms = self._tokenize(query)
        ranked_results = []
        for document in self._document_index:
            score = self._score_document(document, query, search_terms)
            if score <= 0:
                continue

            snippet = self._extract_snippet(document["content"], search_terms)
            ranked_results.append(
                {
                    "document": snippet,
                    "similarity": round(
                        min(score / max(len(search_terms) + 2, 3), 1.0), 3
                    ),
                    "metadata": {
                        "source": document["source"],
                        "section": document["section"],
                        "search_type": "lexical_project_search",
                    },
                    "_score": score,
                }
            )

        ranked_results.sort(
            key=lambda item: float(str(item.get("_score", 0))), reverse=True
        )
        top_results = ranked_results[:top_k]

        for item in top_results:
            item.pop("_score", None)

        log.debug(f"Busqueda documental '{query}' -> {len(top_results)} resultados")
        return {"success": True, "data": top_results}

    async def _buscar_contexto_braincore(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Search BrainCore agentic memory.

        Tool signature: buscar_contexto_braincore(consulta: str, top_k: int = 5)
        Optional filters: domain, source_type
        """
        query = self._extract_first_string(
            parameters,
            ["consulta", "query", "consulta_semantica"],
        )
        top_k = self._safe_top_k(parameters.get("top_k", 5))
        domain = str(parameters.get("domain", "")).strip() or None
        source_type = str(parameters.get("source_type", "")).strip() or None

        if not query:
            return {
                "success": False,
                "error": "Parametro 'consulta' requerido",
            }

        result = self.braincore_manager.search_context(
            query=query,
            domain=domain,
            source_type=source_type,
            top_k=top_k,
        )
        if not result.get("success"):
            return result
        return {"success": True, "data": result.get("data", [])}

    def _search_documents_vector(
        self,
        query: str,
        top_k: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search indexed documents with ChromaDB when vector search is enabled.

        Returns None when vector search is disabled or unavailable, allowing the
        caller to use the lexical implementation as a deterministic fallback.
        """
        if not self.vector_search_enabled:
            return None

        if self.vector_config.engine.lower() != "chromadb":
            log.warning(
                f"Motor vectorial no soportado: {self.vector_config.engine}. "
                "Usando busqueda textual."
            )
            self.vector_search_enabled = False
            return None

        try:
            collection = self._get_vector_collection()
            if collection is None:
                return None

            query_result = collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            log.warning(f"Busqueda vectorial no disponible, usando textual: {exc}")
            self.vector_search_enabled = False
            return None

        documents = (query_result.get("documents") or [[]])[0]
        metadatas = (query_result.get("metadatas") or [[]])[0]
        distances = (query_result.get("distances") or [[]])[0]

        results: List[Dict[str, Any]] = []
        for index, document in enumerate(documents):
            if not document:
                continue

            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            similarity = self._distance_to_similarity(distance)
            results.append(
                {
                    "document": self._trim_document(document),
                    "similarity": similarity,
                    "metadata": {
                        "source": metadata.get("source", "unknown"),
                        "section": metadata.get("section", "Documento"),
                        "search_type": "vector_chromadb",
                    },
                }
            )

        return results

    def _get_vector_collection(self):
        """Create or reuse a ChromaDB collection containing project documents."""
        if self._vector_collection is not None:
            return self._vector_collection

        try:
            import chromadb
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction,
            )
        except ImportError as exc:
            log.warning(f"Dependencias vectoriales no instaladas: {exc}")
            self.vector_search_enabled = False
            return None

        persist_directory = Path(self.vector_config.persist_directory)
        if not persist_directory.is_absolute():
            persist_directory = self.project_root / persist_directory

        embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=self.vector_config.embedding_model
        )
        client = chromadb.PersistentClient(path=str(persist_directory))
        collection = client.get_or_create_collection(
            name=self.VECTOR_COLLECTION_NAME,
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

        documents = [document["content"] for document in self._document_index]
        metadatas = [
            {
                "source": document["source"],
                "section": document["section"],
            }
            for document in self._document_index
        ]
        ids = [
            f"doc-{index}-{self._stable_document_id(document)}"
            for index, document in enumerate(self._document_index)
        ]

        self._clear_vector_collection(collection)
        if documents:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        self._vector_collection = collection
        return collection

    def _clear_vector_collection(self, collection) -> None:
        """Remove stale chunks before refreshing the persisted vector index."""
        try:
            existing_ids = collection.get().get("ids", [])
            if existing_ids:
                collection.delete(ids=existing_ids)
        except Exception as exc:
            log.warning(f"No se pudo limpiar el indice vectorial previo: {exc}")

    def _stable_document_id(self, document: Dict[str, str]) -> str:
        """Build a Chroma-safe deterministic id fragment for a document chunk."""
        raw_id = f"{document['source']}::{document['section']}"
        return re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw_id).strip("-")[:120] or "chunk"

    def _distance_to_similarity(self, distance: Any) -> float:
        """Convert Chroma cosine distance to a bounded similarity score."""
        if distance is None:
            return 1.0
        try:
            score = 1.0 - float(distance)
        except (TypeError, ValueError):
            return 0.0
        return round(min(max(score, 0.0), 1.0), 3)

    def _trim_document(self, document: str, max_chars: int = 360) -> str:
        """Keep vector results compact and consistent with lexical snippets."""
        collapsed = re.sub(r"\s+", " ", document).strip()
        if len(collapsed) <= max_chars:
            return collapsed
        return collapsed[:max_chars].rstrip() + "..."

    async def _registrar_leccion(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a learned lesson in evolutionary memory.

        Tool signature: registrar_leccion(categoria_sugerida: str, descripcion_regla: str)
        """
        categoria = str(parameters.get("categoria_sugerida", "")).strip()
        descripcion = str(parameters.get("descripcion_regla", "")).strip()
        relevancia = self._safe_relevancia(parameters.get("relevancia", 1))

        if not categoria or not descripcion:
            return {
                "success": False,
                "error": "Parametros 'categoria_sugerida' y 'descripcion_regla' requeridos",
            }

        result = self.write_connector.register_lesson(
            categoria=categoria,
            descripcion=descripcion,
            relevancia=relevancia,
        )
        if result.get("success"):
            log.info(f"Leccion registrada - Categoria: {categoria}")
        return result

    async def _consultar_lecciones_aprendidas(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Query learned lessons from evolutionary memory.

        Tool signature: consultar_lecciones_aprendidas(terminos_busqueda: str)
        """
        terminos = str(parameters.get("terminos_busqueda", "")).strip()
        limit = self._safe_top_k(parameters.get("top_k", 5))

        if not terminos:
            return {
                "success": False,
                "error": "Parametro 'terminos_busqueda' requerido",
            }

        result = self.db_connector.query_lessons(terminos=terminos, limit=limit)
        if result.get("success") and self.write_connector.is_connected():
            lesson_ids = [
                lesson.get("id")
                for lesson in result.get("data", [])
                if lesson.get("id") is not None
            ]
            self.write_connector.increment_lesson_usage(lesson_ids)
        return result

    async def _leer_pagina_web(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lee y extrae contenido de una URL web.

        Tool signature: leer_pagina_web(url: str)
        """
        url = str(parameters.get("url", "")).strip()
        if not url:
            return {"success": False, "error": "Parametro 'url' requerido"}

        try:
            log.info(f"Leyendo URL: {url}")
            headers = {
                "User-Agent": "ACU-Agent/1.0 (WebScraperTool)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            # Timeout de 10 segundos para no bloquear el Agente
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Extraer contenido con BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # Eliminar scripts, estilos, head, nav, footer para limpiar ruido
            for tag in soup(
                ["script", "style", "head", "nav", "footer", "iframe", "noscript"]
            ):
                tag.decompose()

            # Convertir HTML residual a Markdown para que sea optimo para el LLM
            markdown_content = markdownify.markdownify(
                str(soup), heading_style="ATX"
            ).strip()

            # Limitar a ~10000 caracteres para no desbordar contexto
            content_limited = markdown_content[:10000]
            if len(markdown_content) > 10000:
                content_limited += "\n...[Contenido truncado por longitud]"

            return {"success": True, "data": {"url": url, "content": content_limited}}

        except requests.exceptions.RequestException as exc:
            log.warning(f"Error descargando web {url}: {exc}")
            return {"success": False, "error": f"Fallo al conectar con la URL: {exc}"}
        except Exception as exc:
            log.error(f"Error parseando web {url}: {exc}")
            return {"success": False, "error": f"Fallo parseando la URL: {exc}"}

    async def _buscar_web(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Realiza una busqueda en internet (DuckDuckGo) para obtener informacion en tiempo real.

        Tool signature: busqueda_web(query: str, max_results: int = 5)
        """
        query = str(parameters.get("query", "")).strip()
        max_results = int(parameters.get("max_results", 5))

        if not query:
            return {"success": False, "error": "Parametro 'query' requerido"}

        try:
            from duckduckgo_search import DDGS

            log.info(f"Buscando en web: '{query}'")

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return {
                    "success": True,
                    "data": "No se encontraron resultados para la busqueda.",
                }

            formatted_results = []
            for i, res in enumerate(results):
                title = res.get("title", "Sin titulo")
                body = res.get("body", "Sin descripcion")
                href = res.get("href", "#")
                formatted_results.append(f"{i + 1}. **{title}**\n{body}\n*URL:* {href}")

            final_text = "\n\n".join(formatted_results)
            return {"success": True, "data": final_text}

        except Exception as exc:
            log.error(f"Error en busqueda web '{query}': {exc}")
            return {"success": False, "error": f"Fallo en motor de busqueda: {exc}"}

    async def _peticion_api_rest(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta una peticion HTTP REST.

        Tool signature: peticion_api_rest(method: str, url: str, headers: dict = {}, json_data: dict = {})
        """
        url = str(parameters.get("url", "")).strip()
        method = str(parameters.get("method", "GET")).upper()
        custom_headers = parameters.get("headers", {})
        json_data = parameters.get("json_data", None)

        if not url:
            return {"success": False, "error": "Parametro 'url' requerido"}

        if method not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            return {"success": False, "error": f"Metodo HTTP no soportado: {method}"}

        try:
            log.info(f"Peticion API [{method}] -> {url}")
            headers = {
                "User-Agent": "ACU-Agent/1.0 (APIClientTool)",
                "Accept": "application/json, */*",
            }
            if isinstance(custom_headers, dict):
                headers.update(custom_headers)

            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data if json_data and method != "GET" else None,
                timeout=15,
            )

            status_code = response.status_code

            try:
                response_data = response.json()
            except ValueError:
                response_data = response.text[:5000]  # Limitar texto si no es JSON

            # Tratar como exito si es 2xx o 3xx
            is_success = 200 <= status_code < 400

            return {
                "success": is_success,
                "data": {"status_code": status_code, "response": response_data},
                "error": f"HTTP {status_code}" if not is_success else None,
                "audit_payload": {
                    "request_url": url,
                    "request_method": method,
                    "request_headers": headers,
                    "request_body": json_data,
                    "response_body_full": response.text,
                },
            }

        except requests.exceptions.RequestException as exc:
            log.warning(f"Error en peticion API [{method}] {url}: {exc}")
            return {"success": False, "error": f"Error de red/conexion: {exc}"}
        except Exception as exc:
            log.error(f"Error critico en peticion API: {exc}")
            return {"success": False, "error": f"Error interno en herramienta: {exc}"}

    async def _gestionar_archivos(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Herramienta de gestion de archivos locales (Sandbox).

        Tool signature: gestionar_archivos(action: str, path: str, content: str = "")
        """
        import os

        action = str(parameters.get("action", "")).lower()
        file_path = str(parameters.get("path", "")).strip()
        content = parameters.get("content", "")

        if not action or not file_path:
            return {
                "success": False,
                "error": "Parametros 'action' y 'path' son requeridos",
            }

        # Configurar un Sandbox seguro (acu_workspace)
        base_dir = Path(os.getcwd()) / "acu_workspace"
        base_dir.mkdir(exist_ok=True)

        # Resolver la ruta de forma segura para evitar Path Traversal (../../)
        try:
            target_path = (base_dir / file_path).resolve()
            if not str(target_path).startswith(str(base_dir)):
                return {
                    "success": False,
                    "error": "Intento de violacion de seguridad (Path Traversal). Solo puedes acceder a archivos dentro de 'acu_workspace'.",
                }
        except Exception as exc:
            return {"success": False, "error": f"Ruta invalida: {exc}"}

        try:
            if action == "read":
                if not target_path.exists():
                    return {
                        "success": False,
                        "error": f"El archivo no existe: {file_path}",
                    }
                if target_path.is_dir():
                    return {
                        "success": False,
                        "error": "La ruta es un directorio, usa 'list' para ver su contenido.",
                    }

                file_content = target_path.read_text(encoding="utf-8")
                # Limitar lectura para evitar romper el contexto
                if len(file_content) > 15000:
                    file_content = (
                        file_content[:15000]
                        + "\n...[Contenido truncado por limite de 15,000 caracteres]"
                    )

                return {
                    "success": True,
                    "data": {
                        "action": action,
                        "path": file_path,
                        "content": file_content,
                    },
                }

            elif action == "write":
                if target_path.is_dir():
                    return {
                        "success": False,
                        "error": "La ruta destino es un directorio.",
                    }

                # Crear directorios padres si no existen
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(str(content), encoding="utf-8")
                return {
                    "success": True,
                    "data": {
                        "action": action,
                        "path": file_path,
                        "message": "Archivo escrito correctamente",
                        "bytes": len(str(content)),
                    },
                    "audit_payload": {"written_content_full": str(content)},
                }

            elif action == "list":
                if not target_path.exists():
                    return {
                        "success": False,
                        "error": f"El directorio no existe: {file_path}",
                    }
                if not target_path.is_dir():
                    return {
                        "success": False,
                        "error": "La ruta es un archivo, usa 'read' para ver su contenido.",
                    }

                items = []
                for item in target_path.iterdir():
                    items.append(
                        {
                            "name": item.name,
                            "type": "directory" if item.is_dir() else "file",
                            "size": item.stat().st_size if item.is_file() else 0,
                        }
                    )
                return {
                    "success": True,
                    "data": {"action": action, "path": file_path, "items": items},
                }

            elif action == "delete":
                if not target_path.exists():
                    return {
                        "success": False,
                        "error": f"El archivo o directorio no existe: {file_path}",
                    }
                if target_path.is_dir():
                    import shutil

                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
                return {
                    "success": True,
                    "data": {
                        "action": action,
                        "path": file_path,
                        "message": "Eliminado correctamente",
                    },
                    "audit_payload": {"deleted_path": str(target_path)},
                }

            else:
                return {
                    "success": False,
                    "error": f"Accion '{action}' no soportada. Usa 'read', 'write', 'list' o 'delete'.",
                }

        except Exception as exc:
            log.error(f"Error gestionando archivo [{action}] {file_path}: {exc}")
            return {"success": False, "error": f"Error del sistema de archivos: {exc}"}

    async def _ejecutar_python(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta codigo Python en un sandbox temporal para calculos o analisis.

        Tool signature: ejecutar_python(code: str)
        """
        import os
        import subprocess
        import tempfile
        import sys

        code = str(parameters.get("code", "")).strip()
        if not code:
            return {"success": False, "error": "Parametro 'code' es requerido"}

        log.info("Ejecutando script Python en Sandbox...")

        # Inyectar el entorno acu_workspace al sys.path para que el script pueda leer archivos del sandbox
        workspace_dir = str(Path(os.getcwd()) / "acu_workspace")

        sandbox_code = f"""import sys
import os
sys.path.insert(0, r"{workspace_dir}")
os.chdir(r"{workspace_dir}")

# --- User Code ---
{code}
"""

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(sandbox_code)
                script_path = f.name

            # Ejecutar con un timeout de 15 segundos para evitar bucles infinitos
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=15,
            )

            # Limpiar script temporal
            os.remove(script_path)

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            # Limitar salida para no saturar memoria
            if len(stdout) > 5000:
                stdout = stdout[:5000] + "\n...[stdout truncado]"
            if len(stderr) > 5000:
                stderr = stderr[:5000] + "\n...[stderr truncado]"

            if result.returncode == 0:
                return {
                    "success": True,
                    "data": {"stdout": stdout, "stderr": stderr if stderr else None},
                    "audit_payload": {
                        "script_code": code,
                        "stdout_full": result.stdout,
                        "stderr_full": result.stderr,
                    },
                }
            else:
                return {
                    "success": False,
                    "error": f"Error de ejecucion (Return Code {result.returncode})",
                    "stdout": stdout,
                    "stderr": stderr,
                    "audit_payload": {
                        "script_code": code,
                        "stdout_full": result.stdout,
                        "stderr_full": result.stderr,
                    },
                }

        except subprocess.TimeoutExpired:
            if "script_path" in locals() and os.path.exists(script_path):
                os.remove(script_path)
            return {
                "success": False,
                "error": "El script excedio el tiempo maximo de ejecucion (15 segundos).",
            }
        except Exception as exc:
            error_msg = f"Error ejecutando python sandbox: {exc}"
            log.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _delegar_tarea(
        self, parameters: Dict[str, Any], session_id: str
    ) -> Dict[str, Any]:
        """
        Instancia un sub-agente (Worker) con un rol especifico para ejecutar una tarea compleja.

        Tool signature: delegar_tarea(worker_persona: str, task_description: str)
        """
        worker_persona = str(parameters.get("worker_persona", "default")).strip()
        task_description = str(parameters.get("task_description", "")).strip()

        if not task_description:
            return {"success": False, "error": "Parametro 'task_description' requerido"}

        try:
            log.info(f"Delegando tarea a sub-agente [{worker_persona}]...")

            # Lazy import to avoid circular dependency
            from src.agent.agent_loop import ACUAgent

            # The worker gets its own isolated conversation history, but we link it via name.
            # They share the shared_memory using the parent's session_id, so the worker must be passed the parent's session id?
            # Wait, if we want them to share shared_memory, we should probably pass the SAME session_id to the worker,
            # or the worker uses its own session_id but we manually pass shared_memory...
            # Actually, the simplest way to share shared memory is if they all use the SAME session_id,
            # BUT wait, conversation history is tied to session_id! We don't want the worker to inherit the user conversation history and mess it up.
            # So worker gets a sub-session id. We will let the tools handle shared memory by passing the parent session id explicitly.
            # But the worker doesn't know its parent session id.
            # For now, let's just create a sub-session id for the worker.
            worker_session_id = (
                f"{session_id}_worker_{worker_persona}_{uuid.uuid4().hex[:4]}"
            )

            worker_agent = ACUAgent(domain="worker", persona=worker_persona)
            initialized = await worker_agent.initialize(session_id=worker_session_id)
            if not initialized:
                return {
                    "success": False,
                    "error": "No se pudo inicializar el sub-agente delegado",
                }

            # To avoid the worker taking too long, we might want to limit iterations,
            # but ACUAgent already respects config.max_iterations.
            worker_result = await worker_agent.process_user_message(task_description)

            # LLM-as-a-Judge: Evaluate if the worker solved the task
            from src.llm.ollama_client import get_ollama_client

            ollama_client = get_ollama_client()
            judge_prompt = f"""
Eres un sub-agente Juez estricto de Aseguramiento de Calidad.
Tarea delegada: {task_description}
Resultado del Worker ({worker_persona}): {worker_result}

Evalua si el resultado cumple de forma satisfactoria y completa la tarea delegada.
Responde unicamente con 'PASS' si es correcto, o 'FAIL: [motivo de la falla y que falta]' si no es suficiente.
"""
            judge_eval = ollama_client.generate_response(
                system_prompt="Eres un Juez Imparcial y riguroso. Tu objetivo es la calidad del enjambre.",
                user_message=judge_prompt,
                conversation_history=[],
                temperature=0.0,
            )

            judge_eval_text = str(judge_eval or "")
            is_pass = judge_eval_text.upper().startswith("PASS")
            log.info(
                f"Evaluacion Juez sobre Worker [{worker_persona}]: {'PASS' if is_pass else 'FAIL'}"
            )

            if not is_pass:
                # Force Auto-Correction (1 attempt for simplicity)
                failure_reason = judge_eval_text.replace("FAIL:", "").strip()
                correction_prompt = f"Tu respuesta anterior fallo la evaluacion de calidad. Motivo: {failure_reason}\nPor favor, corrige y completa la tarea considerando este feedback."
                log.info(f"Forzando auto-correccion en Worker [{worker_persona}]...")
                worker_result = await worker_agent.process_user_message(
                    correction_prompt
                )

            log.info(
                f"Sub-agente [{worker_persona}] finalizo su tarea (Evaluacion completada)."
            )

            return {
                "success": True,
                "data": {
                    "worker_persona": worker_persona,
                    "worker_session_id": worker_session_id,
                    "result": worker_result,
                    "judge_approved": is_pass,
                },
            }
        except Exception as exc:
            log.error(f"Error en delegacion de tarea a {worker_persona}: {exc}")
            return {"success": False, "error": f"Fallo al delegar tarea: {exc}"}

    async def _escribir_memoria_compartida(
        self, parameters: Dict[str, Any], session_id: str
    ) -> Dict[str, Any]:
        """
        Guarda un valor en la memoria compartida del enjambre.
        """
        key = str(parameters.get("key", "")).strip()
        value = str(parameters.get("value", "")).strip()

        if not key or not value:
            return {"success": False, "error": "Parametros 'key' y 'value' requeridos"}

        root_session_id = session_id.split("_worker_")[0]
        success = await redis_manager.set_shared_memory(root_session_id, key, value)

        if success:
            log.info(f"Escritura en memoria compartida exitosa: [{key}]")
            return {
                "success": True,
                "data": f"Valor guardado correctamente en la clave '{key}'.",
            }
        else:
            return {
                "success": False,
                "error": "Fallo al conectar con Redis para escribir.",
            }

    async def _leer_memoria_compartida(
        self, parameters: Dict[str, Any], session_id: str
    ) -> Dict[str, Any]:
        """
        Lee un valor de la memoria compartida del enjambre.
        """
        key = str(parameters.get("key", "")).strip()

        if not key:
            return {"success": False, "error": "Parametro 'key' requerido"}

        root_session_id = session_id.split("_worker_")[0]
        value = await redis_manager.get_shared_memory(root_session_id, key)

        if value is not None:
            return {"success": True, "data": {"key": key, "value": value}}
        else:
            return {
                "success": True,
                "data": f"No se encontro ningun valor para la clave '{key}'.",
            }

    def _build_document_index(self) -> List[Dict[str, str]]:
        """Index searchable project documents and split them into sections."""
        indexed_documents: List[Dict[str, str]] = []

        for path in sorted(self.project_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self.SEARCHABLE_EXTENSIONS:
                continue
            if any(part in self.SKIP_DIRECTORIES for part in path.parts):
                continue

            try:
                raw_content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                log.warning(f"No se pudo leer documento {path}: {exc}")
                continue

            for section in self._split_into_sections(raw_content):
                if len(section["content"]) < 40:
                    continue
                indexed_documents.append(
                    {
                        "source": str(path.relative_to(self.project_root)),
                        "section": section["title"],
                        "content": section["content"],
                    }
                )

        log.info(f"Indice documental construido con {len(indexed_documents)} secciones")
        return indexed_documents

    def _split_into_sections(self, content: str) -> List[Dict[str, str]]:
        """Split document content by markdown headings or blank-line chunks."""
        sections: List[Dict[str, str]] = []
        current_title = "Documento"
        current_lines: List[str] = []

        def flush_section():
            text = "\n".join(current_lines).strip()
            if not text:
                return
            for chunk in self._chunk_text(text):
                sections.append({"title": current_title, "content": chunk})

        for line in content.splitlines():
            heading_match = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", line)
            if heading_match:
                flush_section()
                current_title = heading_match.group(2).strip() or "Documento"
                current_lines = []
                continue
            current_lines.append(line)

        flush_section()

        if not sections and content.strip():
            for chunk in self._chunk_text(content.strip()):
                sections.append({"title": "Documento", "content": chunk})

        return sections

    def _chunk_text(self, text: str, max_chars: int = 1400) -> List[str]:
        """Split long sections into smaller chunks preserving paragraph boundaries."""
        paragraphs = [
            part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()
        ]
        if not paragraphs:
            return []

        chunks: List[str] = []
        current_chunk = ""
        for paragraph in paragraphs:
            candidate = (
                paragraph if not current_chunk else f"{current_chunk}\n\n{paragraph}"
            )
            if len(candidate) <= max_chars:
                current_chunk = candidate
                continue

            if current_chunk:
                chunks.append(current_chunk)
            if len(paragraph) <= max_chars:
                current_chunk = paragraph
            else:
                for start in range(0, len(paragraph), max_chars):
                    chunks.append(paragraph[start : start + max_chars])
                current_chunk = ""

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _score_document(
        self,
        document: Dict[str, str],
        query: str,
        search_terms: List[str],
    ) -> float:
        """Rank a document chunk based on phrase and token overlap."""
        haystack = f"{document['section']} {document['content']}".lower()
        if not haystack.strip():
            return 0.0

        normalized_query = query.lower()
        phrase_bonus = 3.0 if normalized_query in haystack else 0.0
        unique_hits = sum(1.0 for term in search_terms if term in haystack)
        frequency_bonus = sum(haystack.count(term) for term in search_terms) * 0.2
        section_bonus = sum(
            1.5 for term in search_terms if term in document["section"].lower()
        )

        return phrase_bonus + unique_hits + frequency_bonus + section_bonus

    def _extract_snippet(
        self,
        content: str,
        search_terms: List[str],
        radius: int = 160,
    ) -> str:
        """Extract a compact snippet centered around the earliest term match."""
        collapsed = re.sub(r"\s+", " ", content).strip()
        lower_content = collapsed.lower()

        positions = [
            lower_content.find(term)
            for term in search_terms
            if term and lower_content.find(term) != -1
        ]
        if not positions:
            return collapsed[: min(len(collapsed), 320)]

        start = max(min(positions) - radius, 0)
        end = min(start + 320, len(collapsed))
        snippet = collapsed[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(collapsed):
            snippet = snippet + "..."
        return snippet

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase alphanumeric terms."""
        tokens = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
        deduped_tokens: List[str] = []
        for token in tokens:
            if token not in deduped_tokens:
                deduped_tokens.append(token)
        return deduped_tokens

    def _extract_first_string(
        self,
        parameters: Dict[str, Any],
        keys: List[str],
    ) -> str:
        """Return the first non-empty string value for the provided keys."""
        for key in keys:
            value = str(parameters.get(key, "")).strip()
            if value:
                return value
        return ""

    def _safe_top_k(self, value: Any) -> int:
        """Normalize top_k values to a small positive integer."""
        try:
            top_k = int(value)
        except (TypeError, ValueError):
            return 5
        return min(max(top_k, 1), 10)

    def _safe_relevancia(self, value: Any) -> int:
        """Normalize relevancia to a bounded integer."""
        try:
            relevancia = int(value)
        except (TypeError, ValueError):
            return 1
        return min(max(relevancia, 1), 10)

    def get_execution_log(self) -> List[ToolResult]:
        """Get log of all executed tools."""
        return self.execution_log

    def clear_execution_log(self):
        """Clear execution log."""
        self.execution_log = []


_tools_manager = None


def get_tools_manager() -> ToolsManager:
    """Get or create singleton tools manager."""
    global _tools_manager
    if _tools_manager is None:
        _tools_manager = ToolsManager()
    return _tools_manager
