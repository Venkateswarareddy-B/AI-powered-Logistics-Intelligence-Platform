"""Alert model.

Alerts are generated from actual database records and configured rules.
Duplicate alerts for the same unresolved condition are prevented by the
alert service (Phase 15).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

ALERT_TYPES = (
    "HIGH_DELAY_RISK", "SLA_AT_RISK", "SLA_BREACH",
    "FACILITY_CONGESTION", "WEATHER_DISRUPTION", "ROUTE_DEVIATION",
    "MISSING_SCAN", "LATE_EVENT", "DATA_QUALITY_ERROR",
)


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False,
        doc="LOW | MEDIUM | HIGH | CRITICAL")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    shipment_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="SET NULL")
    )
    facility_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="SET NULL")
    )
    carrier_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("carriers.carrier_id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN",
        doc="OPEN | ACKNOWLEDGED | RESOLVED")
    acknowledged_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Dedup key: alerts with the same dedup_key and status=OPEN are not recreated
    dedup_key: Mapped[str | None] = mapped_column(String(300))
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)

    shipment: Mapped = relationship("Shipment")
    facility: Mapped = relationship("Facility")
    carrier: Mapped = relationship("Carrier")

    __table_args__ = (
        CheckConstraint(
            f"alert_type IN {ALERT_TYPES}", name="ck_alert_type"
        ),
        CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_alert_severity"
        ),
        CheckConstraint(
            "status IN ('OPEN','ACKNOWLEDGED','RESOLVED')", name="ck_alert_status"
        ),
    )
