import shutil
from pathlib import Path

from src.braincore.manager import BrainCoreManager


class DummyBrainDB:
    def __init__(self):
        self.register_payload = None
        self.list_payload = None
        self.sources_payload = None
        self.deleted_source_id = None
        self.export_payload = None
        self.deleted_domain_payload = None
        self.ingested_sources = []
        self.search_payload = None

    def register_brain_decision(
        self,
        title,
        context,
        decision,
        alternatives,
        impact,
        domain,
        status,
        tags,
    ):
        self.register_payload = {
            "title": title,
            "context": context,
            "decision": decision,
            "alternatives": alternatives,
            "impact": impact,
            "domain": domain,
            "status": status,
            "tags": tags,
        }
        return {"success": True, "data": {"id": 1, **self.register_payload}}

    def list_brain_decisions(self, search="", domain=None, status=None, limit=20):
        self.list_payload = {
            "search": search,
            "domain": domain,
            "status": status,
            "limit": limit,
        }
        return {"success": True, "data": []}

    def upsert_brain_source(
        self,
        source_path,
        source_type,
        content_hash,
        metadata,
        chunks,
    ):
        self.ingested_sources.append(
            {
                "source_path": source_path,
                "source_type": source_type,
                "content_hash": content_hash,
                "metadata": metadata,
                "chunks": chunks,
            }
        )
        return {
            "success": True,
            "data": {
                "source_id": len(self.ingested_sources),
                "chunks_indexed": len(chunks),
            },
        }

    def list_brain_sources(
        self,
        domain=None,
        source_type=None,
        status=None,
        limit=20,
    ):
        self.sources_payload = {
            "domain": domain,
            "source_type": source_type,
            "status": status,
            "limit": limit,
        }
        return {"success": True, "data": []}

    def get_brain_metrics(self):
        return {
            "success": True,
            "data": {
                "decisions_count": 2,
                "sources_count": 3,
                "chunks_count": 12,
                "domains_count": 2,
                "last_indexed_at": "2026-05-14 10:00:00",
                "last_updated_at": "2026-05-14 10:05:00",
                "domains": [],
                "source_types": [],
            },
        }

    def export_brain_domain(self, domain, include_chunks=True):
        self.export_payload = {
            "domain": domain,
            "include_chunks": include_chunks,
        }
        return {
            "success": True,
            "data": {
                "domain": domain,
                "decisions_count": 1,
                "sources_count": 1,
                "chunks_count": 1 if include_chunks else 4,
                "decisions": [{"id": 7, "domain": domain}],
                "sources": [{"id": 3, "source_path": "wiki/api.md"}],
                "chunks": [{"id": 9}] if include_chunks else [],
            },
        }

    def delete_brain_domain(self, domain, delete_decisions=False):
        self.deleted_domain_payload = {
            "domain": domain,
            "delete_decisions": delete_decisions,
        }
        return {
            "success": True,
            "data": {
                "domain": domain,
                "sources_deleted": 2,
                "chunks_deleted": 8,
                "decisions_deleted": 1 if delete_decisions else 0,
                "vector_sources_deleted": 0,
                "deleted_source_paths": ["wiki/api.md", "wiki/ops.md"],
            },
        }

    def delete_brain_source(self, source_id):
        self.deleted_source_id = source_id
        return {
            "success": True,
            "data": {
                "id": source_id,
                "source_path": "wiki/api.md",
                "source_type": "markdown",
                "content_hash": "abc123",
                "metadata": {"domain": "acu"},
                "status": "indexed",
                "chunks_count": 0,
                "indexed_at": "2026-05-14 10:00:00",
                "updated_at": "2026-05-14 10:05:00",
            },
        }

    def search_brain_chunks(
        self,
        query_text,
        domain=None,
        source_type=None,
        limit=5,
    ):
        self.search_payload = {
            "query_text": query_text,
            "domain": domain,
            "source_type": source_type,
            "limit": limit,
        }
        return {"success": True, "data": [{"chunk_id": 1}]}


class DummyVectorStore:
    def __init__(self, search_results=None):
        self.upserted_documents = None
        self.search_payload = None
        self.deleted_source_path = None
        self.deleted_source_paths = []
        self.search_results = search_results

    def upsert_documents(self, documents):
        self.upserted_documents = documents
        return True

    def search(self, query, domain=None, source_type=None, top_k=5):
        self.search_payload = {
            "query": query,
            "domain": domain,
            "source_type": source_type,
            "top_k": top_k,
        }
        return self.search_results

    def delete_source(self, source_path):
        self.deleted_source_path = source_path
        self.deleted_source_paths.append(source_path)
        return True


def test_braincore_manager_registers_decision_with_defaults():
    db = DummyBrainDB()
    manager = BrainCoreManager(db_connector=db, vector_store=DummyVectorStore())

    result = manager.register_decision(
        title=" Usar FastAPI ",
        context=" API del core ",
        decision=" Exponer ACU via REST ",
    )

    assert result["success"] is True
    assert db.register_payload["title"] == "Usar FastAPI"
    assert db.register_payload["context"] == "API del core"
    assert db.register_payload["decision"] == "Exponer ACU via REST"
    assert db.register_payload["alternatives"] == []
    assert db.register_payload["domain"] == "generic"
    assert db.register_payload["status"] == "accepted"


def test_braincore_manager_lists_decisions_with_filters():
    db = DummyBrainDB()
    manager = BrainCoreManager(db_connector=db, vector_store=DummyVectorStore())

    result = manager.list_decisions(
        search=" rag ",
        domain=" acu ",
        status=" accepted ",
        limit=5,
    )

    assert result["success"] is True
    assert db.list_payload == {
        "search": "rag",
        "domain": "acu",
        "status": "accepted",
        "limit": 5,
    }


def test_braincore_manager_lists_sources_with_filters():
    db = DummyBrainDB()
    manager = BrainCoreManager(db_connector=db, vector_store=DummyVectorStore())

    result = manager.list_sources(
        domain=" acu ",
        source_type=" markdown ",
        status=" indexed ",
        limit=5,
    )

    assert result["success"] is True
    assert db.sources_payload == {
        "domain": "acu",
        "source_type": "markdown",
        "status": "indexed",
        "limit": 5,
    }


def test_braincore_manager_returns_metrics():
    db = DummyBrainDB()
    manager = BrainCoreManager(db_connector=db, vector_store=DummyVectorStore())

    result = manager.get_metrics()

    assert result["success"] is True
    assert result["data"]["sources_count"] == 3
    assert result["data"]["chunks_count"] == 12


def test_braincore_manager_exports_domain_snapshot():
    db = DummyBrainDB()
    manager = BrainCoreManager(db_connector=db, vector_store=DummyVectorStore())

    result = manager.export_domain(domain=" acu ", include_chunks=False)

    assert result["success"] is True
    assert db.export_payload == {"domain": "acu", "include_chunks": False}
    assert result["data"]["domain"] == "acu"
    assert result["data"]["chunks"] == []


def test_braincore_manager_deletes_domain_and_vector_records():
    db = DummyBrainDB()
    vector_store = DummyVectorStore()
    manager = BrainCoreManager(db_connector=db, vector_store=vector_store)

    result = manager.delete_domain(domain=" acu ", delete_decisions=True)

    assert result["success"] is True
    assert db.deleted_domain_payload == {
        "domain": "acu",
        "delete_decisions": True,
    }
    assert result["data"]["sources_deleted"] == 2
    assert result["data"]["decisions_deleted"] == 1
    assert result["data"]["vector_sources_deleted"] == 2
    assert vector_store.deleted_source_paths == ["wiki/api.md", "wiki/ops.md"]


def test_braincore_manager_deletes_source_and_vector_records():
    db = DummyBrainDB()
    vector_store = DummyVectorStore()
    manager = BrainCoreManager(db_connector=db, vector_store=vector_store)

    result = manager.delete_source(3)

    assert result == {
        "success": True,
        "data": {
            "source_id": 3,
            "source_path": "wiki/api.md",
            "deleted": True,
            "vector_deleted": True,
        },
    }
    assert db.deleted_source_id == 3
    assert vector_store.deleted_source_path == "wiki/api.md"


def test_braincore_manager_ingests_local_markdown_file():
    db = DummyBrainDB()
    vector_store = DummyVectorStore()
    manager = BrainCoreManager(db_connector=db, vector_store=vector_store)
    tmp_dir = Path("tests/.tmp_braincore")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        document = tmp_dir / "decision.md"
        document.write_text(
            "# Arquitectura\n\nUsaremos FastAPI como puente REST.\n\n"
            "## Impacto\n\nPermite clientes externos.",
            encoding="utf-8",
        )

        result = manager.ingest_path(str(document), domain="acu")

        assert result["success"] is True
        assert result["data"]["files_found"] == 1
        assert result["data"]["sources_indexed"] == 1
        assert result["data"]["chunks_indexed"] >= 1
        assert result["data"]["vector_indexed"] is True
        assert db.ingested_sources[0]["source_type"] == "markdown"
        assert db.ingested_sources[0]["metadata"]["domain"] == "acu"
        assert db.ingested_sources[0]["chunks"][0]["chunk_hash"]
        assert vector_store.upserted_documents[0]["source_type"] == "markdown"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_braincore_manager_reports_missing_ingest_path():
    manager = BrainCoreManager(
        db_connector=DummyBrainDB(),
        vector_store=DummyVectorStore(),
    )

    result = manager.ingest_path("ruta-inexistente")

    assert result["success"] is False
    assert "Ruta no encontrada" in result["error"]


def test_braincore_manager_searches_context_with_filters():
    db = DummyBrainDB()
    manager = BrainCoreManager(
        db_connector=db,
        vector_store=DummyVectorStore(search_results=None),
    )

    result = manager.search_context(
        query=" arquitectura fastapi ",
        domain=" acu ",
        source_type=" markdown ",
        top_k=3,
    )

    assert result["success"] is True
    assert db.search_payload == {
        "query_text": "arquitectura fastapi",
        "domain": "acu",
        "source_type": "markdown",
        "limit": 3,
    }


def test_braincore_manager_search_requires_query():
    manager = BrainCoreManager(
        db_connector=DummyBrainDB(),
        vector_store=DummyVectorStore(),
    )

    result = manager.search_context(query=" ")

    assert result["success"] is False
    assert "query" in result["error"]


def test_braincore_manager_prefers_vector_results_when_available():
    db = DummyBrainDB()
    vector_store = DummyVectorStore(search_results=[{"chunk_id": 99}])
    manager = BrainCoreManager(db_connector=db, vector_store=vector_store)

    result = manager.search_context(
        query="arquitectura fastapi",
        domain="acu",
        source_type="markdown",
        top_k=2,
    )

    assert result == {"success": True, "data": [{"chunk_id": 99}]}
    assert vector_store.search_payload == {
        "query": "arquitectura fastapi",
        "domain": "acu",
        "source_type": "markdown",
        "top_k": 2,
    }
    assert db.search_payload is None
