"""Shipments REST endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/shipments", tags=["shipments"])


@router.get("")
def list_shipments(
    status: str | None = None,
    sla_status: str | None = None,
    carrier_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    filters, params = [], {"limit": page_size, "offset": offset}
    if status:       filters.append("s.status=:status");      params["status"] = status
    if sla_status:   filters.append("s.sla_status=:sla");     params["sla"] = sla_status
    if carrier_id:   filters.append("s.carrier_id=:cid");     params["cid"] = carrier_id
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    rows = db.execute(text(f"""
        SELECT s.shipment_id, s.status, s.sla_status, s.priority,
               s.planned_ship_time, s.promised_delivery_time, s.actual_delivery_time,
               c.carrier_name, s.carrier_id, s.service_level_id,
               s.origin_facility_id, s.destination_facility_id, s.is_demo
        FROM shipments s
        JOIN carriers c ON s.carrier_id = c.carrier_id
        {where}
        ORDER BY s.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().fetchall()

    total = db.execute(text(f"SELECT COUNT(*) FROM shipments s {where}"),
                       {k: v for k, v in params.items() if k not in ("limit","offset")}).scalar()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [dict(r) for r in rows]}


@router.get("/{shipment_id}")
def get_shipment(shipment_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(text("""
        SELECT s.*, c.carrier_name, c.carrier_code, r.route_name,
               r.distance_km AS route_distance_km, r.base_transit_hours,
               sl.name AS service_level_name, sl.maximum_delivery_hours,
               fo.facility_name AS origin_name, fo.city AS origin_city,
               fd.facility_name AS dest_name, fd.city AS dest_city
        FROM shipments s
        JOIN carriers c ON s.carrier_id=c.carrier_id
        JOIN routes r ON s.route_id=r.route_id
        JOIN service_levels sl ON s.service_level_id=sl.service_level_id
        JOIN facilities fo ON s.origin_facility_id=fo.facility_id
        JOIN facilities fd ON s.destination_facility_id=fd.facility_id
        WHERE s.shipment_id=:sid
    """), {"sid": shipment_id}).mappings().fetchone()
    if not row:
        raise HTTPException(404, f"Shipment {shipment_id} not found")
    return dict(row)


@router.get("/{shipment_id}/tracking")
def get_tracking(shipment_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT te.event_id, te.event_type, te.event_time, te.ingestion_time,
               te.facility_id, f.facility_name, te.description, te.source,
               te.is_duplicate, te.is_late_arrival
        FROM tracking_events te
        LEFT JOIN facilities f ON te.facility_id=f.facility_id
        WHERE te.shipment_id=:sid
        ORDER BY te.event_time
    """), {"sid": shipment_id}).mappings().fetchall()
    return [dict(r) for r in rows]


@router.get("/{shipment_id}/eta")
def get_eta(shipment_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT * FROM eta_estimates
        WHERE shipment_id=:sid
        ORDER BY prediction_time DESC
        LIMIT 10
    """), {"sid": shipment_id}).mappings().fetchall()
    return [dict(r) for r in rows]


@router.get("/{shipment_id}/delay-risk")
def get_delay_risk(shipment_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    latest = db.execute(text("""
        SELECT delay_probability, predicted_eta, model_version, prediction_time
        FROM eta_estimates WHERE shipment_id=:sid
        ORDER BY prediction_time DESC LIMIT 1
    """), {"sid": shipment_id}).mappings().fetchone()
    if not latest:
        return {"shipment_id": shipment_id, "delay_probability": None, "message": "No ETA estimate available"}
    return {**dict(latest), "shipment_id": shipment_id}


@router.get("/{shipment_id}/explanation")
def get_explanation(shipment_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(text("""
        SELECT pe.*, eta.model_version
        FROM prediction_explanations pe
        LEFT JOIN eta_estimates eta ON pe.eta_estimate_id=eta.eta_estimate_id
        WHERE pe.shipment_id=:sid
        ORDER BY pe.created_at DESC LIMIT 1
    """), {"sid": shipment_id}).mappings().fetchone()
    if not row:
        return {"shipment_id": shipment_id, "message": "No explanation available yet"}
    return dict(row)
