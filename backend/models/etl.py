"""ETL staging and feature tables.

Three tiers following the Bronze → Silver → Gold architecture:

  bronze_tracking_events   — raw copy of tracking_events + audit metadata
  bronze_shipment_snapshot — denormalised shipment + carrier + route snapshot
  silver_tracking_events   — cleaned events with lag calculation + anomaly flag
  silver_shipments         — cleaned shipments with derived delay fields
  gold_shipment_features   — ML-ready feature rows (one per usable shipment)

All Bronze and Silver tables are idempotent (ON CONFLICT DO NOTHING/UPDATE).
Gold is updated on every ETL run.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class BronzeTrackingEvent(Base):
    """Raw copy of tracking_events with Bronze audit columns."""

    __tablename__ = "bronze_tracking_events"

    event_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    facility_id: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_late_arrival: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bronze_ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bronze_run_id: Mapped[str | None] = mapped_column(String(50))
    bronze_source: Mapped[str | None] = mapped_column(String(100))
    bronze_is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BronzeShipmentSnapshot(Base):
    """Denormalised snapshot of shipments + carrier + route + service level."""

    __tablename__ = "bronze_shipment_snapshot"

    shipment_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    carrier_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    service_level_id: Mapped[str] = mapped_column(String(50), nullable=False)
    route_id: Mapped[str] = mapped_column(String(50), nullable=False)
    origin_facility_id: Mapped[str] = mapped_column(String(50), nullable=False)
    destination_facility_id: Mapped[str] = mapped_column(String(50), nullable=False)
    planned_ship_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    promised_delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_delivery_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2))
    sla_status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    carrier_name: Mapped[str | None] = mapped_column(String(200))
    carrier_code: Mapped[str | None] = mapped_column(String(20))
    base_delay_factor: Mapped[float | None] = mapped_column(Numeric(5, 3))
    route_name: Mapped[str | None] = mapped_column(String(200))
    distance_km_route: Mapped[float | None] = mapped_column(Numeric(10, 2))
    base_transit_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    service_level_name: Mapped[str | None] = mapped_column(String(100))
    maximum_delivery_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    allowed_delay_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    bronze_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bronze_run_id: Mapped[str | None] = mapped_column(String(50))
    bronze_is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SilverTrackingEvent(Base):
    """Cleaned and enriched tracking events."""

    __tablename__ = "silver_tracking_events"

    event_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    facility_id: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_late_arrival: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ingestion_lag_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_usable_for_ml: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bronze_run_id: Mapped[str | None] = mapped_column(String(50))
    silver_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SilverShipment(Base):
    """Cleaned shipments with derived delay and transit fields."""

    __tablename__ = "silver_shipments"

    shipment_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    carrier_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    service_level_id: Mapped[str] = mapped_column(String(50), nullable=False)
    route_id: Mapped[str] = mapped_column(String(50), nullable=False)
    origin_facility_id: Mapped[str] = mapped_column(String(50), nullable=False)
    destination_facility_id: Mapped[str] = mapped_column(String(50), nullable=False)
    planned_ship_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    promised_delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_delivery_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2))
    sla_status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    carrier_name: Mapped[str | None] = mapped_column(String(200))
    base_delay_factor: Mapped[float | None] = mapped_column(Numeric(5, 3))
    base_transit_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    maximum_delivery_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    allowed_delay_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    total_transit_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))
    is_delayed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delay_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_usable_for_ml: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bronze_run_id: Mapped[str | None] = mapped_column(String(50))
    silver_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GoldShipmentFeature(Base):
    """ML-ready feature row. One row per usable delivered shipment.

    IMPORTANT: ground_truth labels are NOT stored in this table.
    The is_anomaly column is included so ML pipelines can filter explicitly.
    """

    __tablename__ = "gold_shipment_features"

    shipment_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    carrier_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    service_level_id: Mapped[str] = mapped_column(String(50), nullable=False)
    service_level_encoded: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    base_transit_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    base_delay_factor: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    max_weather_delay_factor: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    max_facility_utilization_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    late_event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    total_transit_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))
    delay_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))
    delay_label: Mapped[int] = mapped_column(Integer, nullable=False,
        doc="0=on_time 1=delayed — binary classification target")
    remaining_delivery_hours: Mapped[float | None] = mapped_column(Numeric(10, 4),
        doc="Regression target for ETA model")
    sla_status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False,
        doc="Explicitly included so ML can filter; ground_truth NOT stored here")
    gold_computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
