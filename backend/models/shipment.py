"""Shipment and ShipmentLeg models.

Shipment IDs follow the deterministic format: SHP-YYYY-NNNNNN
Leg IDs: LEG-<shipment_id>-NN

Status lifecycle:
  CREATED → PICKED_UP → IN_TRANSIT → AT_FACILITY
         → OUT_FOR_DELIVERY → DELIVERED
  (CANCELLED and EXCEPTION can occur from most states)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


SHIPMENT_STATUSES = (
    "CREATED", "PICKED_UP", "IN_TRANSIT", "AT_FACILITY",
    "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "EXCEPTION",
)


class Shipment(Base, TimestampMixin):
    __tablename__ = "shipments"

    shipment_id: Mapped[str] = mapped_column(String(30), primary_key=True,
        doc="Format: SHP-YYYY-NNNNNN")
    carrier_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("carriers.carrier_id", ondelete="RESTRICT"), nullable=False
    )
    service_level_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("service_levels.service_level_id", ondelete="RESTRICT"), nullable=False
    )
    route_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False
    )
    origin_facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="RESTRICT"), nullable=False
    )
    destination_facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="RESTRICT"), nullable=False
    )
    planned_ship_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    promised_delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_delivery_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CREATED")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="NORMAL")
    weight_kg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2))
    sla_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ON_TIME",
        doc="ON_TIME | AT_RISK | BREACHED — recalculated by SLA monitor"
    )
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    carrier: Mapped = relationship("Carrier", back_populates="shipments")
    service_level: Mapped = relationship("ServiceLevel", back_populates="shipments")
    route: Mapped = relationship("Route", back_populates="shipments")
    origin_facility: Mapped = relationship(
        "Facility", foreign_keys=[origin_facility_id]
    )
    destination_facility: Mapped = relationship(
        "Facility", foreign_keys=[destination_facility_id]
    )
    legs: Mapped[list[ShipmentLeg]] = relationship(
        "ShipmentLeg", back_populates="shipment", order_by="ShipmentLeg.leg_sequence"
    )
    tracking_events: Mapped[list] = relationship(
        "TrackingEvent", back_populates="shipment", order_by="TrackingEvent.event_time"
    )
    eta_estimates: Mapped[list] = relationship(
        "ETAEstimate", back_populates="shipment", order_by="ETAEstimate.prediction_time"
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN {SHIPMENT_STATUSES}", name="ck_shipment_status"
        ),
        CheckConstraint(
            "priority IN ('LOW','NORMAL','HIGH','CRITICAL')", name="ck_shipment_priority"
        ),
        CheckConstraint(
            "sla_status IN ('ON_TIME','AT_RISK','BREACHED')", name="ck_shipment_sla"
        ),
        CheckConstraint(
            "origin_facility_id != destination_facility_id",
            name="ck_shipment_different_facilities",
        ),
        CheckConstraint(
            "promised_delivery_time > planned_ship_time",
            name="ck_shipment_promised_after_planned",
        ),
    )

    def __repr__(self) -> str:
        return f"<Shipment {self.shipment_id} status={self.status}>"


class ShipmentLeg(Base, TimestampMixin):
    """One segment of a multi-leg shipment.

    Leg IDs: LEG-<shipment_id>-NN (zero-padded sequence).
    """

    __tablename__ = "shipment_legs"

    leg_id: Mapped[str] = mapped_column(String(50), primary_key=True,
        doc="Format: LEG-SHP-YYYY-NNNNNN-NN")
    shipment_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False
    )
    leg_sequence: Mapped[int] = mapped_column(Integer, nullable=False, doc="1-based")
    origin_facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="RESTRICT"), nullable=False
    )
    destination_facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="RESTRICT"), nullable=False
    )
    carrier_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("carriers.carrier_id", ondelete="RESTRICT"), nullable=False
    )
    planned_departure: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_arrival: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2))

    shipment: Mapped[Shipment] = relationship("Shipment", back_populates="legs")

    __table_args__ = (
        UniqueConstraint("shipment_id", "leg_sequence", name="uq_leg_sequence"),
        CheckConstraint("leg_sequence >= 1", name="ck_leg_sequence_positive"),
        CheckConstraint(
            "planned_arrival > planned_departure", name="ck_leg_arrival_after_departure"
        ),
        CheckConstraint(
            "origin_facility_id != destination_facility_id",
            name="ck_leg_different_facilities",
        ),
    )

    def __repr__(self) -> str:
        return f"<ShipmentLeg {self.leg_id} seq={self.leg_sequence}>"
