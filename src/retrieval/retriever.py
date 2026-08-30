"""Query embedding and top-k semantic retrieval."""

from __future__ import annotations

from typing import Any

from src.config import TOP_K
from src.ingestion.embedder import Embedder
from src.vectorstore.vector_store import VectorStore


def retrieve(
    query: str,
    top_k: int = TOP_K,
    embedder: Embedder | None = None,
    store: VectorStore | None = None,
) -> list[dict[str, Any]]:
    """Embed a user query and return the most relevant medical chunks.

    Args:
        query: Natural-language clinical question.
        top_k: Number of chunks to return (default 3).
        embedder: Optional shared embedder instance.
        store: Optional shared vector store instance.

    Returns:
        Ranked chunks with text, metadata, and similarity score.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("Query must not be empty.")

    encoder = embedder or Embedder()
    vector_store = store or VectorStore()
    query_vector = encoder.embed_text(cleaned)
    hits = vector_store.search(query_vector, top_k=top_k)
    if not hits:
        raise RuntimeError("Retrieval returned no matching chunks for this query.")
    return hits
