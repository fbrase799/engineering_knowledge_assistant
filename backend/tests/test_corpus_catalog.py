"""Corpus catalog exposes scenario + readable sample documents."""

from __future__ import annotations

from backend.src.config import REPO_ROOT
from backend.src.retrieval.corpus_catalog import build_corpus_catalog


def test_corpus_catalog_lists_sample_docs():
    catalog = build_corpus_catalog(
        REPO_ROOT / "sample_documents",
        REPO_ROOT / "backend" / "data" / "faiss",
    )
    assert "sensor" in catalog["scenario"]["title"].lower()
    assert catalog["scenario"]["what_we_protect"]
    assert catalog["scenario"]["what_we_analyze"]
    doc_ids = {d["doc_id"] for d in catalog["documents"]}
    assert "REF-ARCH-001" in doc_ids
    assert "SPEC-HB-010" in doc_ids
    assert "ALERT-ESC-005" in doc_ids
    assert "RUN-GW-006" in doc_ids
    assert all(d["content_markdown"] for d in catalog["documents"])
