"""RAG retrieval and citation generation.

Searches ChromaDB for relevant policy chunks and returns them with
full citation information (document name, section/chunk reference, source excerpt).
Never invents citations — if no supporting content is found, says so.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag.embeddings.embedder import embed_query
from rag.vectorstore.chroma_client import query as chroma_query

log = logging.getLogger("rag.retrieval.search")


def search_policies(
    db: Session,
    query_text: str,
    n_results: int = 5,
) -> list[dict]:
    """Search policy documents for relevant content.

    Returns a list of citation dicts with:
      - document_id, document_name, category
      - chunk_index, chunk_total
      - source_excerpt (the retrieved text)
      - distance (similarity score)
    """
    # Embed the query
    query_embedding = embed_query(query_text)

    # Search ChromaDB
    results = chroma_query(query_embedding, n_results=n_results)
    if not results:
        return []

    # Enrich with document metadata from PostgreSQL
    citations = []
    for r in results:
        doc_id = r["metadata"].get("document_id")
        doc = db.execute(text("""
            SELECT document_name, category, version
            FROM rag_documents WHERE document_id = :did
        """), {"did": doc_id}).mappings().fetchone()

        citations.append({
            "document_id": doc_id,
            "document_name": doc["document_name"] if doc else "Unknown",
            "category": doc["category"] if doc else "Unknown",
            "version": doc["version"] if doc else "1.0",
            "chunk_index": r["metadata"].get("chunk_index", 0),
            "chunk_total": r["metadata"].get("chunk_total", 0),
            "source_excerpt": r["text"][:500],
            "distance": round(float(r["distance"]), 4),
        })

    return citations


def format_citations(citations: list[dict]) -> str:
    """Format citations for display in the AI assistant response."""
    if not citations:
        return "No supporting policy information was found."
    parts = []
    for i, c in enumerate(citations, 1):
        parts.append(
            f"[{i}] {c['document_name']} (v{c['version']}, {c['category']}) "
            f"— chunk {c['chunk_index']+1}/{c['chunk_total']}\n"
            f"    \"{c['source_excerpt'][:200]}...\""
        )
    return "\n".join(parts)
