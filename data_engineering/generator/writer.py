"""Batched, idempotent PostgreSQL writer using SQLAlchemy Core.

Uses INSERT ... ON CONFLICT DO NOTHING so the generator is safe to re-run
without duplicating rows. Processes records in configurable batch sizes to
avoid memory pressure on large datasets (50k+ shipments).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.core.database import engine
from backend.models import (
    AgentDecision, Alert, AuditLog, Base, Carrier, CarrierPerformance,
    DataQualityIssue, DelayReason, ETAEstimate, Facility, FacilityPerformance,
    FacilityQueue, HumanApproval, ModelVersion, Notification,
    NotificationPreference, PredictionExplanation, RAGDocument, RAGIngestionJob,
    Role, Route, RouteChange, ServiceLevel, Shipment, ShipmentLeg,
    TrackingEvent, User, WeatherEvent,
)

log = logging.getLogger("data_engineering.generator.writer")

# Map table name → SQLAlchemy Table object
_TABLE_MAP = {t: Base.metadata.tables[t] for t in Base.metadata.tables}


def _bulk_upsert(table_name: str, rows: list[dict], batch_size: int) -> int:
    """Insert rows with ON CONFLICT DO NOTHING. Returns count inserted."""
    if not rows:
        return 0
    table = _TABLE_MAP[table_name]
    inserted = 0
    with engine.begin() as conn:
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            stmt = pg_insert(table).values(batch).on_conflict_do_nothing()
            result = conn.execute(stmt)
            inserted += result.rowcount
    log.info("upserted table=%s rows=%d inserted=%d", table_name, len(rows), inserted)
    return inserted


def write_all(
    data: dict[str, list[dict]],
    batch_size: int = 500,
) -> dict[str, int]:
    """Write all generated data in dependency order. Returns {table: inserted}."""
    # Order matters: FKs must be satisfied
    write_order = [
        "roles",
        "service_levels",
        "carriers",
        "facilities",
        "routes",
        "weather_events",
        "shipments",
        "shipment_legs",
        "tracking_events",
        "facility_queues",
        "data_quality_issues",
    ]
    counts: dict[str, int] = {}
    for table_name in write_order:
        rows = data.get(table_name, [])
        if rows:
            counts[table_name] = _bulk_upsert(table_name, rows, batch_size)
        else:
            counts[table_name] = 0
    return counts
