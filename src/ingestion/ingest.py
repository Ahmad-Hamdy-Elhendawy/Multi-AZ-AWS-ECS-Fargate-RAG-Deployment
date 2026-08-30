"""End-to-end ingestion orchestration: parse, chunk, embed, and index."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION_NAME, DOCUMENTS_DIR, ensure_asset_directories
from src.ingestion.chunker import chunk_documents
from src.ingestion.embedder import Embedder
from src.ingestion.parser import parse_documents
from src.vectorstore.vector_store import VectorStore


def ingest(recreate: bool = True) -> dict[str, Any]:
    """Run the full PDF-to-Qdrant pipeline.

    Args:
        recreate: When True, rebuild the collection so deleted PDFs do not linger.

    Returns:
        Summary statistics for API and CLI callers.
    """
    ensure_asset_directories()
    print(f"[ingest] Scanning PDFs in {DOCUMENTS_DIR}")
    pages = parse_documents(DOCUMENTS_DIR)
    print(f"[ingest] Parsed {len(pages)} pages")

    chunks = chunk_documents(pages, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    print(f"[ingest] Created {len(chunks)} chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    embedder = Embedder()
    texts = [chunk["text"] for chunk in chunks]
    print("[ingest] Encoding chunk embeddings...")
    embeddings = embedder.embed_documents(texts)

    store = VectorStore()
    if recreate:
        print(f"[ingest] Recreating collection '{COLLECTION_NAME}'")
        store.recreate_collection()

    upserted = store.upsert_chunks(chunks, embeddings)
    stats = store.collection_stats()
    print(f"[ingest] Upserted {upserted} vectors into {stats['collection_name']}")

    documents = sorted({page["metadata"]["document_name"] for page in pages})
    return {
        "status": "ok",
        "documents": documents,
        "pages_parsed": len(pages),
        "chunks_indexed": upserted,
        "collection": stats,
    }


if __name__ == "__main__":
    try:
        summary = ingest()
        print("[ingest] Completed successfully:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
    except Exception as exc:  # noqa: BLE001
        print(f"[ingest] Failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
