"""RagWebSource — tracks website sources added to the knowledge base."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, TimestampMixin


class RagWebSource(Base, TimestampMixin):
    """A website URL added as a knowledge base source."""
    __tablename__ = "rag_web_sources"

    source_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="OTHER")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    document_id: Mapped[str | None] = mapped_column(String(80))
    page_title: Mapped[str | None] = mapped_column(String(300))
    word_count: Mapped[int | None] = mapped_column(Integer)
    chunks_created: Mapped[int | None] = mapped_column(Integer)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    added_by: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_rws_status",
        ),
    )
