"""CarrierPerformance and FacilityPerformance — calculated aggregates.

These are period-snapshot rows calculated from actual shipment and event
history by the ETL pipeline (Phase 6). Values are NEVER independently
invented; each field documents its source calculation.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey,
    Integer, Numeric, String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class CarrierPerformance(Base, TimestampMixin):
    __tablename__ = "carrier_performance"

    perf_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    carrier_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("carriers.carrier_id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_shipments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    on_time_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # on_time_count / total_shipments
    on_time_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    average_delay_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    late_scan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # late_scan_count / total_shipments
    late_scan_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    route_change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route_change_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    # Composite score 0-100; formula documented in Phase 12
    carrier_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    carrier: Mapped = relationship("Carrier", back_populates="performance_records")

    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_cp_period"),
        CheckConstraint("total_shipments >= 0", name="ck_cp_total"),
        CheckConstraint("on_time_count >= 0", name="ck_cp_on_time"),
    )


class FacilityPerformance(Base, TimestampMixin):
    __tablename__ = "facility_performance"

    perf_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    average_queue_length: Mapped[float | None] = mapped_column(Numeric(8, 2))
    average_processing_time_minutes: Mapped[float | None] = mapped_column(Numeric(8, 2))
    # Derived: avg_queue / capacity * 100
    average_utilization_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    # Proportion of delayed shipments that passed through this facility
    delay_contribution_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    total_shipments_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    facility: Mapped = relationship("Facility", back_populates="performance_records")

    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_fp_period"),
    )
