"""RAG knowledge base API endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user
from rag.documents.sample_policies import seed_sample_policies
from rag.ingestion.pipeline import ingest_document
from rag.retrieval.search import search_policies, format_citations

router = APIRouter(prefix="/api/rag", tags=["rag"])


class CreateDocRequest(BaseModel):
    document_name: str
    category: str
    content_text: str
    version: str = "1.0"


class SearchRequest(BaseModel):
    query: str
    n_results: int = 5


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT document_id, document_name, category, version,
               processing_status, chunk_count, is_active, is_demo,
               created_at, updated_at
        FROM rag_documents ORDER BY created_at DESC
    """)).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post("/documents")
def create_document(
    req: CreateDocRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    import uuid
    from datetime import datetime, timezone
    doc_id = f"RAGDOC-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO rag_documents (
            document_id, document_name, category, version,
            content_text, file_type, processing_status,
            is_active, is_demo, created_by, created_at, updated_at
        ) VALUES (
            :did, :dname, :cat, :ver,
            :content, 'TEXT', 'PENDING',
            TRUE, FALSE, :cby, :now, :now
        )
    """), {
        "did": doc_id, "dname": req.document_name, "cat": req.category,
        "ver": req.version, "content": req.content_text,
        "cby": user["user_id"], "now": now,
    })
    db.commit()
    # Auto-ingest
    result = ingest_document(db, doc_id, content=req.content_text)
    return {"document_id": doc_id, "ingestion": result}


@router.post("/documents/seed-samples")
def seed_samples(db: Session = Depends(get_db), user=Depends(get_current_user)):
    count = seed_sample_policies(db, created_by=user["user_id"])
    # Ingest all PENDING documents
    pending = db.execute(text(
        "SELECT document_id, content_text FROM rag_documents WHERE processing_status='PENDING'"
    )).mappings().fetchall()
    ingested = 0
    for row in pending:
        r = dict(row)
        result = ingest_document(db, r["document_id"], content=r["content_text"])
        if result.get("status") == "completed":
            ingested += 1
    return {"seeded": count, "ingested": ingested}


@router.post("/documents/{document_id}/reingest")
def reingest_document(
    document_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    row = db.execute(text(
        "SELECT content_text FROM rag_documents WHERE document_id=:did"
    ), {"did": document_id}).mappings().fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    result = ingest_document(db, document_id, content=row["content_text"])
    return result


@router.post("/documents/{document_id}/deactivate")
def deactivate_document(
    document_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    from datetime import datetime, timezone
    db.execute(text("""
        UPDATE rag_documents SET is_active=FALSE, processing_status='ARCHIVED',
               updated_at=:now WHERE document_id=:did
    """), {"did": document_id, "now": datetime.now(timezone.utc)})
    db.commit()
    return {"status": "deactivated", "document_id": document_id}


@router.post("/search")
def search(req: SearchRequest, db: Session = Depends(get_db), _=Depends(get_current_user)):
    citations = search_policies(db, req.query, n_results=req.n_results)
    return {
        "query": req.query,
        "results_count": len(citations),
        "citations": citations,
        "formatted": format_citations(citations),
    }


# ── Website source management ─────────────────────────────────────────────────

class AddWebSourceRequest(BaseModel):
    source_name: str
    url: str
    category: str = "LOGISTICS"


@router.get("/web-sources")
def list_web_sources(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from backend.models.rag_source import RagWebSource  # noqa
    rows = db.execute(text("""
        SELECT source_id, source_name, url, category, status,
               page_title, word_count, chunks_created, last_synced_at,
               error_message, created_at
        FROM rag_web_sources ORDER BY created_at DESC
    """)).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post("/web-sources")
def add_web_source(
    req: AddWebSourceRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    import uuid
    from datetime import datetime, timezone
    source_id = f"WS-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO rag_web_sources (
            source_id, source_name, url, category, status,
            added_by, created_at, updated_at
        ) VALUES (
            :sid, :name, :url, :cat, 'PENDING',
            :uid, :now, :now
        ) ON CONFLICT (url) DO UPDATE SET
            source_name=EXCLUDED.source_name,
            category=EXCLUDED.category,
            status='PENDING',
            updated_at=EXCLUDED.updated_at
    """), {
        "sid": source_id, "name": req.source_name, "url": req.url,
        "cat": req.category, "uid": user["user_id"], "now": now,
    })
    db.commit()
    return {"source_id": source_id, "status": "PENDING"}


@router.post("/web-sources/{source_id}/ingest")
def ingest_web_source(
    source_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    from datetime import datetime, timezone
    from rag.ingestion.web_scraper import ingest_website

    row = db.execute(text("""
        SELECT source_id, source_name, url, category
        FROM rag_web_sources WHERE source_id=:sid
    """), {"sid": source_id}).mappings().fetchone()
    if not row:
        raise HTTPException(404, "Web source not found")

    row = dict(row)
    now = datetime.now(timezone.utc)

    # Mark as processing
    db.execute(text("UPDATE rag_web_sources SET status='PROCESSING', updated_at=:now WHERE source_id=:sid"),
               {"now": now, "sid": source_id})
    db.commit()

    # Ingest
    result = ingest_website(db, source_id, row["url"], row["source_name"], row["category"])

    # Update status
    if result.get("status") == "completed":
        db.execute(text("""
            UPDATE rag_web_sources
            SET status='COMPLETED', document_id=:did, page_title=:title,
                word_count=:wc, chunks_created=:cc, last_synced_at=:now,
                error_message=NULL, updated_at=:now
            WHERE source_id=:sid
        """), {
            "did": result.get("doc_id"), "title": result.get("title", "")[:300],
            "wc": result.get("word_count", 0), "cc": result.get("chunks_created", 0),
            "now": now, "sid": source_id,
        })
    else:
        db.execute(text("""
            UPDATE rag_web_sources
            SET status='FAILED', error_message=:err, updated_at=:now
            WHERE source_id=:sid
        """), {"err": result.get("error", "Unknown error")[:500], "now": now, "sid": source_id})
    db.commit()
    return {**result, "source_id": source_id}


@router.delete("/web-sources/{source_id}")
def delete_web_source(
    source_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    # Also remove from ChromaDB if a document_id exists
    row = db.execute(text(
        "SELECT document_id FROM rag_web_sources WHERE source_id=:sid"
    ), {"sid": source_id}).scalar()
    if row:
        try:
            from rag.vectorstore.chroma_client import delete_by_document
            delete_by_document(row)
        except Exception:
            pass
        db.execute(text("DELETE FROM rag_documents WHERE document_id=:did"), {"did": row})
    db.execute(text("DELETE FROM rag_web_sources WHERE source_id=:sid"), {"sid": source_id})
    db.commit()
    return {"status": "deleted", "source_id": source_id}
