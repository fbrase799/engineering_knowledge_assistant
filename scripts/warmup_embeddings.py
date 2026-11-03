#!/usr/bin/env python3
"""Download the local embedding model into the image cache (build-time warmup)."""

from __future__ import annotations

import os

from fastembed import TextEmbedding

# Keep in sync with backend.src.config.Settings.embedding_model default.
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def main() -> int:
    model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
    model = TextEmbedding(model_name=model_name)
    list(model.embed(["warmup"]))
    print(f"Warmed embedding model: {model_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
