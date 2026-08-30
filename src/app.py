"""Streamlit chat UI for the Polio Guidelines Assistant."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    DOCUMENTS_DIR,
    GROQ_API_KEY,
    GROQ_MODEL,
    TOP_K,
    ensure_asset_directories,
)
from src.generation.generator import generate_answer
from src.ingestion.ingest import ingest
from src.retrieval.retriever import retrieve
from src.vectorstore.vector_store import VectorStore

st.set_page_config(
    page_title="Polio Guidelines Assistant",
    page_icon="🩺",
    layout="wide",
)

TEAM_MEMBERS: list[dict[str, str]] = [
    {
        "name": "Yahya Mahmoud Abdelfadeel",
        "role": "Team Leader",
        "initials": "YA",
    },
    {
        "name": "Mhmd Shahyn",
        "role": "Team Member",
        "initials": "MS",
    },
    {
        "name": "Ahmed Hendawy",
        "role": "Team Member",
        "initials": "AH",
    },
    {
        "name": "Mohamed Salah",
        "role": "Team Member",
        "initials": "ML",
    },
    {
        "name": "Hossam Shiref",
        "role": "Team Member",
        "initials": "HS",
    },
]


def _inject_styles() -> None:
    """Apply compact professional styling for the team credits section."""
    st.markdown(
        """
        <style>
            .team-kicker {
                letter-spacing: 0.14em;
                text-transform: uppercase;
                font-size: 0.72rem;
                font-weight: 600;
                opacity: 0.72;
                margin-bottom: 0.15rem;
            }
            .team-grid {
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 0.7rem;
                margin: 0.85rem 0 1.25rem 0;
            }
            .team-card {
                border: 1px solid rgba(250, 250, 250, 0.12);
                background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
                border-radius: 14px;
                padding: 0.9rem 0.75rem 1rem 0.75rem;
                text-align: center;
                min-height: 148px;
            }
            .team-card.leader {
                border-color: rgba(46, 164, 122, 0.55);
                box-shadow: 0 0 0 1px rgba(46, 164, 122, 0.18);
            }
            .team-avatar {
                width: 42px;
                height: 42px;
                margin: 0 auto 0.65rem auto;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                background: rgba(46, 164, 122, 0.18);
                color: #7dceb0;
            }
            .team-card.leader .team-avatar {
                background: rgba(46, 164, 122, 0.32);
                color: #d8ffe9;
            }
            .team-name {
                font-size: 0.86rem;
                font-weight: 650;
                line-height: 1.25;
                margin-bottom: 0.35rem;
            }
            .team-role {
                font-size: 0.72rem;
                opacity: 0.72;
            }
            .team-card.leader .team-role {
                color: #7dceb0;
                opacity: 1;
                font-weight: 600;
            }
            @media (max-width: 1100px) {
                .team-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }
            @media (max-width: 640px) {
                .team-grid { grid-template-columns: 1fr; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_team_banner() -> None:
    """Render a professional project-team section on the main page."""
    cards = []
    for member in TEAM_MEMBERS:
        leader_class = " leader" if member["role"] == "Team Leader" else ""
        cards.append(
            (
                f'<article class="team-card{leader_class}">'
                f'<div class="team-avatar">{member["initials"]}</div>'
                f'<div class="team-name">{member["name"]}</div>'
                f'<div class="team-role">{member["role"]}</div>'
                "</article>"
            )
        )
    st.markdown(
        '<div class="team-kicker">Project Team</div>'
        '<div class="team-grid">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def _load_stats() -> dict:
    try:
        return VectorStore().collection_stats()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "points_count": 0, "collection_name": COLLECTION_NAME}


def _pdf_count() -> int:
    ensure_asset_directories()
    return len(list(DOCUMENTS_DIR.glob("*.pdf")))


def _render_sidebar() -> None:
    stats = _load_stats()
    pdfs = _pdf_count()
    points = int(stats.get("points_count") or 0)

    st.sidebar.title("System Control")
    st.sidebar.markdown("Polio Guidelines RAG")

    if stats.get("error"):
        st.sidebar.error(f"Vector store error: {stats['error']}")
    elif points > 0:
        st.sidebar.success("Index ready")
    else:
        st.sidebar.warning("Index is empty")

    st.sidebar.metric("Indexed chunks", points)
    st.sidebar.metric("PDF files", pdfs)
    st.sidebar.caption(f"Collection: `{stats.get('collection_name', COLLECTION_NAME)}`")
    st.sidebar.caption(f"LLM: `{GROQ_MODEL}`")
    st.sidebar.caption("Groq key: " + ("configured" if GROQ_API_KEY else "missing"))

    st.sidebar.divider()
    st.sidebar.subheader("Hyperparameters")
    st.sidebar.write(f"Chunk Size: **{CHUNK_SIZE}**")
    st.sidebar.write(f"Overlap: **{CHUNK_OVERLAP}**")
    st.sidebar.write(f"Top-K: **{TOP_K}**")
    st.sidebar.write("Embedding: `all-MiniLM-L6-v2` (384d)")

    st.sidebar.divider()
    st.sidebar.subheader("Documents")
    st.sidebar.caption(str(DOCUMENTS_DIR))
    if st.sidebar.button("Re-Index Documents", use_container_width=True, type="primary"):
        with st.spinner("Parsing PDFs, embedding chunks, and updating Qdrant..."):
            try:
                result = ingest(recreate=True)
                st.session_state["last_ingest"] = result
                st.sidebar.success(f"Indexed {result['chunks_indexed']} chunks from {len(result['documents'])} PDF(s).")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.sidebar.error(str(exc))

    if st.sidebar.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Project Team")
    st.sidebar.caption("Medical RAG System")
    for member in TEAM_MEMBERS:
        label = f"**{member['name']}**"
        if member["role"] == "Team Leader":
            st.sidebar.markdown(f"{label}  \n:green[{member['role']}]")
        else:
            st.sidebar.markdown(f"{label}  \n{member['role']}")


def _answer_query(query: str) -> dict:
    chunks = retrieve(query, top_k=TOP_K)
    generated = generate_answer(query, chunks)
    return {
        "answer": generated["answer"],
        "references": generated["references"],
        "sources": chunks,
        "model": generated.get("model", GROQ_MODEL),
    }


def main() -> None:
    ensure_asset_directories()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    _inject_styles()
    _render_sidebar()

    st.title("Polio Guidelines Assistant")
    st.caption(
        "Answers are grounded in indexed PDFs only. Every medical claim should include a citation "
        "in the form `[Document_Name.pdf, Page 12]`."
    )
    _render_team_banner()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("sources"):
                _render_sources(message["sources"], message.get("references", []))

    prompt = st.chat_input("Ask about OPV vs IPV, symptoms, transmission, or contraindications...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Retrieving guidelines and generating a cited answer..."):
                result = _answer_query(prompt)
            st.markdown(result["answer"])
            _render_sources(result["sources"], result["references"])
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result["sources"],
                    "references": result["references"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            st.error(error)
            st.session_state.messages.append({"role": "assistant", "content": f"**Error:** {error}"})


def _render_sources(sources: list[dict], references: list[dict]) -> None:
    if references:
        citations = " · ".join(item.get("citation", "") for item in references)
        st.markdown(f"**References:** {citations}")

    with st.expander(f"Top-{TOP_K} retrieved source chunks", expanded=False):
        if not sources:
            st.write("No source chunks were returned.")
            return
        for index, chunk in enumerate(sources, start=1):
            metadata = chunk.get("metadata") or {}
            score = chunk.get("score")
            score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
            st.markdown(
                f"**{index}. {metadata.get('document_name', 'unknown')} | Page {metadata.get('page_no', '?')}**  \n"
                f"Similarity score: `{score_text}`"
            )
            st.write(chunk.get("text", ""))
            st.divider()


if __name__ == "__main__":
    main()
else:
    # Streamlit executes the script at import time.
    main()
