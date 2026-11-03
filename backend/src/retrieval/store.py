"""FAISS index load/save helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


def build_embeddings(model_name: str) -> FastEmbedEmbeddings:
    return FastEmbedEmbeddings(model_name=model_name)


def save_faiss_index(
    vectorstore: FAISS,
    index_dir: Path,
    metadata: dict[str, Any],
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    (index_dir / "corpus_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def load_faiss_index(index_dir: Path, embeddings: FastEmbedEmbeddings) -> FAISS:
    if not (index_dir / "index.faiss").exists():
        raise FileNotFoundError(
            f"FAISS index not found at {index_dir}. Run scripts/ingest.py first."
        )
    return FAISS.load_local(
        str(index_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def documents_from_chunks(chunks: list[Any]) -> list[Document]:
    docs: list[Document] = []
    for chunk in chunks:
        docs.append(
            Document(
                page_content=chunk.content,
                metadata={
                    "source_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "version": chunk.version,
                    "source_path": chunk.source_path,
                    "provenance": chunk.provenance,
                },
            )
        )
    return docs


def load_corpus_metadata(index_dir: Path) -> dict[str, Any]:
    path = index_dir / "corpus_metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
