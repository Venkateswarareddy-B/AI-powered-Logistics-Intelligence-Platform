"""Delay Detection and SLA Monitoring Service (Phase 9).

Responsibilities:
  1. Classify each active shipment as ON_TIME / AT_RISK / BREACHED.
  2. Persist every meaningful status TRANSITION to audit_logs.
  3. Generate Alert rows when thresholds are crossed.
  4. Provide aggregate SLA compliance stats.
  5. Support periodic re-evaluation (called by background worker or on demand).

Business rules:
  - ON_TIME  : predicted_eta <= promised_delivery_time
  - AT_RISK  : predicted_eta > promised_delivery_time
               AND predicted_eta <= promised_delivery_time + allowed_delay_hours
  - BREACHED : predicted_eta > promised_delivery_time + allowed_delay_hours
               OR (actual_delivery_time IS NOT NULL
                   AND actual_delivery_time > promised_delivery_time
                                            + allowed_delay_hours)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("backend.services.sla_monitor")

# Alert dedup key prefix
_DEDUP_PREFIX = "SLA"


def _compute_sla_status(
    promised: datetime,
    allowed_delay_hours: float,
    predicted_eta: Optional[datetime],
    actual_delivery: Optional[datetime],
) -> str:
    """Pure function — derives SLA status from timestamps."""
    deadline = promised
    breach_cutoff = promised.replace(
        second=0, microsecond=0
    ) + __import__("datetime").timedelta(hours=allowed_delay_hours)

    # Delivered: use actual time
    if actual_delivery is not None:
        return "BREACHED" if actual_delivery > breach_cutoff else "ON_TIME"

    # In-flight: use predicted ETA
    if predicted_eta is None:
        return "ON_TIME"
    if predicted_eta > breach_cutoff:
        return "BREACHED"
    if predicted_eta > deadline:
        return "AT_RISK"
    return "ON_TIME"


def _latest_eta(db: Session, shipment_id: str) -> Optional[dict]:
    row = db.execute(text("""
        SELECT predicted_eta, delay_probability
        FROM eta_estimates
        WHERE shipment_id = :sid
        ORDER BY prediction_time DESC
        LIMIT 1
    """), {"sid": shipment_id}).mappings().fetchone()
    return dict(row) if row else None


def _ensure_alert(
    db: Session,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    shipment_id: str,
    dedup_key: str,
) -> None:
    """Insert alert only if no OPEN alert with same dedup_key exists."""
    exists = db.execute(text("""
        SELECT 1 FROM alerts
        WHERE dedup_key = :dk AND status = 'OPEN'
        LIMIT 1
    """), {"dk": dedup_key}).scalar()
    if exists:
        return

    from data_engineering.generator.ids import alert_id as _aid
    now = datetime.now(timezone.utc)
    aid = _aid(now, abs(hash(dedup_key)) % 9999)
    db.execute(text("""
        INSERT INTO alerts (
            alert_id, alert_type, severity, title, message,
            shipment_id, status, dedup_key, is_demo, created_at, updated_at
        ) VALUES (
            :aid, :at, :sev, :title, :msg,
            :sid, 'OPEN', :dk, TRUE, :now, :now
        ) ON CONFLICT (alert_id) DO NOTHING
    """), {
        "aid": aid, "at": alert_type, "sev": severity,
        "title": title, "msg": message, "sid": shipment_id,
        "dk": dedup_key, "now": now,
    })


def evaluate_shipment(db: Session, shipment_id: str) -> dict:
    """Evaluate SLA status for one shipment and persist transition if changed."""
    row = db.execute(text("""
        SELECT s.shipment_id, s.promised_delivery_time, s.actual_delivery_time,
               s.status, s.sla_status AS current_sla,
               sl.allowed_delay_hours
        FROM shipments s
        JOIN service_levels sl ON s.service_level_id = sl.service_level_id
        WHERE s.shipment_id = :sid
    """), {"sid": shipment_id}).mappings().fetchone()

    if not row:
        return {"error": f"Shipment {shipment_id} not found"}

    row = dict(row)
    eta_info = _latest_eta(db, shipment_id)
    predicted_eta = (
        datetime.fromisoformat(str(eta_info["predicted_eta"]))
        if eta_info and eta_info["predicted_eta"] else None
    )

    new_status = _compute_sla_status(
        promised=row["promised_delivery_time"],
        allowed_delay_hours=float(row["allowed_delay_hours"]),
        predicted_eta=predicted_eta,
        actual_delivery=row["actual_delivery_time"],
    )

    old_status = row["current_sla"]
    changed = new_status != old_status

    if changed:
        now = datetime.now(timezone.utc)
        db.execute(text("""
            UPDATE shipments SET sla_status = :ns, updated_at = :now
            WHERE shipment_id = :sid
        """), {"ns": new_status, "now": now, "sid": shipment_id})

        # Audit log the transition
        db.execute(text("""
            INSERT INTO audit_logs (
                audit_id, user_id, action, entity_type, entity_id,
                decision, reason, timestamp
            ) VALUES (
                :aid, NULL, 'SLA_STATUS_CHANGE', 'Shipment', :sid,
                :new_status,
                :reason,
                :now
            )
        """), {
            "aid": f"AUD-SLA-{shipment_id}-{now.strftime('%Y%m%d%H%M%S')}",
            "sid": shipment_id,
            "new_status": new_status,
            "reason": f"SLA transitioned {old_status} -> {new_status}",
            "now": now,
        })

        # Generate alert if breached or newly at risk
        if new_status == "BREACHED":
            _ensure_alert(
                db, "SLA_BREACH", "CRITICAL",
                f"SLA Breached: {shipment_id}",
                f"Shipment {shipment_id} has breached its SLA "
                f"(was {old_status}).",
                shipment_id,
                f"{_DEDUP_PREFIX}-BREACH-{shipment_id}",
            )
        elif new_status == "AT_RISK":
            _ensure_alert(
                db, "SLA_AT_RISK", "HIGH",
                f"SLA At Risk: {shipment_id}",
                f"Shipment {shipment_id} is at risk of breaching SLA "
                f"(was {old_status}).",
                shipment_id,
                f"{_DEDUP_PREFIX}-AT_RISK-{shipment_id}",
            )

        db.commit()

    return {
        "shipment_id": shipment_id,
        "previous_sla_status": old_status,
        "new_sla_status": new_status,
        "changed": changed,
        "predicted_eta": predicted_eta.isoformat() if predicted_eta else None,
        "delay_probability": float(eta_info["delay_probability"]) if eta_info and eta_info["delay_probability"] is not None else None,
    }


def run_sla_monitor(db: Session) -> dict:
    """Evaluate all active shipments. Returns aggregate stats."""
    rows = db.execute(text("""
        SELECT shipment_id FROM shipments
        WHERE status NOT IN ('DELIVERED', 'CANCELLED')
    """)).fetchall()
    sids = [r[0] for r in rows]

    transitions = 0
    breached = 0
    at_risk = 0
    on_time = 0

    for sid in sids:
        result = evaluate_shipment(db, sid)
        if result.get("changed"):
            transitions += 1
        ns = result.get("new_sla_status", "ON_TIME")
        if ns == "BREACHED":
            breached += 1
        elif ns == "AT_RISK":
            at_risk += 1
        else:
            on_time += 1

    # Also evaluate delivered shipments for final SLA recording
    delivered = db.execute(text("""
        SELECT shipment_id FROM shipments
        WHERE status = 'DELIVERED'
          AND actual_delivery_time IS NOT NULL
    """)).fetchall()
    for row in delivered:
        evaluate_shipment(db, row[0])

    # Aggregate compliance
    total = db.execute(text("SELECT COUNT(*) FROM shipments")).scalar()
    on_time_total = db.execute(text(
        "SELECT COUNT(*) FROM shipments WHERE sla_status = 'ON_TIME'"
    )).scalar()
    compliance_pct = round(int(on_time_total) / max(int(total), 1) * 100, 2)

    log.info(
        "sla_monitor: evaluated=%d transitions=%d on_time=%d at_risk=%d breached=%d compliance=%.1f%%",
        len(sids), transitions, on_time, at_risk, breached, compliance_pct,
    )

    return {
        "evaluated": len(sids),
        "transitions": transitions,
        "on_time": on_time,
        "at_risk": at_risk,
        "breached": breached,
        "compliance_pct": compliance_pct,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


def sla_summary(db: Session) -> dict:
    """Return current SLA compliance statistics."""
    row = db.execute(text("""
        SELECT
            COUNT(*)                                                          AS total,
            SUM(CASE WHEN sla_status = 'ON_TIME'  THEN 1 ELSE 0 END)        AS on_time,
            SUM(CASE WHEN sla_status = 'AT_RISK'  THEN 1 ELSE 0 END)        AS at_risk,
            SUM(CASE WHEN sla_status = 'BREACHED' THEN 1 ELSE 0 END)        AS breached,
            ROUND(
                SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END)::NUMERIC /
                NULLIF(COUNT(*), 0) * 100, 2
            )                                                                 AS compliance_pct
        FROM shipments
    """)).mappings().fetchone()
    return dict(row) if row else {}
