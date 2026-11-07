"""Analytics, carriers, facilities, delays, ETA predict endpoints."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user
from database.queries.analytics import (
    top_delayed_carriers, top_congested_facilities,
    sla_compliance, carrier_ranking, route_performance, high_risk_shipments,
)

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db), _=Depends(get_current_user)):
    totals = db.execute(text("""
        WITH stats AS (
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN s.status='DELIVERED' THEN 1 ELSE 0 END) AS delivered,
                SUM(CASE WHEN s.status NOT IN ('DELIVERED','CANCELLED') THEN 1 ELSE 0 END) AS in_transit,
                SUM(CASE WHEN s.sla_status='BREACHED' THEN 1 ELSE 0 END) AS delayed,
                SUM(CASE WHEN s.sla_status IN ('BREACHED','AT_RISK') THEN 1 ELSE 0 END) AS high_risk,
                ROUND(AVG(CASE WHEN ss.delay_hours > 0 THEN ss.delay_hours END)::NUMERIC,2) AS avg_delay_hours,
                SUM(CASE WHEN s.sla_status='ON_TIME' THEN 1 ELSE 0 END) AS on_time_count
            FROM shipments s
            LEFT JOIN silver_shipments ss ON s.shipment_id=ss.shipment_id
        )
        SELECT total, delivered, in_transit, delayed, high_risk, avg_delay_hours,
               ROUND(on_time_count::NUMERIC / NULLIF(total,0) * 100, 2) AS on_time_pct,
               ROUND(on_time_count::NUMERIC / NULLIF(total,0) * 100, 2) AS sla_compliance_pct
        FROM stats
    """)).mappings().fetchone()
    return dict(totals)


@router.post("/eta/predict")
def predict_eta(payload: dict, db: Session = Depends(get_db), _=Depends(get_current_user)):
    from backend.services.eta_engine import predict_eta as _predict
    sid = payload.get("shipment_id")
    if not sid:
        raise HTTPException(422, "shipment_id required")
    result = _predict(db, sid)
    if not result:
        raise HTTPException(404, f"Shipment {sid} not found")
    return result


@router.get("/delays")
def list_delays(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT s.shipment_id, s.sla_status, s.status, s.priority,
               c.carrier_name, ss.delay_hours,
               s.promised_delivery_time, s.actual_delivery_time
        FROM shipments s
        JOIN carriers c ON s.carrier_id=c.carrier_id
        LEFT JOIN silver_shipments ss ON s.shipment_id=ss.shipment_id
        WHERE s.sla_status IN ('BREACHED','AT_RISK')
        ORDER BY ss.delay_hours DESC NULLS LAST
        LIMIT 100
    """)).mappings().fetchall()
    return [dict(r) for r in rows]


@router.get("/carriers")
def list_carriers(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text(
        "SELECT carrier_id,carrier_name,carrier_code,is_active,base_delay_factor FROM carriers ORDER BY carrier_name"
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.get("/carriers/{carrier_id}/performance")
def carrier_performance(carrier_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(text(
        "SELECT * FROM carrier_performance WHERE carrier_id=:cid ORDER BY period_end DESC LIMIT 1"
    ), {"cid": carrier_id}).mappings().fetchone()
    if not row:
        raise HTTPException(404, "No performance data for this carrier")
    return dict(row)


@router.get("/facilities")
def list_facilities(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text(
        "SELECT * FROM facilities ORDER BY facility_name"
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.get("/facilities/{facility_id}/queue")
def facility_queue(facility_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT queue_id, timestamp, queue_length, capacity, utilization_pct,
               average_processing_time_minutes
        FROM facility_queues WHERE facility_id=:fid
        ORDER BY timestamp DESC LIMIT 48
    """), {"fid": facility_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# ── Alerts ────────────────────────────────────────────────────────────────────
alerts_router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@alerts_router.get("")
def list_alerts(
    status: str | None = None, severity: str | None = None,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    filters, params = [], {}
    if status:   filters.append("a.status=:st");  params["st"] = status
    if severity: filters.append("a.severity=:se"); params["se"] = severity
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = db.execute(text(f"""
        SELECT a.alert_id, a.alert_type, a.severity, a.title, a.message,
               a.shipment_id, a.facility_id, a.carrier_id, a.status,
               a.created_at, a.acknowledged_at, a.resolved_at
        FROM alerts a {where}
        ORDER BY a.created_at DESC LIMIT 100
    """), params).mappings().fetchall()
    return [dict(r) for r in rows]


@alerts_router.post("/{alert_id}/acknowledge")
def ack_alert(alert_id: str, db: Session = Depends(get_db),
              user=Depends(get_current_user)):
    from backend.services.alert_service import acknowledge_alert
    ok = acknowledge_alert(db, alert_id, user["user_id"])
    if not ok:
        raise HTTPException(404, "Alert not found or not open")
    return {"status": "acknowledged", "alert_id": alert_id}


@alerts_router.post("/{alert_id}/resolve")
def resolve_alert_ep(alert_id: str, db: Session = Depends(get_db),
                     user=Depends(get_current_user)):
    from backend.services.alert_service import resolve_alert
    ok = resolve_alert(db, alert_id, user["user_id"])
    if not ok:
        raise HTTPException(404, "Alert not found or already resolved")
    return {"status": "resolved", "alert_id": alert_id}


# ── Notifications ─────────────────────────────────────────────────────────────
notif_router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@notif_router.get("")
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    where = "WHERE user_id=:uid"
    if unread_only:
        where += " AND is_read=FALSE"
    rows = db.execute(text(f"""
        SELECT notification_id, title, body, severity, is_read, read_at,
               shipment_id, alert_id, created_at
        FROM notifications {where}
        ORDER BY created_at DESC LIMIT 100
    """), {"uid": user["user_id"]}).mappings().fetchall()
    return [dict(r) for r in rows]


@notif_router.get("/stats")
def notif_stats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from backend.services.alert_service import get_notification_stats
    return get_notification_stats(db, user["user_id"])


@notif_router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db),
              user=Depends(get_current_user)):
    from backend.services.alert_service import mark_notification_read
    mark_notification_read(db, notification_id)
    return {"status": "read"}


@notif_router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from backend.services.alert_service import mark_all_notifications_read
    count = mark_all_notifications_read(db, user["user_id"])
    return {"marked_read": count}
