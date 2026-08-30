"""Deterministic text chunking that preserves parent page metadata."""

from __future__ import annotations

import hashlib
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHUNK_OVERLAP, CHUNK_SIZE


def _chunk_id(document_name: str, page_no: int, chunk_index: int, text: str) -> str:
    """Build a stable identifier for a chunk so re-ingestion is idempotent."""
    fingerprint = f"{document_name}|{page_no}|{chunk_index}|{text}"
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"{document_name}::p{page_no}::c{chunk_index}::{digest}"


def chunk_documents(
    pages: list[dict[str, Any]],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Split parsed page documents into overlapping character chunks.

    Args:
        pages: Output of the PDF parser.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        Chunk dictionaries containing text, parent metadata, and chunk_id.
    """
    if not pages:
        raise ValueError("No parsed pages were provided for chunking.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks: list[dict[str, Any]] = []
    for page in pages:
        text = (page.get("text") or "").strip()
        metadata = dict(page.get("metadata") or {})
        if not text:
            continue

        splits = splitter.split_text(text)
        document_name = str(metadata.get("document_name", "unknown.pdf"))
        page_no = int(metadata.get("page_no", 0))

        for index, chunk_text in enumerate(splits):
            chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        "document_name": document_name,
                        "page_no": page_no,
                        "chunk_id": _chunk_id(document_name, page_no, index, chunk_text),
                    },
                }
            )

    if not chunks:
        raise ValueError("Chunking produced no text chunks from the parsed pages.")
    return chunks
