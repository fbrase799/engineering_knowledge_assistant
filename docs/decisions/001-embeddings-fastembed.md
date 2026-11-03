# ADR-001: FastEmbed MiniLM for local embeddings

## Status

Accepted

## Context

The PRD requires a local CPU embedding model. `sentence-transformers` pulls a large PyTorch stack, which slows Docker builds and CI.

## Decision

Use FastEmbed with `sentence-transformers/all-MiniLM-L6-v2` (ONNX) via LangChain's `FastEmbedEmbeddings`.

## Consequences

- Leaner images and faster installs
- Same MiniLM family as originally recommended
- Slight API difference vs HuggingFaceEmbeddings; wrapped in `backend/src/retrieval/store.py`
