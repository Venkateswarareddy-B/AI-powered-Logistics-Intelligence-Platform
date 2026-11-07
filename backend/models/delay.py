"""DelayReason and RouteChange models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey,
    Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class DelayReason(Base, TimestampMixin):
    """Labelled delay reason attached to a shipment.

    Derived from actual delivery outcomes and documented business rules —
    never randomly fabricated.  IDs: DLY-YYYY-NNNNNN
    """

    __tablename__ = "delay_reasons"

    delay_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False
    )
    reason_category: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_detail: Mapped[str | None] = mapped_column(Text)
    delay_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        CheckConstraint(
            "reason_category IN ("
            "'WEATHER','FACILITY_CONGESTION','CARRIER_ISSUE','ROUTE_CHANGE',"
            "'CUSTOMS','MECHANICAL','TRAFFIC','DEMAND_SURGE','MISSING_SCAN','OTHER')",
            name="ck_delay_reason_category",
        ),
        CheckConstraint("delay_hours > 0", name="ck_delay_hours_positive"),
    )


class RouteChange(Base, TimestampMixin):
    """Records a diversion from the original planned route."""

    __tablename__ = "route_changes"

    change_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False
    )
    original_route_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False
    )
    new_route_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False
    )
    change_reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_additional_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    estimated_additional_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    approved_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )

    shipment: Mapped = relationship("Shipment")
    original_route: Mapped = relationship("Route", foreign_keys=[original_route_id])
    new_route: Mapped = relationship("Route", foreign_keys=[new_route_id])

    __table_args__ = (
        CheckConstraint(
            "original_route_id != new_route_id", name="ck_route_change_different"
        ),
    )
