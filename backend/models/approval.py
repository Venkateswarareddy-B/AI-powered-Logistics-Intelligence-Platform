"""HumanApproval — formal approval records for sensitive operational actions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class HumanApproval(Base, TimestampMixin):
    __tablename__ = "human_approvals"

    approval_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_decision_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("agent_decisions.agent_decision_id", ondelete="SET NULL")
    )
    shipment_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="SET NULL")
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False,
        doc="e.g. ROUTE_CHANGE, ESCALATION, CARRIER_SWAP")
    recommendation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    decided_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    model_version: Mapped[str | None] = mapped_column(String(100))
    estimated_time_saving_hours: Mapped[float | None] = mapped_column()
    estimated_cost_impact: Mapped[float | None] = mapped_column()
    estimated_risk_reduction_pct: Mapped[float | None] = mapped_column()

    shipment: Mapped = relationship("Shipment")
    agent_decision: Mapped = relationship("AgentDecision")

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','MORE_INFO_REQUESTED')",
            name="ck_approval_status",
        ),
    )
