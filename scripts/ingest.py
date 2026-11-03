#!/usr/bin/env python3
"""Offline ingestion: chunk sample documents, embed locally, write FAISS index."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from langchain_community.vectorstores import FAISS  # noqa: E402

from backend.src.config import get_settings  # noqa: E402
from backend.src.retrieval.chunking import chunk_documents  # noqa: E402
from backend.src.retrieval.store import (  # noqa: E402
    build_embeddings,
    documents_from_chunks,
    save_faiss_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the shared FAISS index")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=None,
        help="Directory containing sample markdown documents",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=None,
        help="Output directory for the FAISS index",
    )
    args = parser.parse_args()
    settings = get_settings()
    docs_dir = args.docs_dir or settings.sample_docs_dir
    index_dir = args.index_dir or settings.faiss_index_dir

    chunks = chunk_documents(
        docs_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    if not chunks:
        print(f"No documents found in {docs_dir}", file=sys.stderr)
        return 1

    embeddings = build_embeddings(settings.embedding_model)
    docs = documents_from_chunks(chunks)
    vectorstore = FAISS.from_documents(docs, embeddings)
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "document_count": len({c.doc_id for c in chunks}),
        "chunk_count": len(chunks),
        "doc_ids": sorted({c.doc_id for c in chunks}),
    }
    save_faiss_index(vectorstore, index_dir, metadata)
    print(f"Wrote {len(chunks)} chunks to {index_dir}")
    print(f"Documents: {', '.join(metadata['doc_ids'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
