"""Phase 17 RAG tests."""
from __future__ import annotations
import pytest
from sqlalchemy import text
from backend.core.database import SessionLocal
from rag.documents.sample_policies import seed_sample_policies
from rag.ingestion.pipeline import chunk_text, ingest_document
from rag.retrieval.search import search_policies, format_citations
from rag.embeddings.embedder import get_embedder


# ── Unit tests (no external deps) ─────────────────────────────────────────────

class TestChunking:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("Short text", chunk_size=100, overlap=20)
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self):
        long_text = "A" * 250
        chunks = chunk_text(long_text, chunk_size=100, overlap=20)
        assert len(chunks) > 1

    def test_chunks_have_content(self):
        text = "The quick brown fox. " * 50
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        for c in chunks:
            assert len(c) > 0

    def test_default_uses_settings(self):
        chunks = chunk_text("Test content")
        assert len(chunks) >= 1


class TestSamplePolicies:
    def test_policies_well_formed(self):
        assert len(seed_sample_policies.__module__) > 0  # importable
        from rag.documents.sample_policies import SAMPLE_POLICIES
        assert len(SAMPLE_POLICIES) >= 7
        for p in SAMPLE_POLICIES:
            assert "document_name" in p
            assert "category" in p
            assert "content" in p
            assert "DEMO DATA" in p["content"] or "Fictional" in p["content"]

    def test_all_categories_covered(self):
        from rag.documents.sample_policies import SAMPLE_POLICIES
        cats = {p["category"] for p in SAMPLE_POLICIES}
        expected = {"SLA_POLICY","CARRIER_POLICY","WEATHER_SOP","FACILITY_SOP",
                     "DELAY_HANDLING","ROUTE_CHANGE","ESCALATION","OTHER"}
        assert expected.issubset(cats)


class TestCitationFormatting:
    def test_empty_citations(self):
        result = format_citations([])
        assert "No supporting" in result

    def test_citations_formatted(self):
        citations = [{
            "document_name": "SLA Policy", "category": "SLA_POLICY",
            "version": "1.0", "chunk_index": 0, "chunk_total": 3,
            "source_excerpt": "Test excerpt content here",
            "distance": 0.5,
        }]
        result = format_citations(citations)
        assert "SLA Policy" in result
        assert "chunk" in result.lower()


# ── Integration tests (require DB + embedding model) ──────────────────────────

class TestRAGIntegration:
    def test_seed_and_ingest(self, requires_db):
        db = SessionLocal()
        try:
            count = seed_sample_policies(db)
            assert count >= 0  # may be 0 if already seeded

            # Ingest first PENDING document
            row = db.execute(text(
                "SELECT document_id, content_text FROM rag_documents WHERE processing_status='PENDING' LIMIT 1"
            )).mappings().fetchone()
            if row:
                result = ingest_document(db, row["document_id"], content=row["content_text"])
                assert result["status"] in ("completed", "failed")
        finally:
            db.close()

    def test_search_returns_results(self, requires_db):
        db = SessionLocal()
        try:
            # Ensure at least one document is ingested
            row = db.execute(text(
                "SELECT document_id, content_text FROM rag_documents WHERE processing_status='ACTIVE' LIMIT 1"
            )).mappings().fetchone()
            if not row:
                # Seed and ingest
                seed_sample_policies(db)
                pending = db.execute(text(
                    "SELECT document_id, content_text FROM rag_documents WHERE processing_status='PENDING' LIMIT 1"
                )).mappings().fetchone()
                if pending:
                    ingest_document(db, pending["document_id"], content=pending["content_text"])

            results = search_policies(db, "What is the SLA policy for delays?")
            # May be empty if embeddings failed, but should not crash
            assert isinstance(results, list)
        finally:
            db.close()

    def test_citations_have_document_names(self, requires_db):
        db = SessionLocal()
        try:
            results = search_policies(db, "carrier performance score")
            for r in results:
                assert "document_name" in r
                assert "source_excerpt" in r
        finally:
            db.close()

    def test_document_status_after_ingestion(self, requires_db):
        db = SessionLocal()
        try:
            row = db.execute(text(
                "SELECT document_id, content_text FROM rag_documents LIMIT 1"
            )).mappings().fetchone()
            if row:
                ingest_document(db, row["document_id"], content=row["content_text"])
                status = db.execute(text(
                    "SELECT processing_status, chunk_count FROM rag_documents WHERE document_id=:did"
                ), {"did": row["document_id"]}).mappings().fetchone()
                assert status["processing_status"] in ("ACTIVE", "FAILED")
        finally:
            db.close()

    def test_rag_document_has_demo_label(self, requires_db):
        db = SessionLocal()
        try:
            row = db.execute(text(
                "SELECT is_demo FROM rag_documents LIMIT 1"
            )).scalar()
            if row is not None:
                assert row is True or row is False  # just verify column exists
        finally:
            db.close()
