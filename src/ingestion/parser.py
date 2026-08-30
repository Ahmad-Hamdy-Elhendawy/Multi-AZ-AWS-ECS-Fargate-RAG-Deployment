"""PDF parsing with page-level medical metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.config import DOCUMENTS_DIR


def parse_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """Extract text from every page of a single PDF.

    Args:
        pdf_path: Absolute path to a PDF file.

    Returns:
        A list of page dictionaries with text and metadata.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to open PDF '{pdf_path.name}': {exc}") from exc

    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to extract text from '{pdf_path.name}' page {index}: {exc}"
            ) from exc

        cleaned = " ".join(text.split())
        if not cleaned:
            continue

        pages.append(
            {
                "text": cleaned,
                "metadata": {
                    "document_name": pdf_path.name,
                    "page_no": index,
                },
            }
        )
    return pages


def parse_documents(documents_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read all PDF files from the documents directory.

    Args:
        documents_dir: Optional override for the documents folder.

    Returns:
        Flattened list of page documents with metadata.

    Raises:
        FileNotFoundError: If the documents directory does not exist or has no PDFs.
    """
    source_dir = documents_dir or DOCUMENTS_DIR
    if not source_dir.exists():
        raise FileNotFoundError(
            f"Documents directory does not exist: {source_dir}. "
            "Place medical PDFs in src/assets/documents/."
        )

    pdf_files = sorted(source_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in {source_dir}. "
            "Add Polio guideline PDFs before running ingestion."
        )

    parsed: list[dict[str, Any]] = []
    for pdf_path in pdf_files:
        parsed.extend(parse_pdf(pdf_path))

    if not parsed:
        raise ValueError(
            "PDFs were found but no extractable text was recovered. "
            "Ensure the files are text-based (not scanned images without OCR)."
        )
    return parsed
