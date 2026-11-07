"""Gold layer jobs.

Gold produces business-ready, query-optimised tables and ML feature rows.

Jobs:
  GoldCarrierPerformanceJob   — recalculates carrier KPIs from silver_shipments.
  GoldFacilityPerformanceJob  — recalculates facility utilisation / delay contribution.
  GoldShipmentFeaturesJob     — one row per delivered shipment with all ML features.

Key design rules:
  - All values are CALCULATED from source records — never independently invented.
  - Only is_usable_for_ml=TRUE rows feed into Gold ML features.
  - ground_truth labels are explicitly excluded from feature columns.
  - ON CONFLICT DO UPDATE keeps Gold tables current on reruns.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from data_engineering.pipelines.base import ETLJob, JobResult

log = logging.getLogger("data_engineering.transformation.gold")


class GoldCarrierPerformanceJob(ETLJob):
    """Recalculate carrier KPIs and upsert into carrier_performance table.

    Metrics (all derived from silver_shipments, never fabricated):
      on_time_rate      = on_time_count / total_shipments
      average_delay     = AVG(delay_hours) for delayed shipments
      late_scan_rate    = late_scan_count / total_shipments  (from silver events)
      route_change_rate = route_change_count / total_shipments
      carrier_score     = documented formula:
                          40*on_time_rate + 30*(1-late_scan_rate) +
                          30*(1-LEAST(avg_delay/24, 1))
                          clipped to [0, 100]
    """

    name = "gold_carrier_performance"
    stage = "GOLD"

    def _execute(self, db, result: JobResult) -> None:
        source_count = db.execute(
            text("SELECT COUNT(*) FROM silver_shipments")
        ).scalar()
        result.rows_read = int(source_count)

        db.execute(text("""
            INSERT INTO carrier_performance (
                perf_id, carrier_id,
                period_start, period_end,
                total_shipments, on_time_count, on_time_rate,
                average_delay_hours, late_scan_count, late_scan_rate,
                route_change_count, route_change_rate,
                carrier_score,
                created_at, updated_at
            )
            SELECT
                'CP-' || ss.carrier_id || '-GOLD' AS perf_id,
                ss.carrier_id,
                MIN(ss.planned_ship_time)::DATE AS period_start,
                MAX(ss.planned_ship_time)::DATE AS period_end,
                COUNT(*)                        AS total_shipments,
                SUM(CASE WHEN ss.is_delayed = FALSE AND ss.status = 'DELIVERED'
                         THEN 1 ELSE 0 END)     AS on_time_count,
                ROUND(
                    SUM(CASE WHEN ss.is_delayed = FALSE AND ss.status = 'DELIVERED'
                             THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0),
                    4
                )                               AS on_time_rate,
                ROUND(AVG(CASE WHEN ss.delay_hours > 0 THEN ss.delay_hours END), 2)
                                                AS average_delay_hours,
                -- late_scan: events with ingestion_lag_hours > 2
                COALESCE((
                    SELECT COUNT(*)
                    FROM silver_tracking_events ste
                    WHERE ste.shipment_id IN (
                        SELECT shipment_id FROM silver_shipments
                        WHERE carrier_id = ss.carrier_id
                    ) AND ste.ingestion_lag_hours > 2
                ), 0)                           AS late_scan_count,
                ROUND(
                    COALESCE((
                        SELECT COUNT(*)::NUMERIC
                        FROM silver_tracking_events ste
                        WHERE ste.shipment_id IN (
                            SELECT shipment_id FROM silver_shipments
                            WHERE carrier_id = ss.carrier_id
                        ) AND ste.ingestion_lag_hours > 2
                    ), 0) / NULLIF(COUNT(*), 0),
                    4
                )                               AS late_scan_rate,
                -- route_change_count from route_changes table
                COALESCE((
                    SELECT COUNT(*)
                    FROM route_changes rc
                    JOIN shipments shp ON rc.shipment_id = shp.shipment_id
                    WHERE shp.carrier_id = ss.carrier_id
                ), 0)                           AS route_change_count,
                ROUND(
                    COALESCE((
                        SELECT COUNT(*)::NUMERIC
                        FROM route_changes rc
                        JOIN shipments shp ON rc.shipment_id = shp.shipment_id
                        WHERE shp.carrier_id = ss.carrier_id
                    ), 0) / NULLIF(COUNT(*), 0),
                    4
                )                               AS route_change_rate,
                -- carrier_score: 40*OTR + 30*(1-LSR) + 30*(1-min(avg_delay/24,1))
                ROUND(LEAST(100, GREATEST(0,
                    40 * COALESCE(
                        SUM(CASE WHEN ss.is_delayed = FALSE AND ss.status = 'DELIVERED'
                                 THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0),
                        0
                    )
                    + 30 * (1 - COALESCE(
                        COALESCE((
                            SELECT COUNT(*)::NUMERIC
                            FROM silver_tracking_events ste2
                            WHERE ste2.shipment_id IN (
                                SELECT shipment_id FROM silver_shipments
                                WHERE carrier_id = ss.carrier_id
                            ) AND ste2.ingestion_lag_hours > 2
                        ), 0) / NULLIF(COUNT(*), 0),
                        0
                    ))
                    + 30 * (1 - LEAST(
                        COALESCE(AVG(CASE WHEN ss.delay_hours > 0 THEN ss.delay_hours END), 0) / 24,
                        1
                    ))
                )), 2)                          AS carrier_score,
                NOW(),
                NOW()
            FROM silver_shipments ss
            WHERE ss.is_usable_for_ml = TRUE
            GROUP BY ss.carrier_id
            ON CONFLICT (perf_id) DO UPDATE SET
                total_shipments     = EXCLUDED.total_shipments,
                on_time_count       = EXCLUDED.on_time_count,
                on_time_rate        = EXCLUDED.on_time_rate,
                average_delay_hours = EXCLUDED.average_delay_hours,
                late_scan_count     = EXCLUDED.late_scan_count,
                late_scan_rate      = EXCLUDED.late_scan_rate,
                route_change_count  = EXCLUDED.route_change_count,
                route_change_rate   = EXCLUDED.route_change_rate,
                carrier_score       = EXCLUDED.carrier_score,
                period_end          = EXCLUDED.period_end,
                updated_at          = NOW()
        """))
        db.commit()

        written = db.execute(
            text("SELECT COUNT(*) FROM carrier_performance WHERE perf_id LIKE 'CP-%-GOLD'")
        ).scalar()
        result.rows_written = int(written)
        log.info("gold_carrier_performance: upserted=%d", written)


class GoldFacilityPerformanceJob(ETLJob):
    """Recalculate facility KPIs and upsert into facility_performance."""

    name = "gold_facility_performance"
    stage = "GOLD"

    def _execute(self, db, result: JobResult) -> None:
        source_count = db.execute(
            text("SELECT COUNT(*) FROM facilities")
        ).scalar()
        result.rows_read = int(source_count)

        db.execute(text("""
            INSERT INTO facility_performance (
                perf_id, facility_id,
                period_start, period_end,
                average_queue_length,
                average_processing_time_minutes,
                average_utilization_pct,
                delay_contribution_rate,
                total_shipments_processed,
                created_at, updated_at
            )
            SELECT
                'FP-' || f.facility_id || '-GOLD' AS perf_id,
                f.facility_id,
                MIN(fq.timestamp)::DATE AS period_start,
                MAX(fq.timestamp)::DATE AS period_end,
                ROUND(AVG(fq.queue_length), 2) AS average_queue_length,
                ROUND(AVG(fq.average_processing_time_minutes), 2)
                    AS average_processing_time_minutes,
                -- utilization derived: avg_queue / capacity * 100
                ROUND(AVG(fq.queue_length::NUMERIC / NULLIF(fq.capacity, 0) * 100), 2)
                    AS average_utilization_pct,
                -- delay contribution: delayed shipments passing through / total
                COALESCE(ROUND(
                    (SELECT COUNT(*)::NUMERIC
                     FROM silver_shipments ss
                     WHERE (ss.origin_facility_id = f.facility_id
                            OR ss.destination_facility_id = f.facility_id)
                       AND ss.is_delayed = TRUE
                    ) / NULLIF(
                        (SELECT COUNT(*)
                         FROM silver_shipments ss2
                         WHERE ss2.origin_facility_id = f.facility_id
                            OR ss2.destination_facility_id = f.facility_id
                        ), 0
                    ), 4
                ), 0) AS delay_contribution_rate,
                (SELECT COUNT(*)
                 FROM silver_shipments ss3
                 WHERE ss3.origin_facility_id = f.facility_id
                    OR ss3.destination_facility_id = f.facility_id
                ) AS total_shipments_processed,
                NOW(),
                NOW()
            FROM facilities f
            JOIN facility_queues fq ON fq.facility_id = f.facility_id
            GROUP BY f.facility_id
            ON CONFLICT (perf_id) DO UPDATE SET
                average_queue_length             = EXCLUDED.average_queue_length,
                average_processing_time_minutes  = EXCLUDED.average_processing_time_minutes,
                average_utilization_pct          = EXCLUDED.average_utilization_pct,
                delay_contribution_rate          = EXCLUDED.delay_contribution_rate,
                total_shipments_processed        = EXCLUDED.total_shipments_processed,
                period_end                       = EXCLUDED.period_end,
                updated_at                       = NOW()
        """))
        db.commit()

        written = db.execute(
            text("SELECT COUNT(*) FROM facility_performance WHERE perf_id LIKE 'FP-%-GOLD'")
        ).scalar()
        result.rows_written = int(written)
        log.info("gold_facility_performance: upserted=%d", written)


class GoldShipmentFeaturesJob(ETLJob):
    """Build ML feature rows from silver_shipments → gold_shipment_features.

    One row per usable shipment. Features include:
      - distance_km, weight_kg, base_transit_hours
      - carrier_delay_factor (from carriers table)
      - max weather_delay_factor affecting the route during transit
      - max facility_queue utilization at origin/dest during transit
      - event count, late event count
      - day_of_week, hour_of_day at planned_ship_time
      - service_level encoded as integer (STANDARD=0, EXPRESS=1, SAME_DAY=2, PRIORITY=3)
      - delay_label (target for delay classification: 0=on_time, 1=delayed)
      - remaining_delivery_hours (target for ETA regression — at time of last event)

    GROUND TRUTH LABELS (ground_truth_label from data_quality_issues) are
    EXCLUDED from this table. The is_anomaly column from Silver is included
    so downstream training can filter them out explicitly.
    """

    name = "gold_shipment_features"
    stage = "GOLD"

    _SL_ENCODING = {"STANDARD": 0, "EXPRESS": 1, "SAME_DAY": 2, "PRIORITY": 3}

    def _execute(self, db, result: JobResult) -> None:
        source_count = db.execute(
            text("SELECT COUNT(*) FROM silver_shipments WHERE is_usable_for_ml = TRUE")
        ).scalar()
        result.rows_read = int(source_count)

        db.execute(text("""
            INSERT INTO gold_shipment_features (
                shipment_id,
                carrier_id,
                service_level_id,
                service_level_encoded,
                distance_km,
                weight_kg,
                base_transit_hours,
                base_delay_factor,
                max_weather_delay_factor,
                max_facility_utilization_pct,
                event_count,
                late_event_count,
                day_of_week,
                hour_of_day,
                total_transit_hours,
                delay_hours,
                delay_label,
                remaining_delivery_hours,
                sla_status,
                is_anomaly,
                gold_computed_at
            )
            SELECT
                ss.shipment_id,
                ss.carrier_id,
                ss.service_level_id,
                CASE ss.service_level_id
                    WHEN 'STANDARD'  THEN 0
                    WHEN 'EXPRESS'   THEN 1
                    WHEN 'SAME_DAY'  THEN 2
                    WHEN 'PRIORITY'  THEN 3
                    ELSE 0
                END                                     AS service_level_encoded,
                COALESCE(ss.distance_km, ss.base_transit_hours * 60)
                                                        AS distance_km,
                COALESCE(ss.weight_kg, 10.0)            AS weight_kg,
                ss.base_transit_hours,
                CAST(ss.base_delay_factor AS NUMERIC),

                -- max weather delay factor during shipment window
                COALESCE((
                    SELECT MAX(we.delay_factor)
                    FROM weather_events we
                    WHERE we.start_time <= ss.promised_delivery_time
                      AND we.end_time   >= ss.planned_ship_time
                ), 1.0)                                 AS max_weather_delay_factor,

                -- max facility utilization at origin/dest during transit
                COALESCE((
                    SELECT MAX(fq.utilization_pct)
                    FROM facility_queues fq
                    WHERE fq.facility_id IN (ss.origin_facility_id, ss.destination_facility_id)
                      AND fq.timestamp BETWEEN ss.planned_ship_time AND ss.promised_delivery_time
                ), 0)                                   AS max_facility_utilization_pct,

                -- event counts (usable events only)
                COALESCE((
                    SELECT COUNT(*)
                    FROM silver_tracking_events ste
                    WHERE ste.shipment_id = ss.shipment_id
                ), 0)                                   AS event_count,

                -- late event count (ingestion_lag_hours > 2)
                COALESCE((
                    SELECT COUNT(*)
                    FROM silver_tracking_events ste2
                    WHERE ste2.shipment_id = ss.shipment_id
                      AND ste2.ingestion_lag_hours > 2
                ), 0)                                   AS late_event_count,

                EXTRACT(DOW FROM ss.planned_ship_time)::INT AS day_of_week,
                EXTRACT(HOUR FROM ss.planned_ship_time)::INT AS hour_of_day,
                ss.total_transit_hours,
                ss.delay_hours,

                -- delay_label: binary target (0=on-time, 1=delayed)
                CASE WHEN ss.is_delayed THEN 1 ELSE 0 END AS delay_label,

                -- remaining_delivery_hours: from last usable event to actual delivery
                -- Used as the regression target for ETA model
                COALESCE((
                    SELECT ROUND(CAST(
                        EXTRACT(EPOCH FROM
                            (ss.actual_delivery_time - MAX(ste3.event_time))
                        ) / 3600 AS NUMERIC), 4)
                    FROM silver_tracking_events ste3
                    WHERE ste3.shipment_id = ss.shipment_id
                      AND ste3.is_usable_for_ml = TRUE
                ), ss.total_transit_hours)              AS remaining_delivery_hours,

                ss.sla_status,
                ss.is_anomaly,
                NOW()
            FROM silver_shipments ss
            WHERE ss.is_usable_for_ml = TRUE
            ON CONFLICT (shipment_id) DO UPDATE SET
                max_weather_delay_factor     = EXCLUDED.max_weather_delay_factor,
                max_facility_utilization_pct = EXCLUDED.max_facility_utilization_pct,
                event_count                  = EXCLUDED.event_count,
                late_event_count             = EXCLUDED.late_event_count,
                delay_label                  = EXCLUDED.delay_label,
                remaining_delivery_hours     = EXCLUDED.remaining_delivery_hours,
                sla_status                   = EXCLUDED.sla_status,
                is_anomaly                   = EXCLUDED.is_anomaly,
                gold_computed_at             = NOW()
        """))
        db.commit()

        written = db.execute(
            text("SELECT COUNT(*) FROM gold_shipment_features")
        ).scalar()
        anomaly_in_gold = db.execute(
            text("SELECT COUNT(*) FROM gold_shipment_features WHERE is_anomaly = TRUE")
        ).scalar()
        delayed_in_gold = db.execute(
            text("SELECT COUNT(*) FROM gold_shipment_features WHERE delay_label = 1")
        ).scalar()

        result.rows_written = int(written)
        result.extra["anomaly_rows"] = int(anomaly_in_gold)
        result.extra["delayed_rows"] = int(delayed_in_gold)
        log.info(
            "gold_shipment_features: written=%d anomalies=%d delayed=%d",
            written, anomaly_in_gold, delayed_in_gold,
        )
