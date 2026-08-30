"""Groq-backed answer generation with strict citation rules."""

from __future__ import annotations

from typing import Any

from groq import Groq

from src.config import GROQ_MODEL, GROQ_MODEL_FALLBACKS, require_groq_api_key

SYSTEM_PROMPT = """You are a certified medical assistant specializing in Polio (poliomyelitis) guidelines.
Your scope includes research findings, vaccination protocols (OPV vs IPV), symptoms, transmission, and contraindications.

Rules you MUST follow:
1. Rely EXCLUSIVELY on the provided context. Do NOT extrapolate, speculate, or use prior medical knowledge.
2. If the answer is not in the context, explicitly state: "The requested information is not available in the provided medical documents."
3. Enforce citations inline for every medical statement, using this exact format: [Document_Name.pdf, Page 12].
4. Never invent document names, page numbers, dosages, or contraindications.
5. Prefer concise, clinically precise language. Do not give personalized treatment advice beyond the source text.
6. If sources conflict, report the conflict and cite both documents.
"""


def _format_context(retrieved_chunks: list[dict[str, Any]]) -> str:
    """Render retrieved chunks into a numbered context block for the LLM."""
    blocks: list[str] = []
    for index, chunk in enumerate(retrieved_chunks, start=1):
        metadata = chunk.get("metadata") or {}
        document_name = metadata.get("document_name", "unknown.pdf")
        page_no = metadata.get("page_no", "?")
        score = chunk.get("score")
        score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
        blocks.append(
            f"[Source {index}] Document: {document_name} | Page: {page_no} | Similarity: {score_text}\n"
            f"{chunk.get('text', '').strip()}"
        )
    return "\n\n".join(blocks)


def _references(retrieved_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate source metadata while preserving retrieval rank."""
    seen: set[tuple[str, int]] = set()
    references: list[dict[str, Any]] = []
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata") or {}
        document_name = str(metadata.get("document_name") or "unknown.pdf")
        page_no = int(metadata.get("page_no") or 0)
        key = (document_name, page_no)
        if key in seen:
            continue
        seen.add(key)
        references.append(
            {
                "document_name": document_name,
                "page_no": page_no,
                "score": float(chunk.get("score") or 0.0),
                "citation": f"[{document_name} | Page: {page_no}]",
            }
        )
    return references


def generate_answer(query: str, retrieved_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Synthesize a grounded medical answer from retrieved chunks.

    Args:
        query: The clinician or user question.
        retrieved_chunks: Top-k chunks from the retriever.

    Returns:
        Dictionary with ``answer`` and ``references``.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("Query must not be empty.")
    if not retrieved_chunks:
        return {
            "answer": "The requested information is not available in the provided medical documents.",
            "references": [],
        }

    api_key = require_groq_api_key()
    context = _format_context(retrieved_chunks)
    user_prompt = (
        f"Question:\n{cleaned}\n\n"
        f"Context from indexed medical documents:\n{context}\n\n"
        "Answer using only the context. Cite every claim."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    try:
        client = Groq(api_key=api_key)
        completion, used_model = _complete_with_fallback(client, messages)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Groq generation failed: {exc}") from exc

    answer = (completion.choices[0].message.content or "").strip()
    if not answer:
        raise RuntimeError("Groq returned an empty answer.")

    return {
        "answer": answer,
        "references": _references(retrieved_chunks),
        "model": used_model,
    }


def _candidate_models() -> list[str]:
    """Preferred Groq model first, then current public replacements."""
    models: list[str] = []
    for name in (GROQ_MODEL, *GROQ_MODEL_FALLBACKS):
        if name and name not in models:
            models.append(name)
    return models


def _complete_with_fallback(client: Groq, messages: list[dict[str, str]]) -> tuple[Any, str]:
    """Call Groq chat completions, skipping retired/unavailable model IDs."""
    last_error: Exception | None = None
    for model_name in _candidate_models():
        try:
            completion = client.chat.completions.create(
                model=model_name,
                temperature=0.1,
                max_tokens=1024,
                messages=messages,
            )
            return completion, model_name
        except Exception as exc:  # noqa: BLE001
            message = str(exc).lower()
            if "model_not_found" in message or "does not exist" in message or "404" in message:
                last_error = exc
                continue
            raise
    raise RuntimeError(
        "No available Groq model succeeded. "
        f"Tried: {', '.join(_candidate_models())}. Last error: {last_error}"
    ) from last_error
