"""Example questions are available for each retrieval mode."""

from __future__ import annotations

from backend.src.api.app import EXAMPLE_QUESTIONS
from backend.src.retrieval.models import RetrievalMode


def test_five_examples_per_mode():
    for mode in (RetrievalMode.HYBRID, RetrievalMode.LOCAL, RetrievalMode.WEB):
        matched = [q for q in EXAMPLE_QUESTIONS if q.retrieval_mode == mode]
        assert len(matched) == 5, f"{mode.value} expected 5 examples, got {len(matched)}"
        assert all(q.question.strip() for q in matched)
