"""Bronze layer jobs.

Bronze is the raw-data staging layer. We stamp every row with:
  - bronze_ingested_at  — wall-clock time this pipeline ran
  - bronze_run_id       — pipeline run identifier
  - bronze_source       — originating table name
  - bronze_is_anomaly   — True if a data_quality_issue exists for this row

Design:
  - We write into a dedicated ``bronze_tracking_events`` table.
  - Shipment and carrier data is captured via a view-like snapshot written
    to ``bronze_shipment_snapshot``.
  - ON CONFLICT DO NOTHING keeps the job idempotent.
  - Anomalies are PRESERVED and labelled — never discarded.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from data_engineering.pipelines.base import ETLJob, JobResult

log = logging.getLogger("data_engineering.ingestion.bronze")


class BronzeTrackingEventsJob(ETLJob):
    """Copy tracking_events → bronze_tracking_events with anomaly flags."""

    name = "bronze_tracking_events"
    stage = "BRONZE"

    def _execute(self, db, result: JobResult) -> None:
        # Count source rows
        source_count = db.execute(
            text("SELECT COUNT(*) FROM tracking_events")
        ).scalar()
        result.rows_read = int(source_count)

        # Upsert into bronze table
        db.execute(text("""
            INSERT INTO bronze_tracking_events (
                event_id, shipment_id, event_type,
                event_time, ingestion_time, facility_id,
                location, description, source,
                is_duplicate, is_late_arrival, is_demo,
                bronze_ingested_at, bronze_run_id, bronze_source,
                bronze_is_anomaly, created_at
            )
            SELECT
                te.event_id,
                te.shipment_id,
                te.event_type,
                te.event_time,
                te.ingestion_time,
                te.facility_id,
                te.location,
                te.description,
                te.source,
                te.is_duplicate,
                te.is_late_arrival,
                te.is_demo,
                NOW() AS bronze_ingested_at,
                :run_id AS bronze_run_id,
                'tracking_events' AS bronze_source,
                EXISTS (
                    SELECT 1 FROM data_quality_issues dqi
                    WHERE dqi.entity_id = te.event_id
                      AND dqi.entity_type = 'TrackingEvent'
                ) AS bronze_is_anomaly,
                te.created_at
            FROM tracking_events te
            ON CONFLICT (event_id) DO NOTHING
        """), {"run_id": result.extra.get("run_id", "UNKNOWN")})
        db.commit()

        written = db.execute(
            text("SELECT COUNT(*) FROM bronze_tracking_events")
        ).scalar()
        result.rows_written = int(written)
        log.info("bronze_tracking_events: read=%d written=%d",
                 result.rows_read, result.rows_written)


class BronzeShipmentSnapshotJob(ETLJob):
    """Snapshot shipments + carrier + route metadata → bronze_shipment_snapshot."""

    name = "bronze_shipment_snapshot"
    stage = "BRONZE"

    def _execute(self, db, result: JobResult) -> None:
        source_count = db.execute(text("SELECT COUNT(*) FROM shipments")).scalar()
        result.rows_read = int(source_count)

        db.execute(text("""
            INSERT INTO bronze_shipment_snapshot (
                shipment_id, carrier_id, service_level_id, route_id,
                origin_facility_id, destination_facility_id,
                planned_ship_time, promised_delivery_time, actual_delivery_time,
                status, priority, weight_kg, distance_km, sla_status,
                is_demo, carrier_name, carrier_code, base_delay_factor,
                route_name, distance_km_route, base_transit_hours,
                service_level_name, maximum_delivery_hours, allowed_delay_hours,
                bronze_ingested_at, bronze_run_id, bronze_is_anomaly,
                created_at, updated_at
            )
            SELECT
                s.shipment_id,
                s.carrier_id,
                s.service_level_id,
                s.route_id,
                s.origin_facility_id,
                s.destination_facility_id,
                s.planned_ship_time,
                s.promised_delivery_time,
                s.actual_delivery_time,
                s.status,
                s.priority,
                s.weight_kg,
                s.distance_km,
                s.sla_status,
                s.is_demo,
                c.carrier_name,
                c.carrier_code,
                c.base_delay_factor,
                r.route_name,
                r.distance_km,
                r.base_transit_hours,
                sl.name,
                sl.maximum_delivery_hours,
                sl.allowed_delay_hours,
                NOW(),
                :run_id,
                EXISTS (
                    SELECT 1 FROM data_quality_issues dqi
                    WHERE dqi.shipment_id = s.shipment_id
                ),
                s.created_at,
                s.updated_at
            FROM shipments s
            JOIN carriers c ON s.carrier_id = c.carrier_id
            JOIN routes r ON s.route_id = r.route_id
            JOIN service_levels sl ON s.service_level_id = sl.service_level_id
            ON CONFLICT (shipment_id) DO NOTHING
        """), {"run_id": result.extra.get("run_id", "UNKNOWN")})
        db.commit()

        written = db.execute(
            text("SELECT COUNT(*) FROM bronze_shipment_snapshot")
        ).scalar()
        result.rows_written = int(written)
        log.info("bronze_shipment_snapshot: read=%d written=%d",
                 result.rows_read, result.rows_written)
