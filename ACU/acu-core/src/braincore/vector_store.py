"""Optional vector stores for BrainCore chunks."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config.settings import vectordb_config
from src.utils.logger import log


class BrainCoreVectorStore:
    """Indexes and searches BrainCore chunks with ChromaDB or FAISS when enabled."""

    COLLECTION_NAME = "braincore_chunks"
    FAISS_INDEX_FILE = "braincore_faiss.index"
    FAISS_METADATA_FILE = "braincore_faiss_metadata.json"

    def __init__(self, vector_config=None, project_root: Optional[Path] = None):
        self.vector_config = vector_config or vectordb_config
        self.enabled = self.vector_config.enabled
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self._collection = None
        self._embedding_model = None
        self._faiss_index = None
        self._faiss_records: List[Dict[str, Any]] = []

    def upsert_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Upsert collected BrainCore documents into the configured vector store."""
        if not self.enabled or not documents:
            return False

        engine = self.vector_config.engine.lower()
        if engine == "faiss":
            return self._upsert_documents_faiss(documents)
        if engine != "chromadb":
            log.warning(
                f"Motor BrainCore vectorial no soportado: {self.vector_config.engine}"
            )
            self.enabled = False
            return False

        collection = self._get_collection()
        if collection is None:
            return False

        ids = []
        texts = []
        metadatas = []
        for document in documents:
            for chunk in document.get("chunks", []):
                ids.append(self._stable_chunk_id(document, chunk))
                texts.append(chunk["content"])
                metadatas.append(
                    {
                        "source_path": document["source_path"],
                        "relative_path": document["relative_path"],
                        "source_type": document["source_type"],
                        "title": chunk.get("title", "Documento"),
                        "chunk_index": int(chunk.get("chunk_index", 0)),
                        "chunk_hash": chunk.get("chunk_hash", ""),
                        "domain": document.get("metadata", {}).get("domain", "generic"),
                    }
                )

        if not ids:
            return False

        try:
            collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
            return True
        except Exception as exc:
            log.warning(f"No se pudo indexar BrainCore en ChromaDB: {exc}")
            self.enabled = False
            return False

    def delete_source(self, source_path: str) -> bool:
        """Delete indexed chunks for one source path from the vector backend."""
        normalized_path = str(source_path or "").strip()
        if not self.enabled or not normalized_path:
            return False

        engine = self.vector_config.engine.lower()
        if engine == "faiss":
            return self._delete_source_faiss(normalized_path)
        if engine != "chromadb":
            log.warning(
                f"Motor BrainCore vectorial no soportado: {self.vector_config.engine}"
            )
            self.enabled = False
            return False

        collection = self._get_collection()
        if collection is None:
            return False

        try:
            collection.delete(where={"source_path": normalized_path})
            return True
        except Exception as exc:
            log.warning(f"No se pudo eliminar fuente BrainCore en ChromaDB: {exc}")
            self.enabled = False
            return False

    def search(
        self,
        query: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = 5,
    ) -> Optional[List[Dict[str, Any]]]:
        """Search BrainCore chunks semantically, returning None when unavailable."""
        if not self.enabled:
            return None

        engine = self.vector_config.engine.lower()
        if engine == "faiss":
            return self._search_faiss(
                query=query,
                domain=domain,
                source_type=source_type,
                top_k=top_k,
            )
        if engine != "chromadb":
            log.warning(
                f"Motor BrainCore vectorial no soportado: {self.vector_config.engine}"
            )
            self.enabled = False
            return None

        collection = self._get_collection()
        if collection is None:
            return None

        where = self._build_where(domain=domain, source_type=source_type)
        try:
            query_kwargs = {
                "query_texts": [query],
                "n_results": top_k,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                query_kwargs["where"] = where
            query_result = collection.query(**query_kwargs)
        except Exception as exc:
            log.warning(f"Busqueda BrainCore vectorial no disponible: {exc}")
            self.enabled = False
            return None

        documents = (query_result.get("documents") or [[]])[0]
        metadatas = (query_result.get("metadatas") or [[]])[0]
        distances = (query_result.get("distances") or [[]])[0]

        results: List[Dict[str, Any]] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            chunk_hash = metadata.get("chunk_hash", "")
            results.append(
                {
                    "chunk_id": self._hash_to_int(chunk_hash),
                    "source_id": self._hash_to_int(metadata.get("source_path", "")),
                    "source_path": metadata.get("source_path", "unknown"),
                    "source_type": metadata.get("source_type", "unknown"),
                    "title": metadata.get("title", "Documento"),
                    "content": self._trim_document(document),
                    "similarity": self._distance_to_similarity(distance),
                    "metadata": {
                        "chunk": {
                            "chunk_hash": chunk_hash,
                            "chunk_index": metadata.get("chunk_index", 0),
                            "search_type": "vector_chromadb",
                        },
                        "source": {
                            "domain": metadata.get("domain", "generic"),
                            "relative_path": metadata.get("relative_path", ""),
                        },
                    },
                    "indexed_at": "",
                }
            )
        return results

    def get_status(self) -> Dict[str, Any]:
        """Return lightweight vector backend status without loading heavy clients."""
        engine = str(getattr(self.vector_config, "engine", "") or "").lower()
        persist_directory = self._persist_directory()
        configured = bool(getattr(self.vector_config, "enabled", False))
        status = {
            "enabled": configured,
            "available": bool(self.enabled),
            "engine": engine,
            "persist_directory": str(persist_directory),
            "embedding_model": str(
                getattr(self.vector_config, "embedding_model", "") or ""
            ),
            "collection_name": self.COLLECTION_NAME,
            "index_path": None,
            "metadata_path": None,
            "index_exists": False,
            "metadata_exists": False,
            "records_count": 0,
            "cached": bool(
                self._collection is not None
                or self._embedding_model is not None
                or self._faiss_index is not None
                or self._faiss_records
            ),
            "status": "enabled" if bool(self.enabled) else "disabled",
            "error": None,
        }

        if not configured:
            status["available"] = False
            status["status"] = "disabled"
            return status

        if engine == "faiss":
            index_path = self._faiss_index_path()
            metadata_path = self._faiss_metadata_path()
            records = self._load_faiss_records()
            status.update(
                {
                    "index_path": str(index_path),
                    "metadata_path": str(metadata_path),
                    "index_exists": index_path.exists(),
                    "metadata_exists": metadata_path.exists(),
                    "records_count": len(records),
                    "cached": bool(
                        self._faiss_index is not None
                        or self._faiss_records
                        or self._embedding_model is not None
                    ),
                }
            )
            status["status"] = (
                "ready"
                if status["index_exists"] and status["metadata_exists"]
                else "not_indexed"
            )
            return status

        if engine == "chromadb":
            status["status"] = "ready" if self._collection is not None else "configured"
            return status

        status["available"] = False
        status["status"] = "unsupported"
        status["error"] = f"Motor no soportado: {engine}"
        return status

    def _upsert_documents_faiss(self, documents: List[Dict[str, Any]]) -> bool:
        """Persist BrainCore chunks in a local FAISS index."""
        dependencies = self._get_faiss_dependencies()
        if dependencies is None:
            return False
        faiss, np = dependencies

        records = self._load_faiss_records()
        next_records = {
            str(record.get("id")): record
            for record in records
            if record.get("id") and record.get("text")
        }

        for document in documents:
            for chunk in document.get("chunks", []):
                record_id = self._stable_chunk_id(document, chunk)
                metadata = {
                    "source_path": document["source_path"],
                    "relative_path": document["relative_path"],
                    "source_type": document["source_type"],
                    "title": chunk.get("title", "Documento"),
                    "chunk_index": int(chunk.get("chunk_index", 0)),
                    "chunk_hash": chunk.get("chunk_hash", ""),
                    "domain": document.get("metadata", {}).get("domain", "generic"),
                }
                next_records[record_id] = {
                    "id": record_id,
                    "text": chunk["content"],
                    "metadata": metadata,
                }

        self._faiss_records = list(next_records.values())
        if not self._faiss_records:
            return False

        try:
            embeddings = self._encode_texts(
                [record["text"] for record in self._faiss_records],
                np=np,
            )
            index = faiss.IndexFlatIP(int(embeddings.shape[1]))
            index.add(embeddings)
            self._persist_faiss_index(index)
            self._persist_faiss_records(self._faiss_records)
            self._faiss_index = index
            return True
        except Exception as exc:
            log.warning(f"No se pudo indexar BrainCore en FAISS: {exc}")
            self.enabled = False
            return False

    def _delete_source_faiss(self, source_path: str) -> bool:
        """Remove one source from the local FAISS records and rebuild the index."""
        dependencies = self._get_faiss_dependencies()
        if dependencies is None:
            return False
        faiss, np = dependencies

        records = self._load_faiss_records()
        remaining_records = [
            record
            for record in records
            if record.get("metadata", {}).get("source_path") != source_path
        ]
        if len(remaining_records) == len(records):
            return False

        self._faiss_records = remaining_records
        try:
            if not remaining_records:
                self._delete_faiss_files()
                self._faiss_index = None
                self._persist_faiss_records([])
                return True

            embeddings = self._encode_texts(
                [record["text"] for record in remaining_records],
                np=np,
            )
            index = faiss.IndexFlatIP(int(embeddings.shape[1]))
            index.add(embeddings)
            self._persist_faiss_index(index)
            self._persist_faiss_records(remaining_records)
            self._faiss_index = index
            return True
        except Exception as exc:
            log.warning(f"No se pudo eliminar fuente BrainCore en FAISS: {exc}")
            self.enabled = False
            return False

    def _search_faiss(
        self,
        query: str,
        domain: Optional[str],
        source_type: Optional[str],
        top_k: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Search BrainCore chunks in the local FAISS index."""
        dependencies = self._get_faiss_dependencies()
        if dependencies is None:
            return None
        faiss, np = dependencies

        records = self._load_faiss_records()
        if not records:
            return None

        try:
            index = self._load_faiss_index(faiss)
            if index is None:
                return None

            query_embedding = self._encode_texts([query], np=np)
            candidate_count = min(max(top_k * 4, top_k), len(records))
            scores, indices = index.search(query_embedding, candidate_count)
        except Exception as exc:
            log.warning(f"Busqueda BrainCore FAISS no disponible: {exc}")
            self.enabled = False
            return None

        results: List[Dict[str, Any]] = []
        for score, record_index in zip(scores[0], indices[0]):
            if int(record_index) < 0 or int(record_index) >= len(records):
                continue
            record = records[int(record_index)]
            metadata = record.get("metadata", {})
            if domain and metadata.get("domain") != domain:
                continue
            if source_type and metadata.get("source_type") != source_type:
                continue
            results.append(
                self._serialize_vector_record(
                    record=record,
                    similarity=self._cosine_to_similarity(score),
                    search_type="vector_faiss",
                )
            )
            if len(results) >= top_k:
                break
        return results

    def _get_collection(self):
        """Create or reuse the ChromaDB collection."""
        if self._collection is not None:
            return self._collection

        if self.vector_config.engine.lower() != "chromadb":
            self.enabled = False
            return None

        try:
            import chromadb
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction,
            )
        except ImportError as exc:
            log.warning(f"Dependencias BrainCore vectoriales no instaladas: {exc}")
            self.enabled = False
            return None

        persist_directory = self._persist_directory()

        try:
            embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=self.vector_config.embedding_model
            )
            client = chromadb.PersistentClient(path=str(persist_directory))
            self._collection = client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
            return self._collection
        except Exception as exc:
            log.warning(f"No se pudo inicializar ChromaDB para BrainCore: {exc}")
            self.enabled = False
            return None

    def _get_faiss_dependencies(self) -> Optional[Tuple[Any, Any]]:
        """Import FAISS and NumPy lazily."""
        try:
            import faiss
            import numpy as np
        except ImportError as exc:
            log.warning(f"Dependencias BrainCore FAISS no instaladas: {exc}")
            self.enabled = False
            return None
        return faiss, np

    def _get_embedding_model(self):
        """Load the configured sentence-transformers embedding model lazily."""
        if self._embedding_model is not None:
            return self._embedding_model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            log.warning(f"Modelo de embeddings no disponible para FAISS: {exc}")
            self.enabled = False
            return None

        self._embedding_model = SentenceTransformer(self.vector_config.embedding_model)
        return self._embedding_model

    def _encode_texts(self, texts: List[str], np):
        """Encode and L2-normalize texts for cosine search with FAISS."""
        model = self._get_embedding_model()
        if model is None:
            raise RuntimeError("Modelo de embeddings no disponible")

        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype="float32")

    def _load_faiss_index(self, faiss):
        """Load the persisted FAISS index, caching it in memory."""
        if self._faiss_index is not None:
            return self._faiss_index

        index_path = self._faiss_index_path()
        if not index_path.exists():
            return None

        self._faiss_index = faiss.read_index(str(index_path))
        return self._faiss_index

    def _persist_faiss_index(self, index) -> None:
        """Write the FAISS index to disk."""
        index_path = self._faiss_index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        dependencies = self._get_faiss_dependencies()
        if dependencies is None:
            raise RuntimeError("FAISS no disponible")
        faiss, _ = dependencies
        faiss.write_index(index, str(index_path))

    def _load_faiss_records(self) -> List[Dict[str, Any]]:
        """Load persisted FAISS metadata records."""
        if self._faiss_records:
            return self._faiss_records

        metadata_path = self._faiss_metadata_path()
        if not metadata_path.exists():
            return []

        try:
            with metadata_path.open("r", encoding="utf-8") as file:
                records = json.load(file)
            self._faiss_records = records if isinstance(records, list) else []
        except Exception as exc:
            log.warning(f"No se pudo leer metadata FAISS BrainCore: {exc}")
            self._faiss_records = []
        return self._faiss_records

    def _persist_faiss_records(self, records: List[Dict[str, Any]]) -> None:
        """Write FAISS metadata records to disk."""
        metadata_path = self._faiss_metadata_path()
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=True)

    def _faiss_index_path(self) -> Path:
        """Return the absolute FAISS index path."""
        return self._persist_directory() / self.FAISS_INDEX_FILE

    def _faiss_metadata_path(self) -> Path:
        """Return the absolute FAISS metadata path."""
        return self._persist_directory() / self.FAISS_METADATA_FILE

    def _delete_faiss_files(self) -> None:
        """Remove persisted FAISS files when no records remain."""
        for path in (self._faiss_index_path(), self._faiss_metadata_path()):
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                log.warning(
                    f"No se pudo eliminar archivo FAISS BrainCore {path}: {exc}"
                )

    def _persist_directory(self) -> Path:
        """Return the absolute vector persistence directory."""
        persist_directory = Path(self.vector_config.persist_directory)
        if not persist_directory.is_absolute():
            persist_directory = self.project_root / persist_directory
        return persist_directory

    def _serialize_vector_record(
        self,
        record: Dict[str, Any],
        similarity: float,
        search_type: str,
    ) -> Dict[str, Any]:
        """Serialize one vector backend record into the BrainCore API shape."""
        metadata = record.get("metadata", {})
        chunk_hash = metadata.get("chunk_hash", "")
        return {
            "chunk_id": self._hash_to_int(chunk_hash),
            "source_id": self._hash_to_int(metadata.get("source_path", "")),
            "source_path": metadata.get("source_path", "unknown"),
            "source_type": metadata.get("source_type", "unknown"),
            "title": metadata.get("title", "Documento"),
            "content": self._trim_document(record.get("text", "")),
            "similarity": similarity,
            "metadata": {
                "chunk": {
                    "chunk_hash": chunk_hash,
                    "chunk_index": metadata.get("chunk_index", 0),
                    "search_type": search_type,
                },
                "source": {
                    "domain": metadata.get("domain", "generic"),
                    "relative_path": metadata.get("relative_path", ""),
                },
            },
            "indexed_at": "",
        }

    def _build_where(
        self,
        domain: Optional[str],
        source_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Build a Chroma where clause for optional filters."""
        clauses = []
        if domain:
            clauses.append({"domain": domain})
        if source_type:
            clauses.append({"source_type": source_type})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _stable_chunk_id(
        self,
        document: Dict[str, Any],
        chunk: Dict[str, Any],
    ) -> str:
        """Build a Chroma-safe deterministic id for a chunk."""
        raw_id = (
            f"{document['source_path']}::"
            f"{chunk.get('chunk_index', 0)}::"
            f"{chunk.get('chunk_hash', '')}"
        )
        cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw_id).strip("-")
        return cleaned[:240] or chunk.get("chunk_hash", "braincore-chunk")

    def _distance_to_similarity(self, distance: Any) -> float:
        """Convert cosine distance to bounded similarity."""
        if distance is None:
            return 1.0
        try:
            score = 1.0 - float(distance)
        except (TypeError, ValueError):
            return 0.0
        return round(min(max(score, 0.0), 1.0), 3)

    def _cosine_to_similarity(self, value: Any) -> float:
        """Convert normalized FAISS inner product to bounded similarity."""
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(min(max(score, 0.0), 1.0), 3)

    def _trim_document(self, document: str, max_chars: int = 420) -> str:
        """Keep vector results compact."""
        collapsed = re.sub(r"\s+", " ", document or "").strip()
        if len(collapsed) <= max_chars:
            return collapsed
        return collapsed[:max_chars].rstrip() + "..."

    def _hash_to_int(self, value: str) -> int:
        """Return a stable positive integer from a hash-like string."""
        cleaned = re.sub(r"[^a-fA-F0-9]", "", value or "")
        if not cleaned:
            return 0
        return int(cleaned[:12], 16)
