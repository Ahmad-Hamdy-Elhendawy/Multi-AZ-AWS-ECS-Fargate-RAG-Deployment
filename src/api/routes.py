"""HTTP routes for ingestion, chat, and health checks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.schemas import (
    HealthResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
    SourceMetadata,
)
from src.config import COLLECTION_NAME, GROQ_API_KEY, TOP_K
from src.generation.generator import generate_answer
from src.ingestion.ingest import ingest
from src.retrieval.retriever import retrieve
from src.vectorstore.vector_store import VectorStore

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return process and vector-store health."""
    try:
        stats = VectorStore().collection_stats()
        points = int(stats["points_count"])
        status = "ok" if points > 0 else "empty_index"
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Vector store unavailable: {exc}") from exc

    return HealthResponse(
        status=status,
        collection_name=str(stats.get("collection_name") or COLLECTION_NAME),
        points_count=points,
        groq_configured=bool(GROQ_API_KEY),
    )


@router.post("/ingest", response_model=IngestResponse)
def ingest_documents() -> IngestResponse:
    """Parse PDFs under src/assets/documents and rebuild the Qdrant index."""
    try:
        result = ingest(recreate=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc
    return IngestResponse(**result)


@router.post("/chat", response_model=QueryResponse)
def chat(request: QueryRequest) -> QueryResponse:
    """Retrieve evidence and generate a cited medical answer."""
    top_k = request.top_k or TOP_K
    try:
        chunks = retrieve(request.query, top_k=top_k)
        generated = generate_answer(request.query, chunks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status = 503 if "empty" in message.lower() or "GROQ_API_KEY" in message else 500
        raise HTTPException(status_code=status, detail=message) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Chat pipeline failed: {exc}") from exc

    return QueryResponse(
        answer=generated["answer"],
        references=[SourceMetadata(**item) for item in generated["references"]],
        sources=[RetrievedChunk(**chunk) for chunk in chunks],
        model=generated.get("model", ""),
    )
