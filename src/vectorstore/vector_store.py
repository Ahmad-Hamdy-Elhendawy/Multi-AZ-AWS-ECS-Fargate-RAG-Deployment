"""Persistent local Qdrant client for medical document chunks."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.config import COLLECTION_NAME, QDRANT_PATH, VECTOR_SIZE, ensure_asset_directories


def _point_id(chunk_id: str) -> str:
    """Derive a stable UUID from a deterministic chunk identifier."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class VectorStore:
    """Qdrant-backed vector store stored on disk under src/assets/qdrant/."""

    def __init__(self, path: str | None = None, collection_name: str = COLLECTION_NAME) -> None:
        ensure_asset_directories()
        self.collection_name = collection_name
        self.path = path or str(QDRANT_PATH)
        try:
            self.client = QdrantClient(path=self.path)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to initialize Qdrant at '{self.path}': {exc}") from exc
        self.ensure_collection()

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        existing = {item.name for item in self.client.get_collections().collections}
        if self.collection_name in existing:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    def recreate_collection(self) -> None:
        """Drop and recreate the collection so re-indexing does not keep stale chunks."""
        existing = {item.name for item in self.client.get_collections().collections}
        if self.collection_name in existing:
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    def count(self) -> int:
        """Return the number of points currently stored in the collection."""
        try:
            result = self.client.count(collection_name=self.collection_name, exact=True)
            return int(result.count)
        except (UnexpectedResponse, ValueError, Exception):  # noqa: BLE001
            return 0

    def upsert_chunks(self, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> int:
        """Insert or update chunk embeddings in Qdrant.

        Args:
            chunks: Chunk dictionaries with text and metadata.
            embeddings: Dense vectors aligned with ``chunks``.

        Returns:
            Number of upserted points.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length.")
        if not chunks:
            raise ValueError("No chunks were provided for upsert.")

        points: list[PointStruct] = []
        for chunk, vector in zip(chunks, embeddings):
            metadata = dict(chunk.get("metadata") or {})
            chunk_id = str(metadata.get("chunk_id") or "")
            if not chunk_id:
                raise ValueError("Each chunk must include metadata.chunk_id.")
            points.append(
                PointStruct(
                    id=_point_id(chunk_id),
                    vector=vector,
                    payload={
                        "text": chunk["text"],
                        "document_name": metadata.get("document_name"),
                        "page_no": metadata.get("page_no"),
                        "chunk_id": chunk_id,
                    },
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(self, query_vector: list[float], top_k: int = 3) -> list[dict[str, Any]]:
        """Return the most similar chunks for a query embedding.

        Args:
            query_vector: 384-dimensional query embedding.
            top_k: Maximum number of hits to return.

        Returns:
            Hits containing text, metadata, and cosine similarity score.
        """
        if not query_vector:
            raise ValueError("query_vector must not be empty.")
        if self.count() == 0:
            raise RuntimeError(
                "The vector store is empty. Run ingestion before asking medical questions."
            )

        hits = self._query_similar(query_vector, top_k)
        results: list[dict[str, Any]] = []
        for hit in hits:
            payload = getattr(hit, "payload", None) or {}
            results.append(
                {
                    "text": payload.get("text", ""),
                    "score": float(getattr(hit, "score", 0.0) or 0.0),
                    "metadata": {
                        "document_name": payload.get("document_name"),
                        "page_no": payload.get("page_no"),
                        "chunk_id": payload.get("chunk_id"),
                    },
                }
            )
        return results

    def _query_similar(self, query_vector: list[float], top_k: int) -> list[Any]:
        """Run similarity search using the current qdrant-client API.

        Newer clients removed ``QdrantClient.search`` in favor of ``query_points``.
        """
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )
            return list(getattr(response, "points", response) or [])

        if hasattr(self.client, "search"):
            return list(
                self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    with_payload=True,
                )
            )

        raise RuntimeError(
            "Installed qdrant-client does not expose query_points or search. "
            "Upgrade or reinstall qdrant-client."
        )

    def collection_stats(self) -> dict[str, Any]:
        """Return lightweight stats for health checks and the Streamlit sidebar."""
        return {
            "collection_name": self.collection_name,
            "points_count": self.count(),
            "vector_size": VECTOR_SIZE,
            "storage_path": self.path,
        }
