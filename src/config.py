"""Application configuration loaded from environment variables and path constants."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = BASE_DIR.parent
DOCUMENTS_DIR: Path = BASE_DIR / "assets" / "documents"
QDRANT_PATH: Path = BASE_DIR / "assets" / "qdrant"

CHUNK_SIZE: int = 600
CHUNK_OVERLAP: int = 50
TOP_K: int = 3
VECTOR_SIZE: int = 384
COLLECTION_NAME: str = "polio_medical_docs"
EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
# llama-3.3-70b-versatile was shut down by Groq on 2026-08-16.
GROQ_MODEL: str = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b").strip()
GROQ_MODEL_FALLBACKS: tuple[str, ...] = (
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
)
GROQ_API_KEY: str | None = (os.getenv("GROQ_API_KEY") or "").strip() or None

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))


def require_groq_api_key() -> str:
    """Return the Groq API key or raise a clear configuration error."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return GROQ_API_KEY


def ensure_asset_directories() -> None:
    """Create documents and Qdrant storage directories if they do not exist."""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
