"""Local source ingestion utilities for BrainCore."""

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List


class BrainCoreIngestion:
    """Extract source documents and chunks from local files/directories."""

    SEARCHABLE_EXTENSIONS = {
        ".md",
        ".txt",
        ".sql",
        ".py",
        ".json",
        ".yaml",
        ".yml",
        ".pdf",
        ".docx",
        ".csv",
    }
    SKIP_DIRECTORIES = {
        "__pycache__",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        "venv",
        ".venv",
        "data",
    }

    def collect_documents(
        self,
        path: str,
        source_type: str = "auto",
        domain: str = "generic",
    ) -> Dict[str, Any]:
        """Collect indexable documents from a file or directory path."""
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return {"success": False, "error": f"Ruta no encontrada: {path}"}

        files = [target] if target.is_file() else self._iter_files(target)
        documents = []
        for file_path in files:
            document = self._build_document(
                file_path=file_path,
                root=target if target.is_dir() else file_path.parent,
                source_type=source_type,
                domain=domain,
            )
            if document:
                documents.append(document)

        return {
            "success": True,
            "data": {
                "path": str(target),
                "documents": documents,
                "files_found": len(files),
            },
        }

    def _iter_files(self, root: Path) -> List[Path]:
        """Return indexable files below root."""
        files: List[Path] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self.SEARCHABLE_EXTENSIONS:
                continue
            if any(part in self.SKIP_DIRECTORIES for part in path.parts):
                continue
            files.append(path)
        return files

    def _build_document(
        self,
        file_path: Path,
        root: Path,
        source_type: str,
        domain: str,
    ) -> Dict[str, Any]:
        """Build a source document with chunks and metadata."""
        if file_path.suffix.lower() not in self.SEARCHABLE_EXTENSIONS:
            return {}

        try:
            content = self._extract_text_content(file_path)
        except Exception as exc:
            import logging

            logging.warning(f"Error extrayendo {file_path}: {exc}")
            return {}

        normalized = content.strip()
        if not normalized:
            return {}

        relative_path = self._relative_path(file_path, root)
        resolved_type = (
            self._infer_source_type(file_path) if source_type == "auto" else source_type
        )
        chunks = self._split_into_chunks(normalized)
        return {
            "source_path": str(file_path),
            "relative_path": relative_path,
            "source_type": resolved_type,
            "content_hash": self._hash_text(normalized),
            "metadata": {
                "domain": domain,
                "file_name": file_path.name,
                "extension": file_path.suffix.lower(),
                "relative_path": relative_path,
            },
            "chunks": [
                {
                    "chunk_index": index,
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "chunk_hash": self._hash_text(chunk["content"]),
                    "metadata": {
                        "domain": domain,
                        "relative_path": relative_path,
                        "section": chunk["title"],
                    },
                }
                for index, chunk in enumerate(chunks)
            ],
        }

    def _extract_text_content(self, file_path: Path) -> str:
        """Extract text content based on file extension."""
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            try:
                import pypdf

                reader = pypdf.PdfReader(str(file_path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                return text
            except ImportError:
                return f"Error: pypdf no esta instalado para leer {file_path.name}"

        elif suffix == ".docx":
            try:
                import docx

                doc = docx.Document(str(file_path))
                text = "\n".join(para.text for para in doc.paragraphs)
                return text
            except ImportError:
                return (
                    f"Error: python-docx no esta instalado para leer {file_path.name}"
                )

        elif suffix == ".csv":
            import csv

            with open(
                file_path, newline="", encoding="utf-8", errors="ignore"
            ) as csvfile:
                csv_reader = csv.reader(csvfile)
                # Convertir a formato legible en markdown: Fila 1: col1, col2
                lines = []
                for i, row in enumerate(csv_reader):
                    if row:
                        lines.append(f"Fila {i + 1}: " + " | ".join(row))
                return "\n".join(lines)

        else:
            return file_path.read_text(encoding="utf-8", errors="ignore")

    def _relative_path(self, file_path: Path, root: Path) -> str:
        """Return a stable relative path when possible."""
        try:
            return str(file_path.relative_to(root))
        except ValueError:
            return file_path.name

    def _infer_source_type(self, file_path: Path) -> str:
        """Infer source type from extension."""
        suffix = file_path.suffix.lower()
        if suffix == ".md":
            return "markdown"
        if suffix == ".sql":
            return "sql"
        if suffix == ".py":
            return "code"
        if suffix in {".json", ".yaml", ".yml"}:
            return "config"
        if suffix == ".pdf":
            return "pdf"
        if suffix == ".docx":
            return "word_document"
        if suffix == ".csv":
            return "csv_data"
        return "text"

    def _split_into_chunks(
        self, content: str, max_chars: int = 1600
    ) -> List[Dict[str, str]]:
        """Split source text by markdown headings and paragraph boundaries."""
        sections: List[Dict[str, str]] = []
        current_title = "Documento"
        current_lines: List[str] = []

        def flush_section():
            text = "\n".join(current_lines).strip()
            if not text:
                return
            for chunk in self._chunk_text(text, max_chars=max_chars):
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
        if not sections:
            for chunk in self._chunk_text(content, max_chars=max_chars):
                sections.append({"title": "Documento", "content": chunk})
        return sections

    def _chunk_text(self, text: str, max_chars: int) -> List[str]:
        """Split long text while preserving paragraphs where possible."""
        paragraphs = [
            part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()
        ]
        if not paragraphs:
            return []

        chunks: List[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if len(candidate) <= max_chars:
                current = candidate
                continue

            if current:
                chunks.append(current)
            if len(paragraph) <= max_chars:
                current = paragraph
            else:
                chunks.extend(
                    paragraph[start : start + max_chars]
                    for start in range(0, len(paragraph), max_chars)
                )
                current = ""

        if current:
            chunks.append(current)
        return chunks

    def _hash_text(self, text: str) -> str:
        """Return a stable SHA-256 hash."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
