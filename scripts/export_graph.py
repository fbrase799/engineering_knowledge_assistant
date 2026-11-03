#!/usr/bin/env python3
"""Generate docs/langgraph.md from the compiled LangGraph graph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.src.graph.workflow import build_assistant_graph, get_graph_mermaid  # noqa: E402

HEADER = """# LangGraph Workflow

This diagram is **generated from the compiled LangGraph graph**.
Do not edit the Mermaid block by hand — run `uv run python scripts/export_graph.py`.

## Retrieval and synthesis flow
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs" / "langgraph.md",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the existing file is stale",
    )
    args = parser.parse_args()

    # Build without requiring FAISS/API keys — routing structure only.
    graph = build_assistant_graph()
    mermaid = get_graph_mermaid(graph)
    content = f"{HEADER}\n```mermaid\n{mermaid}\n```\n"

    if args.check:
        if not args.output.exists():
            print(f"Missing {args.output}", file=sys.stderr)
            return 1
        existing = args.output.read_text(encoding="utf-8")
        if existing != content:
            print("docs/langgraph.md is stale. Run scripts/export_graph.py", file=sys.stderr)
            return 1
        print("docs/langgraph.md is up to date")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
