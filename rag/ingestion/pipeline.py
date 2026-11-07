"""Document ingestion pipeline: Load → Chunk → Embed → Store in ChromaDB.

Supports TEXT, MARKDOWN, and PDF file types.
Creates a RAGIngestionJob record for traceability.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from rag.embeddings.embedder import embed_texts
from rag.vectorstore.chroma_client import add_chunks, delete_by_document

settings = get_settings()
log = logging.getLogger("rag.ingestion.pipeline")


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: Full document text.
        chunk_size: Max chars per chunk (default from settings).
        overlap: Overlap chars between chunks (default from settings).
    """
    cs = chunk_size or settings.RAG_CHUNK_SIZE
    ov = overlap or settings.RAG_CHUNK_OVERLAP
    if len(text) <= cs:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + cs
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - ov
    return chunks


def ingest_document(
    db: Session,
    document_id: str,
    content: str | None = None,
    file_path: str | None = None,
    file_type: str = "TEXT",
) -> dict:
    """Ingest a document into ChromaDB.

    Returns dict with status, chunks_created, and error info.
    """
    # Create ingestion job record
    job_id = f"RAGJOB-{document_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    started_at = datetime.now(timezone.utc)

    db.execute(text("""
        INSERT INTO rag_ingestion_jobs (
            job_id, document_id, status, started_at,
            embedding_model, created_at
        ) VALUES (
            :jid, :did, 'RUNNING', :st,
            :model, :now
        ) ON CONFLICT (job_id) DO NOTHING
    """), {
        "jid": job_id, "did": document_id, "st": started_at,
        "model": settings.RAG_EMBEDDING_MODEL, "now": started_at,
    })
    db.commit()

    try:
        # Get content
        if content is None and file_path:
            content = _read_file(file_path, file_type)

        if not content or not content.strip():
            raise ValueError("No content to ingest")

        # Delete existing chunks for this document (re-ingestion)
        delete_by_document(document_id)

        # Chunk
        chunks = chunk_text(content)
        log.info("document %s: %d chunks", document_id, len(chunks))

        # Embed
        embeddings = embed_texts(chunks)

        # Build chunk records
        chunk_records = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}-chunk-{i:04d}"
            chunk_records.append({
                "id": chunk_id,
                "text": chunk,
                "metadata": {
                    "document_id": document_id,
                    "chunk_index": i,
                    "chunk_total": len(chunks),
                    "embedding_model": settings.RAG_EMBEDDING_MODEL,
                },
            })

        # Store
        added = add_chunks(chunk_records, embeddings)

        # Update document status
        db.execute(text("""
            UPDATE rag_documents
            SET processing_status='ACTIVE', chunk_count=:cc,
                embedding_model=:model, vector_collection='yottaflex_policies',
                updated_at=:now
            WHERE document_id=:did
        """), {
            "cc": added, "model": settings.RAG_EMBEDDING_MODEL,
            "did": document_id, "now": datetime.now(timezone.utc),
        })

        # Update job
        completed_at = datetime.now(timezone.utc)
        db.execute(text("""
            UPDATE rag_ingestion_jobs
            SET status='COMPLETED', completed_at=:ct, chunks_created=:cc
            WHERE job_id=:jid
        """), {"ct": completed_at, "cc": added, "jid": job_id})
        db.commit()

        return {"status": "completed", "chunks_created": added, "job_id": job_id}

    except Exception as exc:
        log.error("ingestion failed for %s: %s", document_id, exc)
        db.execute(text("""
            UPDATE rag_ingestion_jobs
            SET status='FAILED', completed_at=:now, error_message=:err
            WHERE job_id=:jid
        """), {"now": datetime.now(timezone.utc), "err": str(exc)[:500], "jid": job_id})

        db.execute(text("""
            UPDATE rag_documents SET processing_status='FAILED', updated_at=:now
            WHERE document_id=:did
        """), {"now": datetime.now(timezone.utc), "did": document_id})
        db.commit()
        return {"status": "failed", "error": str(exc)[:500], "job_id": job_id}


def _read_file(path: str, file_type: str) -> str:
    """Read content from a file based on its type."""
    if file_type == "PDF":
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
    elif file_type == "DOCX":
        from docx import Document
        doc = Document(path)
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    else:  # TEXT or MARKDOWN
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
