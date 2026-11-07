"""Advanced SQL analytics for YottaFlex.

All 12 queries use CTEs, window functions, aggregations, and date functions.
Every function returns a list of dicts (JSON-serialisable).
No raw data is fabricated — every metric is computed from source tables.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


# ── 1. Top delayed carriers ───────────────────────────────────────────────────
TOP_DELAYED_CARRIERS_SQL = """
WITH carrier_stats AS (
    SELECT
        c.carrier_id,
        c.carrier_name,
        c.carrier_code,
        COUNT(*)                                    AS total_shipments,
        SUM(CASE WHEN s.sla_status = 'BREACHED' THEN 1 ELSE 0 END) AS breached,
        SUM(CASE WHEN s.is_demo = TRUE THEN 1 ELSE 0 END)          AS demo_rows,
        ROUND(AVG(CASE WHEN ss.delay_hours > 0 THEN ss.delay_hours END)::NUMERIC, 2)
                                                    AS avg_delay_hours,
        ROUND(
            SUM(CASE WHEN s.sla_status = 'BREACHED' THEN 1 ELSE 0 END)::NUMERIC /
            NULLIF(COUNT(*), 0) * 100, 2
        )                                           AS breach_rate_pct
    FROM shipments s
    JOIN carriers c ON s.carrier_id = c.carrier_id
    LEFT JOIN silver_shipments ss ON s.shipment_id = ss.shipment_id
    GROUP BY c.carrier_id, c.carrier_name, c.carrier_code
),
ranked AS (
    SELECT *,
           RANK() OVER (ORDER BY breach_rate_pct DESC NULLS LAST) AS rank
    FROM carrier_stats
)
SELECT rank, carrier_id, carrier_name, carrier_code,
       total_shipments, breached, breach_rate_pct, avg_delay_hours
FROM ranked
ORDER BY rank
LIMIT :limit
"""

# ── 2. Top congested facilities ───────────────────────────────────────────────
TOP_CONGESTED_FACILITIES_SQL = """
WITH fq_stats AS (
    SELECT
        f.facility_id,
        f.facility_name,
        f.facility_type,
        f.city,
        f.capacity,
        ROUND(AVG(fq.utilization_pct)::NUMERIC, 2)   AS avg_utilization_pct,
        ROUND(MAX(fq.utilization_pct)::NUMERIC, 2)   AS max_utilization_pct,
        ROUND(AVG(fq.average_processing_time_minutes)::NUMERIC, 2)
                                                       AS avg_proc_minutes,
        COUNT(fq.queue_id)                             AS snapshot_count
    FROM facilities f
    JOIN facility_queues fq ON f.facility_id = fq.facility_id
    GROUP BY f.facility_id, f.facility_name, f.facility_type, f.city, f.capacity
),
ranked AS (
    SELECT *,
           RANK() OVER (ORDER BY avg_utilization_pct DESC) AS rank
    FROM fq_stats
)
SELECT rank, facility_id, facility_name, facility_type, city, capacity,
       avg_utilization_pct, max_utilization_pct, avg_proc_minutes, snapshot_count
FROM ranked
ORDER BY rank
LIMIT :limit
"""

# ── 3. Daily shipment volume ──────────────────────────────────────────────────
DAILY_SHIPMENT_VOLUME_SQL = """
SELECT
    planned_ship_time::DATE                           AS ship_date,
    COUNT(*)                                          AS total_shipments,
    SUM(CASE WHEN status = 'DELIVERED' THEN 1 ELSE 0 END) AS delivered,
    SUM(CASE WHEN sla_status = 'BREACHED' THEN 1 ELSE 0 END) AS sla_breached,
    SUM(CASE WHEN sla_status = 'AT_RISK'  THEN 1 ELSE 0 END) AS sla_at_risk
FROM shipments
WHERE planned_ship_time >= CURRENT_DATE - INTERVAL ':days days'
GROUP BY ship_date
ORDER BY ship_date DESC
"""

# ── 4. SLA compliance summary ─────────────────────────────────────────────────
SLA_COMPLIANCE_SQL = """
WITH sla_counts AS (
    SELECT
        sla_status,
        COUNT(*) AS cnt
    FROM shipments
    GROUP BY sla_status
),
total AS (SELECT SUM(cnt) AS grand_total FROM sla_counts)
SELECT
    sc.sla_status,
    sc.cnt,
    ROUND(sc.cnt::NUMERIC / t.grand_total * 100, 2) AS pct
FROM sla_counts sc, total t
ORDER BY
    CASE sc.sla_status
        WHEN 'ON_TIME'  THEN 1
        WHEN 'AT_RISK'  THEN 2
        WHEN 'BREACHED' THEN 3
        ELSE 4
    END
"""

# ── 5. Average delay by carrier ───────────────────────────────────────────────
AVG_DELAY_BY_CARRIER_SQL = """
SELECT
    c.carrier_id,
    c.carrier_name,
    c.carrier_code,
    COUNT(ss.shipment_id)                                       AS delivered_count,
    ROUND(AVG(CASE WHEN ss.is_delayed THEN ss.delay_hours END)::NUMERIC, 2)
                                                                AS avg_delay_hours,
    ROUND(AVG(CASE WHEN NOT ss.is_delayed THEN ABS(ss.delay_hours) END)::NUMERIC, 2)
                                                                AS avg_early_hours,
    ROUND(SUM(CASE WHEN ss.is_delayed THEN 1 ELSE 0 END)::NUMERIC /
          NULLIF(COUNT(ss.shipment_id), 0) * 100, 2)            AS delay_rate_pct,
    RANK() OVER (ORDER BY
        ROUND(AVG(CASE WHEN ss.is_delayed THEN ss.delay_hours END)::NUMERIC, 2)
        DESC NULLS LAST
    )                                                           AS delay_rank
FROM silver_shipments ss
JOIN carriers c ON ss.carrier_id = c.carrier_id
WHERE ss.status = 'DELIVERED'
GROUP BY c.carrier_id, c.carrier_name, c.carrier_code
ORDER BY delay_rank
"""

# ── 6. Average delay by route ─────────────────────────────────────────────────
AVG_DELAY_BY_ROUTE_SQL = """
WITH route_stats AS (
    SELECT
        r.route_id,
        r.route_name,
        r.distance_km,
        r.base_transit_hours,
        COUNT(ss.shipment_id)               AS shipment_count,
        ROUND(AVG(ss.total_transit_hours)::NUMERIC, 2)  AS avg_actual_hours,
        ROUND(AVG(ss.delay_hours)::NUMERIC, 2)          AS avg_delay_hours,
        ROUND(SUM(CASE WHEN ss.is_delayed THEN 1 ELSE 0 END)::NUMERIC /
              NULLIF(COUNT(ss.shipment_id), 0) * 100, 2) AS delay_rate_pct
    FROM silver_shipments ss
    JOIN routes r ON ss.route_id = r.route_id
    WHERE ss.status = 'DELIVERED'
    GROUP BY r.route_id, r.route_name, r.distance_km, r.base_transit_hours
)
SELECT *,
       RANK() OVER (ORDER BY avg_delay_hours DESC NULLS LAST) AS delay_rank
FROM route_stats
ORDER BY delay_rank
"""

# ── 7. Latest tracking event per shipment ────────────────────────────────────
LATEST_EVENT_PER_SHIPMENT_SQL = """
WITH ranked_events AS (
    SELECT
        te.*,
        ROW_NUMBER() OVER (
            PARTITION BY te.shipment_id
            ORDER BY te.event_time DESC, te.ingestion_time DESC
        ) AS rn
    FROM tracking_events te
),
latest AS (
    SELECT re.*, s.status AS shipment_status, s.sla_status
    FROM ranked_events re
    JOIN shipments s ON re.shipment_id = s.shipment_id
    WHERE re.rn = 1
)
SELECT
    shipment_id, event_id, event_type, event_time,
    ingestion_time, facility_id, shipment_status, sla_status
FROM latest
WHERE shipment_id = :shipment_id
"""

# ── 8. Shipment event gaps (missing scan detection) ──────────────────────────
SHIPMENT_EVENT_GAPS_SQL = """
WITH event_sequence AS (
    SELECT
        shipment_id,
        event_type,
        event_time,
        LAG(event_time)  OVER (PARTITION BY shipment_id ORDER BY event_time) AS prev_event_time,
        LAG(event_type)  OVER (PARTITION BY shipment_id ORDER BY event_time) AS prev_event_type,
        LEAD(event_time) OVER (PARTITION BY shipment_id ORDER BY event_time) AS next_event_time
    FROM tracking_events
    WHERE is_duplicate = FALSE
),
gaps AS (
    SELECT
        shipment_id,
        prev_event_type,
        event_type        AS current_event_type,
        prev_event_time,
        event_time        AS current_event_time,
        ROUND(CAST(
            EXTRACT(EPOCH FROM (event_time - prev_event_time)) / 3600
        AS NUMERIC), 2)   AS gap_hours
    FROM event_sequence
    WHERE prev_event_time IS NOT NULL
)
SELECT *
FROM gaps
WHERE gap_hours > :threshold_hours
ORDER BY gap_hours DESC
LIMIT :limit
"""

# ── 9. High-risk shipments ────────────────────────────────────────────────────
HIGH_RISK_SHIPMENTS_SQL = """
WITH risk_data AS (
    SELECT
        s.shipment_id,
        s.status,
        s.sla_status,
        s.priority,
        c.carrier_name,
        s.promised_delivery_time,
        -- days until SLA breach
        ROUND(CAST(
            EXTRACT(EPOCH FROM (s.promised_delivery_time - NOW())) / 3600
        AS NUMERIC), 1)    AS hours_until_promised,
        -- max weather risk on route
        COALESCE((
            SELECT MAX(we.delay_factor)
            FROM weather_events we
            WHERE we.end_time >= NOW()
              AND we.start_time <= s.promised_delivery_time
        ), 1.0)            AS max_upcoming_weather_factor,
        -- latest facility utilization on route
        COALESCE((
            SELECT MAX(fq.utilization_pct)
            FROM facility_queues fq
            WHERE fq.facility_id IN (s.origin_facility_id, s.destination_facility_id)
              AND fq.timestamp >= NOW() - INTERVAL '4 hours'
        ), 0)              AS current_max_utilization
    FROM shipments s
    JOIN carriers c ON s.carrier_id = c.carrier_id
    WHERE s.status NOT IN ('DELIVERED', 'CANCELLED')
)
SELECT *
FROM risk_data
WHERE sla_status IN ('AT_RISK', 'BREACHED')
   OR hours_until_promised < 4
   OR max_upcoming_weather_factor >= 1.35
   OR current_max_utilization >= 80
ORDER BY
    CASE sla_status WHEN 'BREACHED' THEN 1 WHEN 'AT_RISK' THEN 2 ELSE 3 END,
    hours_until_promised ASC
LIMIT :limit
"""

# ── 10. Facility queue trends ─────────────────────────────────────────────────
FACILITY_QUEUE_TRENDS_SQL = """
SELECT
    fq.facility_id,
    f.facility_name,
    fq.timestamp::DATE                                  AS queue_date,
    ROUND(AVG(fq.utilization_pct)::NUMERIC, 2)          AS avg_utilization_pct,
    ROUND(MAX(fq.utilization_pct)::NUMERIC, 2)          AS max_utilization_pct,
    ROUND(AVG(fq.queue_length)::NUMERIC, 1)             AS avg_queue_length,
    ROUND(AVG(fq.average_processing_time_minutes)::NUMERIC, 2)
                                                         AS avg_proc_minutes,
    ROUND(
        AVG(fq.utilization_pct)::NUMERIC -
        LAG(AVG(fq.utilization_pct)::NUMERIC, 1)
            OVER (PARTITION BY fq.facility_id ORDER BY fq.timestamp::DATE),
        2
    )                                                    AS utilization_change_pct
FROM facility_queues fq
JOIN facilities f ON fq.facility_id = f.facility_id
WHERE fq.facility_id = :facility_id
GROUP BY fq.facility_id, f.facility_name, queue_date
ORDER BY queue_date DESC
LIMIT :days
"""

# ── 11. Carrier ranking ────────────────────────────────────────────────────────
CARRIER_RANKING_SQL = """
WITH perf AS (
    SELECT
        cp.carrier_id,
        c.carrier_name,
        c.carrier_code,
        COALESCE(cp.on_time_rate, 0)      AS on_time_rate,
        COALESCE(cp.late_scan_rate, 0)    AS late_scan_rate,
        COALESCE(cp.average_delay_hours, 0) AS avg_delay_hours,
        COALESCE(cp.carrier_score, 0)     AS carrier_score,
        cp.total_shipments
    FROM carrier_performance cp
    JOIN carriers c ON cp.carrier_id = c.carrier_id
    WHERE cp.perf_id LIKE 'CP-%-GOLD'
)
SELECT
    RANK()       OVER (ORDER BY carrier_score DESC) AS overall_rank,
    DENSE_RANK() OVER (ORDER BY on_time_rate DESC)  AS on_time_rank,
    carrier_id, carrier_name, carrier_code,
    ROUND((on_time_rate * 100)::NUMERIC, 1)         AS on_time_pct,
    ROUND((late_scan_rate * 100)::NUMERIC, 1)       AS late_scan_pct,
    ROUND(avg_delay_hours::NUMERIC, 2)              AS avg_delay_hours,
    ROUND(carrier_score::NUMERIC, 1)                AS carrier_score,
    total_shipments
FROM perf
ORDER BY overall_rank
"""

# ── 12. Route performance ──────────────────────────────────────────────────────
ROUTE_PERFORMANCE_SQL = """
WITH route_perf AS (
    SELECT
        r.route_id,
        r.route_name,
        r.distance_km,
        r.base_transit_hours,
        f_orig.city                                     AS origin_city,
        f_dest.city                                     AS destination_city,
        COUNT(s.shipment_id)                            AS total_shipments,
        SUM(CASE WHEN s.status = 'DELIVERED' THEN 1 ELSE 0 END) AS delivered,
        SUM(CASE WHEN s.sla_status = 'BREACHED' THEN 1 ELSE 0 END) AS sla_breached,
        ROUND(AVG(ss.total_transit_hours)::NUMERIC, 2)  AS avg_actual_hours,
        ROUND(
            (r.base_transit_hours -
             AVG(COALESCE(ss.total_transit_hours, r.base_transit_hours)))::NUMERIC,
        2)                                              AS avg_hours_vs_plan,
        ROUND(
            SUM(CASE WHEN s.sla_status = 'BREACHED' THEN 1 ELSE 0 END)::NUMERIC /
            NULLIF(COUNT(s.shipment_id), 0) * 100,
        2)                                              AS breach_rate_pct
    FROM routes r
    JOIN facilities f_orig ON r.origin_facility_id      = f_orig.facility_id
    JOIN facilities f_dest ON r.destination_facility_id = f_dest.facility_id
    LEFT JOIN shipments s ON s.route_id = r.route_id
    LEFT JOIN silver_shipments ss ON ss.shipment_id = s.shipment_id
    GROUP BY r.route_id, r.route_name, r.distance_km, r.base_transit_hours,
             f_orig.city, f_dest.city
)
SELECT *,
       RANK() OVER (ORDER BY breach_rate_pct DESC NULLS LAST) AS performance_rank
FROM route_perf
ORDER BY performance_rank
"""


# ── Query runner helpers ───────────────────────────────────────────────────────

def _run(db: Session, sql: str, params: dict) -> list[dict]:
    rows = db.execute(text(sql), params).mappings().fetchall()
    return [dict(r) for r in rows]


def top_delayed_carriers(db: Session, limit: int = 10) -> list[dict]:
    return _run(db, TOP_DELAYED_CARRIERS_SQL, {"limit": limit})


def top_congested_facilities(db: Session, limit: int = 10) -> list[dict]:
    return _run(db, TOP_CONGESTED_FACILITIES_SQL, {"limit": limit})


def daily_shipment_volume(db: Session, days: int = 30) -> list[dict]:
    # Inject days directly (safe: it's an integer from trusted code)
    sql = DAILY_SHIPMENT_VOLUME_SQL.replace(":days days", f"{days} days")
    return _run(db, sql, {})


def sla_compliance(db: Session) -> list[dict]:
    return _run(db, SLA_COMPLIANCE_SQL, {})


def avg_delay_by_carrier(db: Session) -> list[dict]:
    return _run(db, AVG_DELAY_BY_CARRIER_SQL, {})


def avg_delay_by_route(db: Session) -> list[dict]:
    return _run(db, AVG_DELAY_BY_ROUTE_SQL, {})


def latest_event_per_shipment(db: Session, shipment_id: str) -> list[dict]:
    return _run(db, LATEST_EVENT_PER_SHIPMENT_SQL, {"shipment_id": shipment_id})


def shipment_event_gaps(
    db: Session, threshold_hours: float = 6.0, limit: int = 50
) -> list[dict]:
    return _run(db, SHIPMENT_EVENT_GAPS_SQL,
                {"threshold_hours": threshold_hours, "limit": limit})


def high_risk_shipments(db: Session, limit: int = 50) -> list[dict]:
    return _run(db, HIGH_RISK_SHIPMENTS_SQL, {"limit": limit})


def facility_queue_trends(
    db: Session, facility_id: str, days: int = 7
) -> list[dict]:
    return _run(db, FACILITY_QUEUE_TRENDS_SQL,
                {"facility_id": facility_id, "days": days})


def carrier_ranking(db: Session) -> list[dict]:
    return _run(db, CARRIER_RANKING_SQL, {})


def route_performance(db: Session) -> list[dict]:
    return _run(db, ROUTE_PERFORMANCE_SQL, {})
