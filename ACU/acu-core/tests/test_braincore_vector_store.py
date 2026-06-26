import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

from src.braincore.vector_store import BrainCoreVectorStore


class FakeCollection:
    def __init__(self):
        self.upsert_calls = []
        self.query_calls = []
        self.delete_calls = []

    def upsert(self, ids, documents, metadatas):
        self.upsert_calls.append(
            {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
        )

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {
            "documents": [["FastAPI expone ACU como puente REST."]],
            "metadatas": [
                [
                    {
                        "source_path": "wiki/api.md",
                        "relative_path": "api.md",
                        "source_type": "markdown",
                        "title": "Arquitectura API",
                        "chunk_index": 0,
                        "chunk_hash": "abcdef123456",
                        "domain": "acu",
                    }
                ]
            ],
            "distances": [[0.08]],
        }

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)


class FakeVectorStore(BrainCoreVectorStore):
    def __init__(self, collection):
        super().__init__(
            vector_config=SimpleNamespace(
                enabled=True,
                engine="chromadb",
                persist_directory="./data/vectors",
                embedding_model="test-model",
            )
        )
        self._collection = collection


class FakeEmbeddingMatrix:
    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]) if rows else 0)


class FakeFaissIndex:
    def __init__(self, dimensions):
        self.dimensions = dimensions
        self.embeddings = None

    def add(self, embeddings):
        self.embeddings = embeddings

    def search(self, query_embedding, top_k):
        return [[0.87, 0.42][:top_k]], [[0, 1][:top_k]]


class FakeFaiss:
    IndexFlatIP = FakeFaissIndex


class FakeFaissVectorStore(BrainCoreVectorStore):
    def __init__(self):
        super().__init__(
            vector_config=SimpleNamespace(
                enabled=True,
                engine="faiss",
                persist_directory="./data/vectors",
                embedding_model="test-model",
            )
        )
        self.persisted_index = None

    def _get_faiss_dependencies(self):
        return FakeFaiss, object()

    def _encode_texts(self, texts, np):
        return FakeEmbeddingMatrix([[1.0, 0.0] for _ in texts])

    def _persist_faiss_index(self, index):
        self.persisted_index = index

    def _load_faiss_index(self, faiss):
        return self.persisted_index

    def _load_faiss_records(self):
        return self._faiss_records

    def _persist_faiss_records(self, records):
        self._faiss_records = records

    def _delete_faiss_files(self):
        self._faiss_records = []
        self.persisted_index = None


def test_vector_store_upserts_document_chunks():
    collection = FakeCollection()
    store = FakeVectorStore(collection)
    documents = [
        {
            "source_path": "C:/repo/wiki/api.md",
            "relative_path": "api.md",
            "source_type": "markdown",
            "metadata": {"domain": "acu"},
            "chunks": [
                {
                    "chunk_index": 0,
                    "chunk_hash": "abcdef123456",
                    "title": "Arquitectura API",
                    "content": "FastAPI expone ACU como puente REST.",
                }
            ],
        }
    ]

    result = store.upsert_documents(documents)

    assert result is True
    assert len(collection.upsert_calls) == 1
    call = collection.upsert_calls[0]
    assert call["documents"] == ["FastAPI expone ACU como puente REST."]
    assert call["metadatas"][0]["domain"] == "acu"
    assert call["metadatas"][0]["chunk_hash"] == "abcdef123456"


def test_vector_store_search_serializes_results_and_filters():
    collection = FakeCollection()
    store = FakeVectorStore(collection)

    results = store.search(
        query="fastapi rest",
        domain="acu",
        source_type="markdown",
        top_k=3,
    )

    assert collection.query_calls[0]["where"] == {
        "$and": [{"domain": "acu"}, {"source_type": "markdown"}]
    }
    assert results[0]["source_path"] == "wiki/api.md"
    assert results[0]["source_type"] == "markdown"
    assert results[0]["similarity"] == 0.92
    assert results[0]["metadata"]["chunk"]["search_type"] == "vector_chromadb"


def test_vector_store_deletes_chromadb_source_records():
    collection = FakeCollection()
    store = FakeVectorStore(collection)

    result = store.delete_source("wiki/api.md")

    assert result is True
    assert collection.delete_calls == [{"where": {"source_path": "wiki/api.md"}}]


def test_vector_store_get_collection_initializes_chromadb(monkeypatch):
    created = {}

    class FakeEmbeddingFunction:
        def __init__(self, model_name):
            created["model_name"] = model_name

    class FakeClient:
        def __init__(self, path):
            created["path"] = path

        def get_or_create_collection(self, name, embedding_function, metadata):
            created["collection_name"] = name
            created["metadata"] = metadata
            created["embedding_function"] = embedding_function
            return "collection"

    chromadb_module = ModuleType("chromadb")
    chromadb_module.PersistentClient = FakeClient
    utils_module = ModuleType("chromadb.utils")
    embedding_module = ModuleType("chromadb.utils.embedding_functions")
    embedding_module.SentenceTransformerEmbeddingFunction = FakeEmbeddingFunction

    monkeypatch.setitem(sys.modules, "chromadb", chromadb_module)
    monkeypatch.setitem(sys.modules, "chromadb.utils", utils_module)
    monkeypatch.setitem(
        sys.modules,
        "chromadb.utils.embedding_functions",
        embedding_module,
    )

    store = BrainCoreVectorStore(
        vector_config=SimpleNamespace(
            enabled=True,
            engine="chromadb",
            persist_directory="vectors",
            embedding_model="test-model",
        ),
        project_root=Path("C:/repo"),
    )

    assert store._get_collection() == "collection"
    assert created["path"] == str(Path("C:/repo") / "vectors")
    assert created["model_name"] == "test-model"
    assert created["collection_name"] == "braincore_chunks"


def test_vector_store_disabled_returns_none_for_search():
    store = BrainCoreVectorStore(
        vector_config=SimpleNamespace(
            enabled=False,
            engine="chromadb",
            persist_directory="./data/vectors",
            embedding_model="test-model",
        )
    )

    assert store.search("fastapi") is None
    assert store.upsert_documents([]) is False
    assert store.get_status()["status"] == "disabled"
    assert store.get_status()["available"] is False


def test_vector_store_reports_chromadb_status_without_initializing_client():
    collection = FakeCollection()
    store = FakeVectorStore(collection)

    status = store.get_status()

    assert status["enabled"] is True
    assert status["available"] is True
    assert status["engine"] == "chromadb"
    assert status["collection_name"] == "braincore_chunks"
    assert status["status"] == "ready"
    assert status["cached"] is True


def test_faiss_vector_store_reports_index_status():
    store = FakeFaissVectorStore()
    store._faiss_records = [
        {
            "id": "1",
            "text": "Resultado ACU",
            "metadata": {"source_path": "wiki/api.md"},
        }
    ]

    status = store.get_status()

    assert status["enabled"] is True
    assert status["engine"] == "faiss"
    assert status["records_count"] == 1
    assert status["index_path"].endswith("braincore_faiss.index")
    assert status["metadata_path"].endswith("braincore_faiss_metadata.json")
    assert status["status"] == "not_indexed"


def test_faiss_vector_store_upserts_and_searches_records():
    store = FakeFaissVectorStore()
    documents = [
        {
            "source_path": "C:/repo/wiki/api.md",
            "relative_path": "api.md",
            "source_type": "markdown",
            "metadata": {"domain": "acu"},
            "chunks": [
                {
                    "chunk_index": 0,
                    "chunk_hash": "abcdef123456",
                    "title": "Arquitectura API",
                    "content": "FastAPI expone ACU como puente REST.",
                },
                {
                    "chunk_index": 1,
                    "chunk_hash": "fedcba654321",
                    "title": "Otro dominio",
                    "content": "Contenido administrativo.",
                },
            ],
        }
    ]
    documents[0]["chunks"][1]["content"] = "Otro dominio"
    documents[0]["metadata"] = {"domain": "acu"}

    assert store.upsert_documents(documents) is True

    results = store.search(
        query="fastapi rest",
        domain="acu",
        source_type="markdown",
        top_k=1,
    )

    assert results[0]["content"] == "FastAPI expone ACU como puente REST."
    assert results[0]["similarity"] == 0.87
    assert results[0]["metadata"]["chunk"]["search_type"] == "vector_faiss"


def test_faiss_vector_store_applies_domain_filter():
    store = FakeFaissVectorStore()
    store._faiss_records = [
        {
            "id": "1",
            "text": "Resultado ACU",
            "metadata": {
                "source_path": "wiki/api.md",
                "relative_path": "api.md",
                "source_type": "markdown",
                "title": "API",
                "chunk_index": 0,
                "chunk_hash": "abcdef123456",
                "domain": "acu",
            },
        },
        {
            "id": "2",
            "text": "Resultado ventas",
            "metadata": {
                "source_path": "wiki/sales.md",
                "relative_path": "sales.md",
                "source_type": "markdown",
                "title": "Ventas",
                "chunk_index": 0,
                "chunk_hash": "fedcba654321",
                "domain": "sales",
            },
        },
    ]
    store.persisted_index = FakeFaissIndex(2)

    results = store.search("api", domain="sales", source_type="markdown", top_k=1)

    assert len(results) == 1
    assert results[0]["content"] == "Resultado ventas"
    assert results[0]["metadata"]["source"]["domain"] == "sales"


def test_faiss_vector_store_deletes_source_and_rebuilds_index():
    store = FakeFaissVectorStore()
    store._faiss_records = [
        {
            "id": "1",
            "text": "Resultado ACU",
            "metadata": {
                "source_path": "wiki/api.md",
                "relative_path": "api.md",
                "source_type": "markdown",
                "title": "API",
                "chunk_index": 0,
                "chunk_hash": "abcdef123456",
                "domain": "acu",
            },
        },
        {
            "id": "2",
            "text": "Resultado ventas",
            "metadata": {
                "source_path": "wiki/sales.md",
                "relative_path": "sales.md",
                "source_type": "markdown",
                "title": "Ventas",
                "chunk_index": 0,
                "chunk_hash": "fedcba654321",
                "domain": "sales",
            },
        },
    ]

    result = store.delete_source("wiki/api.md")

    assert result is True
    assert len(store._faiss_records) == 1
    assert store._faiss_records[0]["metadata"]["source_path"] == "wiki/sales.md"
    assert store.persisted_index is not None
