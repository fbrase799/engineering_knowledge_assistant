"""Chunking and top-k / budget enforcement tests."""

from __future__ import annotations

from backend.src.config import REPO_ROOT
from backend.src.retrieval.chunking import chunk_documents
from backend.src.retrieval.retriever import SharedRetriever


def test_sample_documents_chunk():
    docs_dir = REPO_ROOT / "sample_documents"
    chunks = chunk_documents(docs_dir, chunk_size=800, chunk_overlap=120)
    assert len(chunks) >= 4
    doc_ids = {c.doc_id for c in chunks}
    assert "REF-ARCH-001" in doc_ids
    assert "SPEC-HB-010" in doc_ids
    assert all(c.content for c in chunks)


def test_top_k_and_context_budget(local_sources, settings):
    class StubStore:
        def similarity_search_with_relevance_scores(self, question, k):
            docs = []
            for src in local_sources * 3:
                class Doc:
                    page_content = src.content + (" x" * 200)
                    metadata = src.model_dump()
                docs.append((Doc(), src.score))
            return docs[:k]

    settings.retrieval_top_k = 2
    settings.max_context_chars = 400
    settings.retrieval_score_threshold = 0.1
    retriever = SharedRetriever(StubStore(), settings)  # type: ignore[arg-type]
    results = retriever.search("timeouts")
    assert len(results) <= 2
    assert sum(len(r.content) for r in results) <= settings.max_context_chars + 50
