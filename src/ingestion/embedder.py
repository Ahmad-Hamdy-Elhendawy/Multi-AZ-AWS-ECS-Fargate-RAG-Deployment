"""Sentence-transformer embeddings for queries and document chunks."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from sentence_transformers import SentenceTransformer

from src.config import EMBEDDING_MODEL_NAME, VECTOR_SIZE


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the embedding model (384-dimensional MiniLM)."""
    try:
        return SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Failed to load embedding model '{EMBEDDING_MODEL_NAME}': {exc}"
        ) from exc


class Embedder:
    """Thin wrapper around SentenceTransformer for query and batch embedding."""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = get_embedding_model() if model_name == EMBEDDING_MODEL_NAME else SentenceTransformer(model_name)

    def embed_text(self, text: str) -> list[float]:
        """Embed a single query or chunk.

        Args:
            text: Raw string to encode.

        Returns:
            A 384-dimensional dense vector.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text.")
        vector = self._model.encode(text, normalize_embeddings=True)
        embedding = vector.tolist()
        if len(embedding) != VECTOR_SIZE:
            raise RuntimeError(
                f"Unexpected embedding dimension {len(embedding)}; expected {VECTOR_SIZE}."
            )
        return embedding

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of document chunks.

        Args:
            texts: Chunk strings in insertion order.

        Returns:
            A list of 384-dimensional vectors aligned with ``texts``.
        """
        if not texts:
            raise ValueError("No texts were provided for embedding.")
        if any(not (item or "").strip() for item in texts):
            raise ValueError("Embedding batch contains empty strings.")

        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=len(texts) > 16,
        )
        embeddings = [row.tolist() for row in vectors]
        if any(len(item) != VECTOR_SIZE for item in embeddings):
            raise RuntimeError("One or more embeddings have an unexpected dimension.")
        return embeddings


def embed_text(text: str) -> list[float]:
    """Module-level helper that embeds a single string."""
    return Embedder().embed_text(text)


def embed_documents(texts: Sequence[str]) -> list[list[float]]:
    """Module-level helper that embeds a list of strings."""
    return Embedder().embed_documents(texts)
