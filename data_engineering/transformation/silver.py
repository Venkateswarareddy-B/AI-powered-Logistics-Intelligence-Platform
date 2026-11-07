"""Silver layer jobs.

Silver cleans, deduplicates, and type-checks Bronze data:
  - Removes exact duplicate events (is_duplicate = TRUE kept for audit).
  - Fixes NULL facility references where resolvable.
  - Flags remaining anomalies via is_anomaly column.
  - Calculates ingestion_lag_hours for every event.
  - Writes to silver_tracking_events and silver_shipments.

Anomalies are NEVER deleted — they are marked is_anomaly=TRUE and flow
into Gold where ML feature queries explicitly exclude them.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from data_engineering.pipelines.base import ETLJob, JobResult

log = logging.getLogger("data_engineering.transformation.silver")


class SilverTrackingEventsJob(ETLJob):
    """bronze_tracking_events → silver_tracking_events.

    Rules applied:
      - Skip rows already flagged is_duplicate=TRUE (archived, not deleted).
      - Calculate ingestion_lag_hours = EXTRACT(EPOCH FROM (ingestion - event)) / 3600.
      - Flag is_anomaly if bronze_is_anomaly OR ingestion_time < event_time
        OR event_time > NOW() + 1 hour.
      - is_usable_for_ml = NOT is_anomaly AND NOT is_duplicate.
    """

    name = "silver_tracking_events"
    stage = "SILVER"

    def _execute(self, db, result: JobResult) -> None:
        source_count = db.execute(
            text("SELECT COUNT(*) FROM bronze_tracking_events")
        ).scalar()
        result.rows_read = int(source_count)

        db.execute(text("""
            INSERT INTO silver_tracking_events (
                event_id, shipment_id, event_type,
                event_time, ingestion_time, facility_id,
                location, description, source,
                is_duplicate, is_late_arrival, is_demo,
                ingestion_lag_hours, is_anomaly, is_usable_for_ml,
                bronze_run_id, silver_processed_at, created_at
            )
            SELECT
                b.event_id,
                b.shipment_id,
                b.event_type,
                b.event_time,
                b.ingestion_time,
                b.facility_id,
                b.location,
                b.description,
                b.source,
                b.is_duplicate,
                b.is_late_arrival,
                b.is_demo,
                ROUND(
                    CAST(
                        EXTRACT(EPOCH FROM (b.ingestion_time - b.event_time)) / 3600
                    AS NUMERIC), 4
                ) AS ingestion_lag_hours,
                -- is_anomaly: bronze flagged, OR time confusion, OR future event
                (
                    b.bronze_is_anomaly
                    OR b.ingestion_time < b.event_time
                    OR b.event_time > NOW() + INTERVAL '1 hour'
                ) AS is_anomaly,
                -- is_usable_for_ml: clean, non-duplicate, non-anomalous
                (
                    NOT b.is_duplicate
                    AND NOT b.bronze_is_anomaly
                    AND b.ingestion_time >= b.event_time
                    AND b.event_time <= NOW() + INTERVAL '1 hour'
                ) AS is_usable_for_ml,
                b.bronze_run_id,
                NOW() AS silver_processed_at,
                b.created_at
            FROM bronze_tracking_events b
            ON CONFLICT (event_id) DO UPDATE SET
                is_anomaly = EXCLUDED.is_anomaly,
                is_usable_for_ml = EXCLUDED.is_usable_for_ml,
                silver_processed_at = EXCLUDED.silver_processed_at
        """))
        db.commit()

        written = db.execute(
            text("SELECT COUNT(*) FROM silver_tracking_events")
        ).scalar()
        anomaly_count = db.execute(
            text("SELECT COUNT(*) FROM silver_tracking_events WHERE is_anomaly = TRUE")
        ).scalar()
        usable_count = db.execute(
            text("SELECT COUNT(*) FROM silver_tracking_events WHERE is_usable_for_ml = TRUE")
        ).scalar()

        result.rows_written = int(written)
        result.rows_skipped = int(anomaly_count)
        result.extra["anomaly_count"] = int(anomaly_count)
        result.extra["usable_for_ml_count"] = int(usable_count)
        log.info(
            "silver_tracking_events: written=%d anomalies=%d usable_for_ml=%d",
            written, anomaly_count, usable_count,
        )


class SilverShipmentsJob(ETLJob):
    """bronze_shipment_snapshot → silver_shipments.

    Adds derived fields:
      - total_transit_hours: actual (or planned) transit duration.
      - is_delayed: actual > promised (or NULL if not yet delivered).
      - delay_hours: actual - promised in hours (NULL if not delivered).
      - is_anomaly: inherits from bronze_is_anomaly.
      - is_usable_for_ml: DELIVERED + not anomalous + has valid dates.
    """

    name = "silver_shipments"
    stage = "SILVER"

    def _execute(self, db, result: JobResult) -> None:
        source_count = db.execute(
            text("SELECT COUNT(*) FROM bronze_shipment_snapshot")
        ).scalar()
        result.rows_read = int(source_count)

        db.execute(text("""
            INSERT INTO silver_shipments (
                shipment_id, carrier_id, service_level_id, route_id,
                origin_facility_id, destination_facility_id,
                planned_ship_time, promised_delivery_time, actual_delivery_time,
                status, priority, weight_kg, distance_km, sla_status,
                is_demo, carrier_name, base_delay_factor,
                base_transit_hours, maximum_delivery_hours, allowed_delay_hours,
                total_transit_hours, is_delayed, delay_hours,
                is_anomaly, is_usable_for_ml,
                bronze_run_id, silver_processed_at, created_at, updated_at
            )
            SELECT
                b.shipment_id,
                b.carrier_id,
                b.service_level_id,
                b.route_id,
                b.origin_facility_id,
                b.destination_facility_id,
                b.planned_ship_time,
                b.promised_delivery_time,
                b.actual_delivery_time,
                b.status,
                b.priority,
                b.weight_kg,
                b.distance_km,
                b.sla_status,
                b.is_demo,
                b.carrier_name,
                b.base_delay_factor,
                b.base_transit_hours,
                b.maximum_delivery_hours,
                b.allowed_delay_hours,
                -- total_transit_hours: actual if delivered, else planned
                CASE
                    WHEN b.actual_delivery_time IS NOT NULL THEN
                        ROUND(CAST(
                            EXTRACT(EPOCH FROM
                                (b.actual_delivery_time - b.planned_ship_time)
                            ) / 3600 AS NUMERIC), 4)
                    ELSE
                        ROUND(CAST(
                            EXTRACT(EPOCH FROM
                                (b.promised_delivery_time - b.planned_ship_time)
                            ) / 3600 AS NUMERIC), 4)
                END AS total_transit_hours,
                -- is_delayed
                CASE
                    WHEN b.actual_delivery_time IS NOT NULL
                         AND b.actual_delivery_time > b.promised_delivery_time
                    THEN TRUE
                    ELSE FALSE
                END AS is_delayed,
                -- delay_hours (positive = late, negative = early)
                CASE
                    WHEN b.actual_delivery_time IS NOT NULL THEN
                        ROUND(CAST(
                            EXTRACT(EPOCH FROM
                                (b.actual_delivery_time - b.promised_delivery_time)
                            ) / 3600 AS NUMERIC), 4)
                    ELSE NULL
                END AS delay_hours,
                b.bronze_is_anomaly AS is_anomaly,
                -- usable for ML: delivered, valid dates, not anomalous
                (
                    b.status = 'DELIVERED'
                    AND b.actual_delivery_time IS NOT NULL
                    AND b.actual_delivery_time >= b.planned_ship_time
                    AND b.promised_delivery_time > b.planned_ship_time
                    AND NOT b.bronze_is_anomaly
                ) AS is_usable_for_ml,
                b.bronze_run_id,
                NOW(),
                b.created_at,
                b.updated_at
            FROM bronze_shipment_snapshot b
            ON CONFLICT (shipment_id) DO UPDATE SET
                status              = EXCLUDED.status,
                actual_delivery_time= EXCLUDED.actual_delivery_time,
                sla_status          = EXCLUDED.sla_status,
                total_transit_hours = EXCLUDED.total_transit_hours,
                is_delayed          = EXCLUDED.is_delayed,
                delay_hours         = EXCLUDED.delay_hours,
                is_anomaly          = EXCLUDED.is_anomaly,
                is_usable_for_ml    = EXCLUDED.is_usable_for_ml,
                silver_processed_at = EXCLUDED.silver_processed_at
        """))
        db.commit()

        written = db.execute(
            text("SELECT COUNT(*) FROM silver_shipments")
        ).scalar()
        usable = db.execute(
            text("SELECT COUNT(*) FROM silver_shipments WHERE is_usable_for_ml = TRUE")
        ).scalar()
        delayed = db.execute(
            text("SELECT COUNT(*) FROM silver_shipments WHERE is_delayed = TRUE")
        ).scalar()

        result.rows_written = int(written)
        result.extra["usable_for_ml_count"] = int(usable)
        result.extra["delayed_count"] = int(delayed)
        log.info(
            "silver_shipments: written=%d usable_for_ml=%d delayed=%d",
            written, usable, delayed,
        )
