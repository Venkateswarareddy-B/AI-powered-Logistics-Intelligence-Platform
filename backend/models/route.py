"""Route model.

A route defines the standard path between two facilities including
base transit time and distance. Routes are referenced by shipments and
used in ETA calculations and what-if analysis.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Route(Base, TimestampMixin):
    __tablename__ = "routes"

    route_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    route_name: Mapped[str] = mapped_column(String(200), nullable=False)
    origin_facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="RESTRICT"), nullable=False
    )
    destination_facility_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("facilities.facility_id", ondelete="RESTRICT"), nullable=False
    )
    distance_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    base_transit_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    origin_facility: Mapped["Facility"] = relationship(
        "Facility", foreign_keys=[origin_facility_id], back_populates="outbound_routes"
    )
    destination_facility: Mapped["Facility"] = relationship(
        "Facility", foreign_keys=[destination_facility_id], back_populates="inbound_routes"
    )
    shipments: Mapped[list] = relationship("Shipment", back_populates="route")

    __table_args__ = (
        CheckConstraint("distance_km > 0", name="ck_route_distance"),
        CheckConstraint("base_transit_hours > 0", name="ck_route_transit"),
        CheckConstraint(
            "origin_facility_id != destination_facility_id",
            name="ck_route_different_facilities",
        ),
    )

    def __repr__(self) -> str:
        return f"<Route {self.route_id} {self.origin_facility_id}->{self.destination_facility_id}>"
