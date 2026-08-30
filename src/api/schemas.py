"""Pydantic request and response models for the Medical RAG API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Incoming chat question."""

    query: str = Field(..., min_length=1, description="Medical question about polio guidelines.")
    top_k: int | None = Field(default=None, ge=1, le=10, description="Optional retrieval depth.")


class SourceMetadata(BaseModel):
    """Citation metadata for a retrieved source page."""

    document_name: str
    page_no: int
    score: float
    citation: str


class RetrievedChunk(BaseModel):
    """A single retrieved evidence chunk shown to clients and the UI."""

    text: str
    score: float
    metadata: dict[str, Any]


class QueryResponse(BaseModel):
    """Grounded answer plus supporting sources."""

    answer: str
    references: list[SourceMetadata]
    sources: list[RetrievedChunk]
    model: str


class IngestResponse(BaseModel):
    """Summary returned after indexing PDFs."""

    status: str
    documents: list[str]
    pages_parsed: int
    chunks_indexed: int
    collection: dict[str, Any]


class HealthResponse(BaseModel):
    """Liveness and vector-store status."""

    status: str
    collection_name: str
    points_count: int
    groq_configured: bool
