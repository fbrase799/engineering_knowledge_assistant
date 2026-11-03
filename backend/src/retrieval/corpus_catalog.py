"""Public catalog of the shared synthetic RAG corpus for UI disclosure."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.src.retrieval.chunking import load_markdown_documents
from backend.src.retrieval.store import load_corpus_metadata

SCENARIO = {
    "title": "Fleet sensor monitoring / watchdog scenario",
    "summary": (
        "Your engineering knowledge is a read-only set of documents — a synthetic story "
        "about edge sensors, heartbeat supervision, and timeout handling. The documents "
        "are processed and stored in a local RAG."
    ),
    "what_we_protect": (
        "In a real system these would be internal design choices you want to keep "
        "grounded and citable. Here the corpus is public/synthetic on purpose, so we "
        "can still show selective disclosure: only retrieved excerpts go to the LLM, "
        "never the full corpus in one shot, and document text is never sent to Tavily."
    ),
    "what_we_analyze": (
        "Hybrid mode retrieves local excerpts, runs one targeted public web search, "
        "then compares documented approach vs current external guidance — with "
        "citations and an explicit evidence gap when something is missing."
    ),
}


def _first_paragraph(body: str) -> str:
    text = body.strip()
    text = re.sub(r"^#+\s+.*$", "", text, count=1, flags=re.MULTILINE).strip()
    for block in re.split(r"\n\s*\n", text):
        cleaned = re.sub(r"\s+", " ", block).strip()
        if cleaned and not cleaned.startswith("|") and not cleaned.startswith("#"):
            return cleaned[:320] + ("…" if len(cleaned) > 320 else "")
    return ""


def build_corpus_catalog(docs_dir: Path, index_dir: Path) -> dict[str, Any]:
    index_meta = load_corpus_metadata(index_dir)
    documents: list[dict[str, Any]] = []
    for meta, body, path in load_markdown_documents(docs_dir):
        documents.append(
            {
                "doc_id": str(meta.get("doc_id") or path.stem),
                "title": str(meta.get("title") or path.stem),
                "version": str(meta.get("version") or "1.0"),
                "section": str(meta.get("section") or "General"),
                "filename": path.name,
                "summary": _first_paragraph(body),
                "content_markdown": body.strip(),
                "provenance": "synthetic-public",
            }
        )
    return {
        "scenario": SCENARIO,
        "documents": documents,
        "index": {
            "embedding_model": index_meta.get("embedding_model"),
            "chunk_count": index_meta.get("chunk_count"),
            "document_count": index_meta.get("document_count") or len(documents),
            "created_at": index_meta.get("created_at"),
            "doc_ids": index_meta.get("doc_ids") or [d["doc_id"] for d in documents],
        },
    }
