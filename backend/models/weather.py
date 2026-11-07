"""WeatherEvent model.

Stores discrete weather disruption windows used by the ETA engine to add
delay factors to predicted arrival times.  Does NOT claim real-time weather
integration — these are either synthetic (Phase 4) or manually entered.

Weather-type → delay_factor documentation:
  NORMAL       1.00  (no impact)
  RAIN         1.15  (+15% transit time)
  HEAVY_RAIN   1.35  (+35%)
  STORM        1.60  (+60%)
  FLOOD        2.00  (+100%)
  EXTREME_HEAT 1.10  (+10%)
  FOG          1.25  (+25%)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class WeatherEvent(Base, TimestampMixin):
    __tablename__ = "weather_events"

    weather_event_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weather_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[int] = mapped_column(nullable=False, doc="1=low 2=medium 3=high 4=critical")
    # Multiplier applied to base transit time; derived from weather_type.
    delay_factor: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "weather_type IN ('NORMAL','RAIN','HEAVY_RAIN','STORM','FLOOD','EXTREME_HEAT','FOG')",
            name="ck_weather_type",
        ),
        CheckConstraint("severity BETWEEN 1 AND 4", name="ck_weather_severity"),
        CheckConstraint("delay_factor >= 1.0", name="ck_weather_delay_factor"),
        CheckConstraint("end_time > start_time", name="ck_weather_time_order"),
    )
