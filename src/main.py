"""FastAPI application entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import HOST, PORT, ensure_asset_directories

ensure_asset_directories()

app = FastAPI(
    title="Medical RAG System",
    description="Polio Guidelines Assistant with grounded retrieval and citations.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    """Simple service banner."""
    return {
        "service": "Medical RAG System",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host=HOST, port=PORT, reload=True)
