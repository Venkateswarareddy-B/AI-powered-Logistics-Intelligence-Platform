"""DataQualityIssue — labelled anomalies from the validation pipeline.

Anomalies are NEVER silently deleted. They are labelled and preserved
with full traceability so they can be excluded from ML training safely.
The ground_truth source (generator label) is stored separately and is
NEVER used as a model input feature.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


ISSUE_TYPES = (
    "INGESTION_TIME_CONFUSION", "IMPOSSIBLE_ROUTE_ORDER", "FUTURE_EVENT_LEAKAGE",
    "DELIVERED_STILL_IN_TRANSIT", "DUPLICATE_TRACKING_EVENT", "DELAYED_SCAN",
    "ROUTE_CHANGE_ANOMALY", "MISSING_TRACKING_EVENT", "FACILITY_OVERLOAD",
    "SEVERE_WEATHER_DISRUPTION", "FK_VIOLATION", "ENUM_VIOLATION",
    "DATE_INCONSISTENCY", "DUPLICATE_PK", "OTHER",
)


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    issue_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False,
        doc="e.g. TrackingEvent, Shipment")
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    shipment_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    # Ground truth label from the generator — never fed to ML models
    ground_truth_label: Mapped[str | None] = mapped_column(String(100))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pipeline_run_id: Mapped[str | None] = mapped_column(String(80))
    is_resolved: Mapped[bool] = mapped_column(default=False, nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"issue_type IN {ISSUE_TYPES}", name="ck_dqi_issue_type"
        ),
        CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_dqi_severity",
        ),
    )
