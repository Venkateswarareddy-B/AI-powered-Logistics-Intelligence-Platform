"""ServiceLevel reference table.

Defines SLA parameters: maximum delivery hours and allowed delay hours.
These values drive SLA evaluation in Phase 9.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class ServiceLevel(Base, TimestampMixin):
    __tablename__ = "service_levels"

    service_level_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Maximum hours from pickup to delivery before SLA is considered breached
    maximum_delivery_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    # Grace period before AT_RISK flips to BREACHED
    allowed_delay_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    shipments: Mapped[list] = relationship("Shipment", back_populates="service_level")

    __table_args__ = (
        CheckConstraint(
            "service_level_id IN ('STANDARD','EXPRESS','SAME_DAY','PRIORITY')",
            name="ck_sl_id",
        ),
        CheckConstraint("maximum_delivery_hours > 0", name="ck_sl_max_hours"),
        CheckConstraint("allowed_delay_hours >= 0", name="ck_sl_allowed_delay"),
    )

    def __repr__(self) -> str:
        return f"<ServiceLevel {self.service_level_id} max={self.maximum_delivery_hours}h>"
