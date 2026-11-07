"""Facility and FacilityQueue models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey,
    Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Facility(Base, TimestampMixin):
    __tablename__ = "facilities"

    facility_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    facility_name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="India")
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    operating_hours: Mapped[str | None] = mapped_column(String(100), doc="e.g. '06:00-22:00'")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text)

    queue_records: Mapped[list[FacilityQueue]] = relationship("FacilityQueue", back_populates="facility")
    outbound_routes: Mapped[list] = relationship(
        "Route", foreign_keys="Route.origin_facility_id", back_populates="origin_facility"
    )
    inbound_routes: Mapped[list] = relationship(
        "Route", foreign_keys="Route.destination_facility_id", back_populates="destination_facility"
    )
    performance_records: Mapped[list] = relationship("FacilityPerformance", back_populates="facility")

    __table_args__ = (
        CheckConstraint(
            "facility_type IN ('WAREHOUSE','HUB','DISTRIBUTION_CENTER','SORTING_CENTER','DELIVERY_CENTER')",
            name="ck_facility_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE','MAINTENANCE')",
            name="ck_facility_status",
        ),
        CheckConstraint("capacity > 0", name="ck_facility_capacity"),
    )

    def __repr__(self) -> str:
        return f"<Facility {self.facility_id} {self.facility_name}>"


class FacilityQueue(Base):
    """Point-in-time queue snapshot for a facility.

    Utilization is always *calculated* from queue_length / capacity — never
    stored independently — to prevent inconsistencies.
    """

    __tablename__ = "facility_queues"

    queue_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    queue_length: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_processing_time_minutes: Mapped[float | None] = mapped_column(Numeric(8, 2))
    # Stored for fast querying; must equal queue_length / capacity * 100
    utilization_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    facility: Mapped[Facility] = relationship("Facility", back_populates="queue_records")

    __table_args__ = (
        CheckConstraint("queue_length >= 0", name="ck_fq_queue_length"),
        CheckConstraint("capacity > 0", name="ck_fq_capacity"),
        CheckConstraint(
            "utilization_pct >= 0 AND utilization_pct <= 100",
            name="ck_fq_utilization",
        ),
    )
