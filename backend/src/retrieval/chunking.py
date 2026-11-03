"""Markdown document loading and chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    version: str
    content: str
    source_path: str
    provenance: str


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    return meta, body


def load_markdown_documents(docs_dir: Path) -> list[tuple[dict, str, Path]]:
    documents: list[tuple[dict, str, Path]] = []
    for path in sorted(docs_dir.glob("*.md")):
        if path.name.upper().startswith("LICENSE"):
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        documents.append((meta, body, path))
    return documents


def chunk_documents(
    docs_dir: Path,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[DocumentChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    chunks: list[DocumentChunk] = []
    for meta, body, path in load_markdown_documents(docs_dir):
        doc_id = str(meta.get("doc_id") or path.stem)
        title = str(meta.get("title") or path.stem)
        section = str(meta.get("section") or "General")
        version = str(meta.get("version") or "1.0")
        parts = splitter.split_text(body.strip())
        for index, part in enumerate(parts):
            chunk_id = f"{doc_id}#chunk-{index + 1}"
            heading = _first_heading(part) or section
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    title=title,
                    section=heading,
                    version=version,
                    content=part.strip(),
                    source_path=str(path.relative_to(docs_dir.parent)),
                    provenance="synthetic-public",
                )
            )
    return chunks


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None
