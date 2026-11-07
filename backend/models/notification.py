"""Notification and NotificationPreference models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    """In-app notification delivered to a specific user."""

    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    alert_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("alerts.alert_id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="LOW")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipment_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("shipments.shipment_id", ondelete="SET NULL")
    )
    action_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped = relationship("User")
    alert: Mapped = relationship("Alert")
    shipment: Mapped = relationship("Shipment")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_notif_severity",
        ),
    )


class NotificationPreference(Base, TimestampMixin):
    """Per-user notification channel and type preferences."""

    __tablename__ = "notification_preferences"

    pref_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False,
        doc="IN_APP | EMAIL | SMS — only IN_APP is active until external providers configured")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_severity: Mapped[str] = mapped_column(String(20), nullable=False, default="LOW")
