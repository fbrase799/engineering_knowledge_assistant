"""Integration smoke: shared FAISS index retrieves timeout-related chunks."""

from __future__ import annotations

import pytest

from backend.src.config import get_settings
from backend.src.retrieval.retriever import SharedRetriever, reset_shared_retriever
from backend.src.retrieval.store import build_embeddings, load_faiss_index


@pytest.fixture
def faiss_retriever():
    settings = get_settings()
    if not (settings.faiss_index_dir / "index.faiss").exists():
        pytest.skip("FAISS index missing; run scripts/ingest.py")
    reset_shared_retriever()
    embeddings = build_embeddings(settings.embedding_model)
    store = load_faiss_index(settings.faiss_index_dir, embeddings)
    return SharedRetriever(store, settings)


def test_timeout_query_hits_reference_architecture(faiss_retriever):
    results = faiss_retriever.search(
        "What timeout thresholds are used for sensor heartbeats?",
        top_k=4,
        score_threshold=0.05,
    )
    assert results
    doc_ids = {r.doc_id for r in results}
    assert doc_ids & {"REF-ARCH-001", "SPEC-HB-010", "ADR-WATCHDOG-003"}
