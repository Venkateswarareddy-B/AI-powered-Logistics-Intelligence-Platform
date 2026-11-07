"""TrackingEvent model — append-only, never overwritten.

Event IDs: EVT-<shipment_id>-NNNNNN

Two timestamps are stored separately:
  event_time    — when the event physically occurred
  ingestion_time — when the system received/recorded it

This separation enables:
  - Late-arriving event detection
  - Future-data leakage prevention (only events with ingestion_time <=
    prediction_time are used as model features in Phase 8+)
  - Duplicate detection
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


EVENT_TYPES = (
    "PICKED_UP", "DEPARTED_FACILITY", "ARRIVED_FACILITY", "IN_TRANSIT",
    "DELAYED", "ROUTE_CHANGED", "OUT_FOR_DELIVERY", "DELIVERED",
)


class TrackingEvent(Base):
    """Immutable tracking event record.

    Once inserted, rows are never updated or deleted (history is sacred).
    Duplicates are detected by the data engineering pipeline (Phase 5).
    """

    __tablename__ = "tracking_events"

    event_id: Mapped[str] = mapped_column(String(60), primary_key=True,
        doc="Format: EVT-SHP-YYYY-NNNNNN-NNNNNN")
    shipment_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="When the event physically occurred"
    )
    ingestion_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="When the system received the event (may be later than event_time)"
    )
    facility_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="SET NULL")
    )
    location: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100), doc="e.g. 'SCANNER','MANUAL','API'")
    is_duplicate: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_late_arrival: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    shipment: Mapped = relationship("Shipment", back_populates="tracking_events")
    facility: Mapped = relationship("Facility")

    __table_args__ = (
        CheckConstraint(
            f"event_type IN {EVENT_TYPES}", name="ck_event_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<TrackingEvent {self.event_id} type={self.event_type}>"
