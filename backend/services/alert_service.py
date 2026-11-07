"""Alert and Notification service (Phase 15).

Responsibilities:
  1. Generate alerts from DB records and configured rules.
  2. Prevent duplicate alerts for the same unresolved condition (dedup_key).
  3. Create in-app notifications for affected users.
  4. Support acknowledgement and resolution.
  5. Persist everything in PostgreSQL.

Alert types: HIGH_DELAY_RISK, SLA_AT_RISK, SLA_BREACH,
  FACILITY_CONGESTION, WEATHER_DISRUPTION, ROUTE_DEVIATION,
  MISSING_SCAN, LATE_EVENT, DATA_QUALITY_ERROR
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from data_engineering.generator.ids import alert_id

log = logging.getLogger("backend.services.alert_service")

# Severity thresholds
_DELAY_RISK_THRESHOLD = 0.7     # delay_probability > 0.7 → HIGH_DELAY_RISK
_FACILITY_UTIL_THRESHOLD = 90   # utilization > 90% → FACILITY_CONGESTION
_LATE_EVENT_LAG_HOURS = 48      # ingestion lag > 48h → LATE_EVENT


def _create_alert(
    db: Session,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    dedup_key: str,
    shipment_id: str | None = None,
    facility_id: str | None = None,
    carrier_id: str | None = None,
) -> str | None:
    """Insert an alert if no OPEN alert with the same dedup_key exists.

    Returns the alert_id if created, None if deduplicated.
    """
    existing = db.execute(text("""
        SELECT 1 FROM alerts
        WHERE dedup_key = :dk AND status = 'OPEN'
        LIMIT 1
    """), {"dk": dedup_key}).scalar()

    if existing:
        return None  # deduplicated

    now = datetime.now(timezone.utc)
    aid = alert_id(now, abs(hash(dedup_key)) % 9999)

    db.execute(text("""
        INSERT INTO alerts (
            alert_id, alert_type, severity, title, message,
            shipment_id, facility_id, carrier_id,
            status, dedup_key, is_demo, created_at, updated_at
        ) VALUES (
            :aid, :at, :sev, :title, :msg,
            :sid, :fid, :cid,
            'OPEN', :dk, TRUE, :now, :now
        ) ON CONFLICT (alert_id) DO NOTHING
    """), {
        "aid": aid, "at": alert_type, "sev": severity,
        "title": title, "msg": message,
        "sid": shipment_id, "fid": facility_id, "cid": carrier_id,
        "dk": dedup_key, "now": now,
    })
    db.commit()
    log.info("alert created: type=%s severity=%s id=%s", alert_type, severity, aid)
    return aid


def _create_notification(
    db: Session,
    user_id: str,
    title: str,
    body: str,
    severity: str = "MEDIUM",
    alert_id: str | None = None,
    shipment_id: str | None = None,
) -> str:
    """Create an in-app notification for a user."""
    now = datetime.now(timezone.utc)
    nid = f"NTF-{now.strftime('%Y%m%d%H%M%S')}-{abs(hash(title+user_id))%9999:04d}"

    db.execute(text("""
        INSERT INTO notifications (
            notification_id, user_id, alert_id, title, body,
            severity, is_read, read_at,
            shipment_id, created_at, updated_at
        ) VALUES (
            :nid, :uid, :aid, :title, :body,
            :sev, FALSE, NULL,
            :sid, :now, :now
        ) ON CONFLICT (notification_id) DO NOTHING
    """), {
        "nid": nid, "uid": user_id, "aid": alert_id,
        "title": title, "body": body, "sev": severity,
        "sid": shipment_id, "now": now,
    })
    db.commit()
    return nid


def generate_high_delay_risk_alerts(db: Session) -> int:
    """Generate HIGH_DELAY_RISK alerts for shipments with high delay probability."""
    rows = db.execute(text("""
        SELECT DISTINCT ON (e.shipment_id)
            e.shipment_id, e.delay_probability, e.predicted_eta,
            s.promised_delivery_time, s.carrier_id
        FROM eta_estimates e
        JOIN shipments s ON e.shipment_id = s.shipment_id
        WHERE e.delay_probability > :thresh
          AND s.status NOT IN ('DELIVERED', 'CANCELLED')
        ORDER BY e.shipment_id, e.prediction_time DESC
    """), {"thresh": _DELAY_RISK_THRESHOLD}).mappings().fetchall()

    count = 0
    for row in rows:
        r = dict(row)
        aid = _create_alert(
            db, "HIGH_DELAY_RISK", "HIGH",
            f"High Delay Risk: {r['shipment_id']}",
            f"Shipment {r['shipment_id']} has {round(float(r['delay_probability'])*100)}% delay probability. "
            f"Predicted ETA: {r['predicted_eta']}, Promised: {r['promised_delivery_time']}.",
            f"HDR-{r['shipment_id']}",
            shipment_id=r["shipment_id"],
            carrier_id=r.get("carrier_id"),
        )
        if aid:
            count += 1
    return count


def generate_facility_congestion_alerts(db: Session) -> int:
    """Generate FACILITY_CONGESTION alerts for facilities with high utilization."""
    rows = db.execute(text("""
        SELECT fq.facility_id, fq.utilization_pct, fq.queue_length, fq.capacity,
               f.facility_name, f.city
        FROM facility_queues fq
        JOIN facilities f ON fq.facility_id = f.facility_id
        WHERE fq.utilization_pct > :thresh
          AND fq.timestamp >= NOW() - INTERVAL '4 hours'
          AND fq.timestamp = (
              SELECT MAX(timestamp) FROM facility_queues fq2
              WHERE fq2.facility_id = fq.facility_id
          )
        ORDER BY fq.utilization_pct DESC
    """), {"thresh": _FACILITY_UTIL_THRESHOLD}).mappings().fetchall()

    count = 0
    for row in rows:
        r = dict(row)
        aid = _create_alert(
            db, "FACILITY_CONGESTION", "HIGH",
            f"Facility Congestion: {r['facility_name']}",
            f"Facility {r['facility_name']} ({r['city']}) at {round(float(r['utilization_pct']))}% utilization "
            f"({r['queue_length']}/{r['capacity']} queue).",
            f"FC-{r['facility_id']}",
            facility_id=r["facility_id"],
        )
        if aid:
            count += 1
    return count


def generate_weather_disruption_alerts(db: Session) -> int:
    """Generate WEATHER_DISRUPTION alerts for active severe weather events."""
    rows = db.execute(text("""
        SELECT weather_event_id, location, weather_type, severity, delay_factor,
               start_time, end_time
        FROM weather_events
        WHERE delay_factor >= 1.35
          AND end_time >= NOW()
        ORDER BY severity DESC
    """)).mappings().fetchall()

    count = 0
    for row in rows:
        r = dict(row)
        sev = "CRITICAL" if r["severity"] >= 4 else "HIGH"
        aid = _create_alert(
            db, "WEATHER_DISRUPTION", sev,
            f"Weather Disruption: {r['weather_type']} at {r['location']}",
            f"{r['weather_type'].replace('_',' ').title()} near {r['location']} "
            f"(severity {r['severity']}/4, delay factor {r['delay_factor']}). "
            f"Active until {r['end_time']}.",
            f"WD-{r['weather_event_id']}",
        )
        if aid:
            count += 1
    return count


def generate_missing_scan_alerts(db: Session) -> int:
    """Generate MISSING_SCAN alerts for shipments with event gaps > 24h."""
    rows = db.execute(text("""
        WITH last_events AS (
            SELECT shipment_id, MAX(event_time) AS last_event
            FROM tracking_events
            GROUP BY shipment_id
        )
        SELECT s.shipment_id, le.last_event, s.status, s.carrier_id
        FROM shipments s
        JOIN last_events le ON s.shipment_id = le.shipment_id
        WHERE s.status NOT IN ('DELIVERED', 'CANCELLED')
          AND le.last_event < NOW() - INTERVAL '24 hours'
    """)).mappings().fetchall()

    count = 0
    for row in rows:
        r = dict(row)
        aid = _create_alert(
            db, "MISSING_SCAN", "MEDIUM",
            f"Missing Scan: {r['shipment_id']}",
            f"Shipment {r['shipment_id']} (status: {r['status']}) has no tracking event "
            f"in the last 24 hours. Last event: {r['last_event']}.",
            f"MS-{r['shipment_id']}",
            shipment_id=r["shipment_id"],
            carrier_id=r.get("carrier_id"),
        )
        if aid:
            count += 1
    return count


def generate_data_quality_alerts(db: Session) -> int:
    """Generate DATA_QUALITY_ERROR alerts for unresolved DQ issues."""
    rows = db.execute(text("""
        SELECT issue_id, issue_type, entity_type, entity_id, severity, description
        FROM data_quality_issues
        WHERE is_resolved = FALSE
          AND severity IN ('HIGH', 'CRITICAL')
    """)).mappings().fetchall()

    count = 0
    for row in rows:
        r = dict(row)
        aid = _create_alert(
            db, "DATA_QUALITY_ERROR", r["severity"],
            f"Data Quality Issue: {r['issue_type']}",
            f"{r['description']} (entity: {r['entity_type']}:{r['entity_id']})",
            f"DQ-{r['issue_id']}",
        )
        if aid:
            count += 1
    return count


def run_alert_generation(db: Session) -> dict:
    """Run all alert generators. Returns aggregate stats."""
    results = {
        "high_delay_risk": generate_high_delay_risk_alerts(db),
        "facility_congestion": generate_facility_congestion_alerts(db),
        "weather_disruption": generate_weather_disruption_alerts(db),
        "missing_scan": generate_missing_scan_alerts(db),
        "data_quality": generate_data_quality_alerts(db),
    }
    total_new = sum(results.values())

    # Create notifications for all active users
    users = db.execute(text(
        "SELECT user_id FROM users WHERE is_active = TRUE"
    )).fetchall()
    if total_new > 0 and users:
        open_alerts = db.execute(text("""
            SELECT alert_id, title, severity, shipment_id FROM alerts
            WHERE status = 'OPEN' ORDER BY created_at DESC LIMIT 20
        """)).mappings().fetchall()
        for alert in open_alerts:
            for user in users:
                _create_notification(
                    db, user[0],
                    alert["title"],
                    f"New alert: {alert['title']} (severity: {alert['severity']})",
                    alert["severity"],
                    alert_id=str(alert["alert_id"]),
                    shipment_id=str(alert["shipment_id"]) if alert["shipment_id"] else None,
                )

    log.info("alert generation: total_new=%d %s", total_new, results)
    return {
        "new_alerts": total_new,
        "by_type": results,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


def acknowledge_alert(db: Session, alert_id: str, user_id: str) -> bool:
    """Acknowledge an alert."""
    now = datetime.now(timezone.utc)
    result = db.execute(text("""
        UPDATE alerts
        SET status = 'ACKNOWLEDGED', acknowledged_by = :uid,
            acknowledged_at = :now, updated_at = :now
        WHERE alert_id = :aid AND status = 'OPEN'
    """), {"aid": alert_id, "uid": user_id, "now": now})
    db.commit()
    return result.rowcount > 0


def resolve_alert(db: Session, alert_id: str, user_id: str) -> bool:
    """Resolve an alert."""
    now = datetime.now(timezone.utc)
    result = db.execute(text("""
        UPDATE alerts
        SET status = 'RESOLVED', acknowledged_by = :uid,
            resolved_at = :now, updated_at = :now
        WHERE alert_id = :aid AND status IN ('OPEN', 'ACKNOWLEDGED')
    """), {"aid": alert_id, "uid": user_id, "now": now})
    db.commit()
    return result.rowcount > 0


def mark_notification_read(db: Session, notification_id: str) -> bool:
    """Mark a single notification as read."""
    now = datetime.now(timezone.utc)
    result = db.execute(text("""
        UPDATE notifications
        SET is_read = TRUE, read_at = :now, updated_at = :now
        WHERE notification_id = :nid AND is_read = FALSE
    """), {"nid": notification_id, "now": now})
    db.commit()
    return result.rowcount > 0


def mark_all_notifications_read(db: Session, user_id: str) -> int:
    """Mark all unread notifications for a user as read."""
    now = datetime.now(timezone.utc)
    result = db.execute(text("""
        UPDATE notifications
        SET is_read = TRUE, read_at = :now, updated_at = :now
        WHERE user_id = :uid AND is_read = FALSE
    """), {"uid": user_id, "now": now})
    db.commit()
    return result.rowcount


def get_notification_stats(db: Session, user_id: str) -> dict:
    """Get unread/read counts for a user."""
    row = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN is_read = FALSE THEN 1 ELSE 0 END) AS unread,
            SUM(CASE WHEN is_read = TRUE THEN 1 ELSE 0 END) AS read
        FROM notifications WHERE user_id = :uid
    """), {"uid": user_id}).mappings().fetchone()
    return dict(row) if row else {"total": 0, "unread": 0, "read": 0}
