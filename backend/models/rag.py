"""RAGDocument and RAGIngestionJob — knowledge base document management.

Documents are created/uploaded by administrators and chunked + embedded
into ChromaDB. The platform uses local Sentence Transformer embeddings —
never OpenAI embeddings.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class RAGDocument(Base, TimestampMixin):
    __tablename__ = "rag_documents"

    document_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    document_name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False,
        doc="SLA_POLICY | CARRIER_POLICY | WEATHER_SOP | FACILITY_SOP | "
            "DELAY_HANDLING | ROUTE_CHANGE | ESCALATION | OTHER")
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    content_text: Mapped[str | None] = mapped_column(Text,
        doc="Full text content (for text/markdown docs)")
    file_path: Mapped[str | None] = mapped_column(String(500),
        doc="Relative path to uploaded file (PDF/DOCX)")
    file_type: Mapped[str | None] = mapped_column(String(20),
        doc="TEXT | PDF | DOCX | MARKDOWN")
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False,
        default="PENDING",
        doc="PENDING | PROCESSING | ACTIVE | FAILED | ARCHIVED")
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    vector_collection: Mapped[str | None] = mapped_column(String(200),
        doc="ChromaDB collection name")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[str | None] = mapped_column(Text, doc="JSON blob")

    ingestion_jobs: Mapped[list[RAGIngestionJob]] = relationship(
        "RAGIngestionJob", back_populates="document", order_by="RAGIngestionJob.created_at"
    )

    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('PENDING','PROCESSING','ACTIVE','FAILED','ARCHIVED')",
            name="ck_rag_status",
        ),
        CheckConstraint(
            "category IN ('SLA_POLICY','CARRIER_POLICY','WEATHER_SOP','FACILITY_SOP',"
            "'DELAY_HANDLING','ROUTE_CHANGE','ESCALATION','OTHER')",
            name="ck_rag_category",
        ),
    )

    def __repr__(self) -> str:
        return f"<RAGDocument {self.document_id} {self.document_name[:40]}>"


class RAGIngestionJob(Base):
    """Tracks each (re-)ingestion run for a document."""

    __tablename__ = "rag_ingestion_jobs"

    job_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("rag_documents.document_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="QUEUED")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chunks_created: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    document: Mapped[RAGDocument] = relationship("RAGDocument", back_populates="ingestion_jobs")

    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED')",
            name="ck_rag_job_status",
        ),
    )
