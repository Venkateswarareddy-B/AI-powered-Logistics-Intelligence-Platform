"""AuditLog — immutable record of important system operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AuditLog(Base):
    """Immutable audit record. Rows are never updated or deleted."""

    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False,
        doc="e.g. LOGIN, APPROVE_ROUTE_CHANGE, GENERATE_REPORT")
    entity_type: Mapped[str | None] = mapped_column(String(100),
        doc="e.g. Shipment, Alert, RouteChange")
    entity_id: Mapped[str | None] = mapped_column(String(80))
    decision: Mapped[str | None] = mapped_column(String(50),
        doc="APPROVED | REJECTED | ACKNOWLEDGED | RESOLVED")
    reason: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(50))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    extra_data: Mapped[str | None] = mapped_column(Text, doc="JSON blob for extra context")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
