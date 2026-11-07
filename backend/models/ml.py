"""ModelVersion and PredictionExplanation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class ModelVersion(Base, TimestampMixin):
    """Registry of trained ML model versions."""

    __tablename__ = "model_versions"

    model_version_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    training_seed: Mapped[int | None] = mapped_column()
    training_dataset_description: Mapped[str | None] = mapped_column(Text)
    feature_names: Mapped[str | None] = mapped_column(Text, doc="JSON array")
    # Regression metrics (ETA model)
    mae: Mapped[float | None] = mapped_column(Numeric(10, 4))
    rmse: Mapped[float | None] = mapped_column(Numeric(10, 4))
    r2: Mapped[float | None] = mapped_column(Numeric(8, 6))
    # Classification metrics (delay model)
    accuracy: Mapped[float | None] = mapped_column(Numeric(8, 6))
    precision: Mapped[float | None] = mapped_column(Numeric(8, 6))
    recall: Mapped[float | None] = mapped_column(Numeric(8, 6))
    f1: Mapped[float | None] = mapped_column(Numeric(8, 6))
    roc_auc: Mapped[float | None] = mapped_column(Numeric(8, 6))
    pr_auc: Mapped[float | None] = mapped_column(Numeric(8, 6))
    artifact_path: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "model_type IN ('ETA','DELAY')", name="ck_mv_model_type"
        ),
    )


class PredictionExplanation(Base):
    """SHAP-derived explanation for a single prediction.

    Values are derived from the actual explanation method — never fabricated.
    """

    __tablename__ = "prediction_explanations"

    explanation_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    eta_estimate_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("eta_estimates.eta_estimate_id", ondelete="CASCADE")
    )
    shipment_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False
    )
    model_version_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("model_versions.model_version_id", ondelete="SET NULL")
    )
    prediction_type: Mapped[str] = mapped_column(String(20), nullable=False,
        doc="ETA | DELAY")
    # Serialised as JSON: [{feature, shap_value, display_impact_pct}, ...]
    shap_values_json: Mapped[str | None] = mapped_column(Text)
    base_value: Mapped[float | None] = mapped_column(Numeric(10, 4))
    prediction_value: Mapped[float | None] = mapped_column(Numeric(10, 4))
    explanation_method: Mapped[str] = mapped_column(String(50), nullable=False,
        default="SHAP_TREE", doc="SHAP_TREE | SHAP_LINEAR | RULE_BASED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    eta_estimate: Mapped = relationship("ETAEstimate")
    shipment: Mapped = relationship("Shipment")

    __table_args__ = (
        CheckConstraint(
            "prediction_type IN ('ETA','DELAY')", name="ck_pe_prediction_type"
        ),
    )
