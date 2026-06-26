"""BrainCore orchestration layer."""

from typing import Any, Dict, List, Optional

from src.braincore.ingestion import BrainCoreIngestion
from src.braincore.vector_store import BrainCoreVectorStore
from src.memory.mysql_manager import get_db_connector


class BrainCoreManager:
    """Coordinates BrainCore memory operations."""

    def __init__(self, db_connector=None, ingestion=None, vector_store=None):
        self.db_connector = db_connector or get_db_connector(use_read_only=False)
        self.ingestion = ingestion or BrainCoreIngestion()
        self.vector_store = vector_store or BrainCoreVectorStore()

    def register_decision(
        self,
        title: str,
        context: str,
        decision: str,
        alternatives: Optional[List[str]] = None,
        impact: str = "",
        domain: str = "generic",
        status: str = "accepted",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register an architectural decision in BrainCore."""
        return self.db_connector.register_brain_decision(
            title=title.strip(),
            context=context.strip(),
            decision=decision.strip(),
            alternatives=alternatives or [],
            impact=impact.strip(),
            domain=domain.strip() or "generic",
            status=status.strip() or "accepted",
            tags=tags or [],
        )

    def list_decisions(
        self,
        search: str = "",
        domain: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List BrainCore architectural decisions."""
        return self.db_connector.list_brain_decisions(
            search=search.strip(),
            domain=domain.strip() if domain else None,
            status=status.strip() if status else None,
            limit=limit,
        )

    def list_sources(
        self,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List BrainCore indexed sources."""
        return self.db_connector.list_brain_sources(
            domain=domain.strip() if domain else None,
            source_type=source_type.strip() if source_type else None,
            status=status.strip() if status else None,
            limit=limit,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Return aggregate BrainCore operational metrics."""
        return self.db_connector.get_brain_metrics()

    def get_vector_status(self) -> Dict[str, Any]:
        """Return vector backend runtime status."""
        return {"success": True, "data": self.vector_store.get_status()}

    def export_domain(
        self,
        domain: str,
        include_chunks: bool = True,
    ) -> Dict[str, Any]:
        """Export BrainCore decisions, sources and chunks for one domain."""
        normalized_domain = domain.strip()
        if not normalized_domain:
            return {"success": False, "error": "domain es requerido"}
        return self.db_connector.export_brain_domain(
            domain=normalized_domain,
            include_chunks=include_chunks,
        )

    def delete_domain(
        self,
        domain: str,
        delete_decisions: bool = False,
    ) -> Dict[str, Any]:
        """Delete all BrainCore sources for one domain and optional decisions."""
        normalized_domain = domain.strip()
        if not normalized_domain:
            return {"success": False, "error": "domain es requerido"}

        result = self.db_connector.delete_brain_domain(
            domain=normalized_domain,
            delete_decisions=delete_decisions,
        )
        if not result.get("success"):
            return result

        data = result.get("data", {})
        vector_sources_deleted = 0
        for source_path in data.get("deleted_source_paths", []):
            if self.vector_store.delete_source(source_path):
                vector_sources_deleted += 1
        data["vector_sources_deleted"] = vector_sources_deleted
        return {"success": True, "data": data}

    def delete_source(self, source_id: int) -> Dict[str, Any]:
        """Delete a BrainCore source from structured and vector storage."""
        result = self.db_connector.delete_brain_source(source_id=source_id)
        if not result.get("success"):
            return result

        source = result.get("data", {})
        vector_deleted = self.vector_store.delete_source(source.get("source_path", ""))
        return {
            "success": True,
            "data": {
                "source_id": source.get("id"),
                "source_path": source.get("source_path", ""),
                "deleted": True,
                "vector_deleted": vector_deleted,
            },
        }

    def ingest_path(
        self,
        path: str,
        source_type: str = "auto",
        domain: str = "generic",
    ) -> Dict[str, Any]:
        """Ingest local files/directories into BrainCore metadata storage."""
        collected = self.ingestion.collect_documents(
            path=path,
            source_type=source_type.strip() or "auto",
            domain=domain.strip() or "generic",
        )
        if not collected.get("success"):
            return collected

        documents = collected["data"]["documents"]
        sources_indexed = 0
        chunks_indexed = 0
        skipped_sources = 0
        errors = []

        for document in documents:
            result = self.db_connector.upsert_brain_source(
                source_path=document["source_path"],
                source_type=document["source_type"],
                content_hash=document["content_hash"],
                metadata=document["metadata"],
                chunks=document["chunks"],
            )
            if result.get("success"):
                sources_indexed += 1
                chunks_indexed += int(result.get("data", {}).get("chunks_indexed", 0))
            else:
                skipped_sources += 1
                errors.append(
                    {
                        "source_path": document["source_path"],
                        "error": result.get("error", "Error desconocido"),
                    }
                )

        vector_indexed = self.vector_store.upsert_documents(documents)
        return {
            "success": not errors,
            "data": {
                "path": collected["data"]["path"],
                "files_found": collected["data"]["files_found"],
                "sources_indexed": sources_indexed,
                "chunks_indexed": chunks_indexed,
                "vector_indexed": vector_indexed,
                "skipped_sources": skipped_sources,
                "errors": errors,
            },
            "error": "; ".join(error["error"] for error in errors) if errors else None,
        }

    def search_context(
        self,
        query: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Search BrainCore context from ingested source chunks."""
        normalized_query = query.strip()
        if not normalized_query:
            return {"success": False, "error": "query es requerido"}

        normalized_domain = domain.strip() if domain else None
        normalized_source_type = source_type.strip() if source_type else None
        normalized_top_k = min(max(int(top_k), 1), 20)
        vector_results = self.vector_store.search(
            query=normalized_query,
            domain=normalized_domain,
            source_type=normalized_source_type,
            top_k=normalized_top_k,
        )
        if vector_results is not None:
            return {"success": True, "data": vector_results}

        return self.db_connector.search_brain_chunks(
            query_text=normalized_query,
            domain=normalized_domain,
            source_type=normalized_source_type,
            limit=normalized_top_k,
        )


_braincore_manager = None


def get_braincore_manager() -> BrainCoreManager:
    """Get or create the BrainCore manager singleton."""
    global _braincore_manager
    if _braincore_manager is None:
        _braincore_manager = BrainCoreManager()
    return _braincore_manager
