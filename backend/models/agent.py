"""AgentDecision — records every agentic AI tool execution and recommendation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class AgentDecision(Base, TimestampMixin):
    __tablename__ = "agent_decisions"

    agent_decision_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    request_text: Mapped[str] = mapped_column(Text, nullable=False,
        doc="The natural-language request sent to the agent")
    tools_used: Mapped[str | None] = mapped_column(Text,
        doc="JSON array of {tool, input, output} dicts")
    recommendation: Mapped[str | None] = mapped_column(Text)
    supporting_evidence: Mapped[str | None] = mapped_column(Text,
        doc="JSON summary of key data points used")
    policy_sources: Mapped[str | None] = mapped_column(Text,
        doc="JSON array of RAG citation objects")
    confidence_note: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False,
        default="PENDING_REVIEW")
    approved_by: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    model_version: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        CheckConstraint(
            "approval_status IN ('PENDING_REVIEW','APPROVED','REJECTED','NOT_REQUIRED')",
            name="ck_agent_approval_status",
        ),
    )
