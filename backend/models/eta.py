"""ETAEstimate — prediction history (append-only snapshots).

ID format: ETA-<shipment_id>-YYYYMMDDHHmm

Every time a prediction is calculated (rule-based or ML) a new row is
inserted. Previous estimates are NEVER overwritten. This preserves full
prediction history and enables ETA accuracy evaluation.

feature_cutoff_time enforces the future-data leakage contract:
  only events with ingestion_time <= feature_cutoff_time were used.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class ETAEstimate(Base):
    __tablename__ = "eta_estimates"

    eta_estimate_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False
    )
    prediction_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="Wall-clock time when this prediction was generated"
    )
    feature_cutoff_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="Only data with ingestion_time <= this were used — no future leakage"
    )
    predicted_eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predicted_remaining_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    delay_probability: Mapped[float | None] = mapped_column(
        Numeric(5, 4), doc="0.0 – 1.0 probability of delay"
    )
    model_version: Mapped[str] = mapped_column(String(100), nullable=False,
        doc="e.g. 'rule_based_v1' or 'gradient_boosting_v1.2'")
    model_type: Mapped[str] = mapped_column(String(50), nullable=False,
        doc="RULE_BASED | LINEAR | RANDOM_FOREST | GRADIENT_BOOSTING | XGBOOST")
    base_travel_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    carrier_delay_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    weather_delay_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    facility_queue_delay_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    route_change_delay_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    shipment: Mapped = relationship("Shipment", back_populates="eta_estimates")

    __table_args__ = (
        CheckConstraint(
            "delay_probability IS NULL OR (delay_probability >= 0 AND delay_probability <= 1)",
            name="ck_eta_delay_prob",
        ),
        CheckConstraint(
            "feature_cutoff_time <= prediction_time",
            name="ck_eta_cutoff_before_prediction",
        ),
        CheckConstraint(
            "model_type IN ('RULE_BASED','LINEAR','RANDOM_FOREST','GRADIENT_BOOSTING','XGBOOST')",
            name="ck_eta_model_type",
        ),
    )
