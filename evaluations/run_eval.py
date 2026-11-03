#!/usr/bin/env python3
"""Run evaluation cases against mocked or live graph dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.src.config import get_settings  # noqa: E402
from backend.src.graph.workflow import build_assistant_graph  # noqa: E402
from backend.src.integrations.azure_openai import (  # noqa: E402
    AzureOpenAIClient,
    RecordingLLMClient,
)
from backend.src.integrations.tavily_client import (  # noqa: E402
    RecordingTavilyClient,
    TavilyClient,
)
from backend.src.retrieval.models import (  # noqa: E402
    ComparisonSections,
    LocalSource,
    RetrievalMode,
    WebSource,
)
from backend.src.retrieval.retriever import get_shared_retriever  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--cases",
        type=Path,
        default=REPO_ROOT / "evaluations" / "cases.json",
    )
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    settings = get_settings()

    if args.live:
        graph = build_assistant_graph(
            settings=settings,
            tavily=TavilyClient(settings),
            llm=AzureOpenAIClient(settings),
        )
    else:
        web = [
            WebSource(
                source_id="web-1",
                title="Example watchdog guidance",
                url="https://example.com/watchdog",
                snippet="Use hardware watchdog fallbacks and conservative timeouts.",
                retrieved_at=datetime.now(UTC),
            )
        ]
        local = [
            LocalSource(
                source_id="REF-ARCH-001#chunk-1",
                doc_id="REF-ARCH-001",
                title="Sensor Monitoring Reference Architecture",
                section="Timeout strategy",
                version="1.2",
                content="Healthy <30s, Degraded 30-90s, Offline >90s.",
                score=0.9,
            )
        ]

        class FixedRetriever:
            def search(self, question: str, **kwargs):
                return local

        graph = build_assistant_graph(
            settings=settings,
            retriever=FixedRetriever(),  # type: ignore[arg-type]
            tavily=RecordingTavilyClient(web),
            llm=RecordingLLMClient(
                sections=ComparisonSections(
                    documented_approach="30/90 timeouts",
                    web_findings="Hardware fallback",
                    comparison="Agree on explicit supervision",
                    engineering_implications="(proposal) Document hardware policy",
                ),
                citation_ids=["REF-ARCH-001#chunk-1", "web-1"],
            ),
        )

    failures = 0
    for case in cases:
        mode = RetrievalMode(case["retrieval_mode"])
        result = graph.invoke(
            {
                "request_id": case["id"],
                "question": case["question"],
                "retrieval_mode": mode,
            }
        )
        expect = case["expect"]
        usage = result["usage_metrics"]
        if hasattr(usage, "tavily_calls"):
            tavily_calls = usage.tavily_calls
            llm_calls = usage.llm_calls
        else:
            tavily_calls = usage["tavily_calls"]
            llm_calls = usage["llm_calls"]
        ok = True
        if tavily_calls > expect.get("max_tavily_calls", 1):
            ok = False
        if llm_calls > expect.get("max_llm_calls", 1):
            ok = False
        allowed_statuses = expect.get("comparison_status_in")
        if allowed_statuses and result["comparison_status"] not in allowed_statuses:
            if not expect.get("allow_evidence_gap_or_partial"):
                ok = False
        print(
            f"{'PASS' if ok else 'FAIL'} {case['id']} "
            f"status={result['comparison_status']} tavily={tavily_calls} llm={llm_calls}"
        )
        failures += 0 if ok else 1

    if not args.live:
        # Ensure real FAISS is loadable for local integration confidence.
        try:
            get_shared_retriever()
            print("PASS faiss-index-loadable")
        except FileNotFoundError:
            print("WARN faiss-index-missing (run scripts/ingest.py)")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
