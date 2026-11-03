"""Shared read-only FAISS retriever used by all requests."""

from __future__ import annotations

import threading
from functools import lru_cache

from langchain_community.vectorstores import FAISS

from backend.src.config import Settings, get_settings
from backend.src.retrieval.models import LocalSource
from backend.src.retrieval.store import build_embeddings, load_faiss_index


class SharedRetriever:
    """Process-wide FAISS index; per-request state remains independent."""

    def __init__(self, vectorstore: FAISS, settings: Settings):
        self._vectorstore = vectorstore
        self._settings = settings
        self._lock = threading.Lock()

    @property
    def vectorstore(self) -> FAISS:
        return self._vectorstore

    def search(
        self,
        question: str,
        *,
        top_k: int | None = None,
        score_threshold: float | None = None,
        max_context_chars: int | None = None,
    ) -> list[LocalSource]:
        k = top_k if top_k is not None else self._settings.retrieval_top_k
        threshold = (
            score_threshold
            if score_threshold is not None
            else self._settings.retrieval_score_threshold
        )
        budget = (
            max_context_chars
            if max_context_chars is not None
            else self._settings.max_context_chars
        )

        with self._lock:
            pairs = self._vectorstore.similarity_search_with_relevance_scores(question, k=k)

        selected: list[LocalSource] = []
        used_chars = 0
        for doc, score in pairs:
            if score < threshold:
                continue
            remaining = budget - used_chars
            if remaining <= 0:
                break
            content = doc.page_content
            if len(content) > remaining:
                if selected:
                    break
                content = content[:remaining]
            meta = doc.metadata
            selected.append(
                LocalSource(
                    source_id=str(meta.get("source_id")),
                    doc_id=str(meta.get("doc_id")),
                    title=str(meta.get("title")),
                    section=str(meta.get("section")),
                    version=str(meta.get("version")),
                    content=content,
                    score=float(score),
                    provenance=str(meta.get("provenance", "sample_documents")),
                )
            )
            used_chars += len(content)
        return selected


@lru_cache
def get_shared_retriever() -> SharedRetriever:
    settings = get_settings()
    embeddings = build_embeddings(settings.embedding_model)
    vectorstore = load_faiss_index(settings.faiss_index_dir, embeddings)
    return SharedRetriever(vectorstore, settings)


def reset_shared_retriever() -> None:
    get_shared_retriever.cache_clear()
