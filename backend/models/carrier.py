"""Carrier model."""

from __future__ import annotations

from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Carrier(Base, TimestampMixin):
    __tablename__ = "carriers"

    carrier_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    carrier_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    carrier_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    base_delay_factor: Mapped[float] = mapped_column(
        Numeric(5, 3), default=1.0, nullable=False,
        doc="Multiplier applied to base transit time (1.0 = no extra delay)"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    shipments: Mapped[list] = relationship("Shipment", back_populates="carrier")
    performance_records: Mapped[list] = relationship("CarrierPerformance", back_populates="carrier")

    def __repr__(self) -> str:
        return f"<Carrier {self.carrier_code}>"
