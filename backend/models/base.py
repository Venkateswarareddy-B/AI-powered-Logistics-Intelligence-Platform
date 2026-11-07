"""Declarative base and shared mixins.

All ORM models inherit from ``Base``.  Shared behaviour (timestamps, soft
delete, deterministic IDs) is factored into mixins so it is defined once.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base."""
    # Allow bare relationship annotations (e.g. ``Mapped = relationship(...)``)
    # without requiring every back-reference to be fully typed.
    # Individual column annotations still use strict ``Mapped[T]`` typing.
    __allow_unmapped__ = True


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns to any model.

    Both are stored as timezone-aware UTC timestamps.
    ``updated_at`` is refreshed automatically by the DB on every UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
