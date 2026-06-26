import shutil
from pathlib import Path
from typing import Any, Dict

import pytest

from src.braincore.vector_store import BrainCoreVectorStore
from src.config.settings import VectorDBConfig

pytestmark = pytest.mark.integration_vector


@pytest.fixture
def temp_vector_dir():
    """Provide a temporary directory for VectorDB index files."""
    test_dir = Path("data/test_vectors")
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    # Cleanup after test
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def faiss_vector_store(temp_vector_dir):
    """Provide a configured BrainCoreVectorStore using FAISS."""
    config = VectorDBConfig(
        enabled=True,
        engine="faiss",
        persist_directory=str(temp_vector_dir),
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    store = BrainCoreVectorStore(
        vector_config=config, project_root=Path(temp_vector_dir)
    )
    return store


def test_faiss_upsert_and_search(faiss_vector_store):
    """Test full integration loop for FAISS vector store (upsert -> search -> delete)."""
    # 1. Prepare sample document
    sample_doc: Dict[str, Any] = {
        "source_path": "test/integration_faiss.md",
        "relative_path": "integration_faiss.md",
        "source_type": "markdown",
        "metadata": {"domain": "test_domain"},
        "chunks": [
            {
                "chunk_index": 0,
                "chunk_hash": "abc123hash",
                "title": "FAISS Integration Test",
                "content": "This is a document about testing the FAISS engine in ACU-CORE. It covers vector similarity and embeddings.",
            },
            {
                "chunk_index": 1,
                "chunk_hash": "def456hash",
                "title": "Second Chunk",
                "content": "A completely different topic about MySQL and databases.",
            },
        ],
    }

    # 2. Upsert document
    success = faiss_vector_store.upsert_documents([sample_doc])
    assert success is True, "Upsert should succeed"

    # 3. Check status
    status = faiss_vector_store.get_status()
    assert status["status"] == "ready"
    assert status["records_count"] == 2

    # 4. Search for the first topic
    results = faiss_vector_store.search(
        "testing FAISS and embeddings", domain="test_domain", top_k=1
    )
    assert results is not None
    assert len(results) == 1
    assert "FAISS engine" in results[0]["content"]

    # 5. Search for the second topic
    results2 = faiss_vector_store.search(
        "databases and MySQL", domain="test_domain", top_k=1
    )
    assert results2 is not None
    assert len(results2) == 1
    assert "MySQL" in results2[0]["content"]

    # 6. Delete the source
    delete_success = faiss_vector_store.delete_source("test/integration_faiss.md")
    assert delete_success is True

    # 7. Check status after deletion
    status_after = faiss_vector_store.get_status()
    assert status_after["records_count"] == 0
