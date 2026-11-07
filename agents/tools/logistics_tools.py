"""Logistics agent tools.

Each tool is a function that queries live PostgreSQL data.
The agent NEVER guesses — it calls tools to get verified operational data.

Tool outputs are JSON-serialisable dicts.
Error handling: tools catch exceptions and return {"error": ...} dicts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("agents.tools.logistics_tools")


def get_shipment(db: Session, shipment_id: str) -> dict:
    """Get full shipment details by ID."""
    try:
        row = db.execute(text("""
            SELECT s.shipment_id, s.status, s.sla_status, s.priority,
                   s.planned_ship_time, s.promised_delivery_time, s.actual_delivery_time,
                   s.weight_kg, s.distance_km,
                   c.carrier_name, c.carrier_code, c.base_delay_factor,
                   sl.name AS service_level, sl.maximum_delivery_hours,
                   r.route_name, r.distance_km AS route_distance, r.base_transit_hours,
                   fo.facility_name AS origin_name, fo.city AS origin_city,
                   fd.facility_name AS dest_name, fd.city AS dest_city
            FROM shipments s
            JOIN carriers c ON s.carrier_id = c.carrier_id
            JOIN service_levels sl ON s.service_level_id = sl.service_level_id
            JOIN routes r ON s.route_id = r.route_id
            JOIN facilities fo ON s.origin_facility_id = fo.facility_id
            JOIN facilities fd ON s.destination_facility_id = fd.facility_id
            WHERE s.shipment_id = :sid
        """), {"sid": shipment_id}).mappings().fetchone()
        return dict(row) if row else {"error": f"Shipment {shipment_id} not found"}
    except Exception as e:
        return {"error": str(e)}


def get_tracking_events(db: Session, shipment_id: str) -> list[dict]:
    """Get tracking events for a shipment."""
    try:
        rows = db.execute(text("""
            SELECT event_id, event_type, event_time, ingestion_time,
                   facility_id, description, source,
                   is_duplicate, is_late_arrival
            FROM tracking_events WHERE shipment_id = :sid
            ORDER BY event_time
        """), {"sid": shipment_id}).mappings().fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


def get_eta(db: Session, shipment_id: str) -> dict:
    """Get the latest ETA estimate for a shipment."""
    try:
        row = db.execute(text("""
            SELECT eta_estimate_id, predicted_eta, predicted_remaining_hours,
                   delay_probability, model_version, model_type,
                   prediction_time, feature_cutoff_time
            FROM eta_estimates WHERE shipment_id = :sid
            ORDER BY prediction_time DESC LIMIT 1
        """), {"sid": shipment_id}).mappings().fetchone()
        return dict(row) if row else {"error": "No ETA estimate available"}
    except Exception as e:
        return {"error": str(e)}


def get_delay_risk(db: Session, shipment_id: str) -> dict:
    """Get delay risk for a shipment (uses ML model if available)."""
    try:
        from ml.delay.predict import predict_delay_ml
        return predict_delay_ml(db, shipment_id)
    except Exception as e:
        return {"error": str(e)}


def get_weather(db: Session, location: str | None = None) -> list[dict]:
    """Get active weather events, optionally filtered by location."""
    try:
        sql = """
            SELECT weather_event_id, location, weather_type, severity,
                   delay_factor, start_time, end_time
            FROM weather_events WHERE end_time >= NOW()
        """
        params = {}
        if location:
            sql += " AND location ILIKE :loc"
            params["loc"] = f"%{location}%"
        sql += " ORDER BY severity DESC LIMIT 10"
        rows = db.execute(text(sql), params).mappings().fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


def get_facility_queue(db: Session, facility_id: str) -> list[dict]:
    """Get the latest queue snapshots for a facility."""
    try:
        rows = db.execute(text("""
            SELECT queue_id, timestamp, queue_length, capacity,
                   utilization_pct, average_processing_time_minutes
            FROM facility_queues WHERE facility_id = :fid
            ORDER BY timestamp DESC LIMIT 10
        """), {"fid": facility_id}).mappings().fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


def get_carrier_performance(db: Session, carrier_id: str) -> dict:
    """Get carrier performance metrics."""
    try:
        row = db.execute(text("""
            SELECT cp.* FROM carrier_performance cp
            WHERE cp.carrier_id = :cid AND cp.perf_id LIKE 'CP-%-GOLD'
            LIMIT 1
        """), {"cid": carrier_id}).mappings().fetchone()
        return dict(row) if row else {"error": "No performance data for this carrier"}
    except Exception as e:
        return {"error": str(e)}


def search_policy(db: Session, query: str, n_results: int = 5) -> list[dict]:
    """Search RAG policy documents for relevant content."""
    try:
        from rag.retrieval.search import search_policies
        return search_policies(db, query, n_results=n_results)
    except Exception as e:
        return [{"error": str(e)}]


def get_sla_status(db: Session, shipment_id: str) -> dict:
    """Get SLA status for a shipment."""
    try:
        row = db.execute(text("""
            SELECT shipment_id, sla_status, status, promised_delivery_time,
                   actual_delivery_time
            FROM shipments WHERE shipment_id = :sid
        """), {"sid": shipment_id}).mappings().fetchone()
        return dict(row) if row else {"error": f"Shipment {shipment_id} not found"}
    except Exception as e:
        return {"error": str(e)}


def compare_routes(
    db: Session,
    shipment_id: str,
    alternative_route_id: str | None = None,
) -> dict:
    """Compare current route with an alternative route (what-if analysis).

    Returns estimated delivery time, delay probability, and cost comparison.
    Uses documented simulation rules — never claims verified carrier quotations.
    """
    try:
        shp = db.execute(text("""
            SELECT s.shipment_id, s.route_id, s.planned_ship_time,
                   s.promised_delivery_time, r.distance_km, r.base_transit_hours,
                   c.base_delay_factor
            FROM shipments s
            JOIN routes r ON s.route_id = r.route_id
            JOIN carriers c ON s.carrier_id = c.carrier_id
            WHERE s.shipment_id = :sid
        """), {"sid": shipment_id}).mappings().fetchone()

        if not shp:
            return {"error": f"Shipment {shipment_id} not found"}

        current = dict(shp)
        current_eta_h = float(current["base_transit_hours"]) * float(current["base_delay_factor"])

        if alternative_route_id:
            alt = db.execute(text("""
                SELECT route_id, distance_km, base_transit_hours
                FROM routes WHERE route_id = :rid
            """), {"rid": alternative_route_id}).mappings().fetchone()
            if not alt:
                return {"error": f"Alternative route {alternative_route_id} not found"}
            alt = dict(alt)
            alt_eta_h = float(alt["base_transit_hours"]) * float(current["base_delay_factor"])
            time_saved = round(current_eta_h - alt_eta_h, 2)
            # Cost estimate: ₹8/km (documented simulation rule)
            current_cost = round(float(current["distance_km"]) * 8, 0)
            alt_cost = round(float(alt["distance_km"]) * 8, 0)
            return {
                "shipment_id": shipment_id,
                "current_route_id": current["route_id"],
                "alternative_route_id": alternative_route_id,
                "current_eta_hours": round(current_eta_h, 2),
                "alternative_eta_hours": round(alt_eta_h, 2),
                "time_saved_hours": time_saved,
                "current_cost": current_cost,
                "alternative_cost": alt_cost,
                "additional_cost": alt_cost - current_cost,
                "note": "SIMULATION — costs are estimated using documented rules, not verified carrier quotations.",
            }
        else:
            return {
                "shipment_id": shipment_id,
                "current_route_id": current["route_id"],
                "current_eta_hours": round(current_eta_h, 2),
                "note": "No alternative route specified. Provide alternative_route_id for comparison.",
            }
    except Exception as e:
        return {"error": str(e)}


def generate_report(db: Session, report_type: str = "summary") -> dict:
    """Generate an operational report."""
    try:
        if report_type == "summary":
            row = db.execute(text("""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status='DELIVERED' THEN 1 ELSE 0 END) AS delivered,
                       SUM(CASE WHEN sla_status='BREACHED' THEN 1 ELSE 0 END) AS breached,
                       SUM(CASE WHEN sla_status='AT_RISK' THEN 1 ELSE 0 END) AS at_risk
                FROM shipments
            """)).mappings().fetchone()
            return dict(row)
        elif report_type == "carriers":
            rows = db.execute(text("""
                SELECT c.carrier_name, cp.on_time_rate, cp.carrier_score, cp.total_shipments
                FROM carrier_performance cp
                JOIN carriers c ON cp.carrier_id = c.carrier_id
                WHERE cp.perf_id LIKE 'CP-%-GOLD'
                ORDER BY cp.carrier_score DESC
            """)).mappings().fetchall()
            return {"carriers": [dict(r) for r in rows]}
        else:
            return {"error": f"Unknown report type: {report_type}"}
    except Exception as e:
        return {"error": str(e)}


def search_shipments(db: Session, status: str | None = None, sla_status: str | None = None,
                     limit: int = 10) -> list[dict]:
    """Search shipments by status or SLA status."""
    try:
        filters, params = [], {"limit": limit}
        if status:
            filters.append("s.status = :status")
            params["status"] = status.upper()
        if sla_status:
            filters.append("s.sla_status = :sla")
            params["sla"] = sla_status.upper()
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        rows = db.execute(text(f"""
            SELECT s.shipment_id, s.status, s.sla_status, s.priority,
                   c.carrier_name, s.promised_delivery_time
            FROM shipments s
            JOIN carriers c ON s.carrier_id = c.carrier_id
            {where}
            ORDER BY s.created_at DESC
            LIMIT :limit
        """), params).mappings().fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


def get_high_risk_shipments(db: Session, limit: int = 20) -> list[dict]:
    """Get shipments at high delay risk (AT_RISK or BREACHED SLA, high delay probability)."""
    try:
        rows = db.execute(text("""
            SELECT s.shipment_id, s.status, s.sla_status, s.priority,
                   c.carrier_name, s.promised_delivery_time,
                   e.delay_probability, e.predicted_eta
            FROM shipments s
            JOIN carriers c ON s.carrier_id = c.carrier_id
            LEFT JOIN LATERAL (
                SELECT delay_probability, predicted_eta FROM eta_estimates
                WHERE shipment_id = s.shipment_id
                ORDER BY prediction_time DESC LIMIT 1
            ) e ON TRUE
            WHERE s.sla_status IN ('AT_RISK','BREACHED')
               OR (e.delay_probability IS NOT NULL AND e.delay_probability > 0.6)
            ORDER BY e.delay_probability DESC NULLS LAST, s.promised_delivery_time ASC
            LIMIT :limit
        """), {"limit": limit}).mappings().fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


def get_sla_statistics(db: Session) -> dict:
    """Get SLA compliance statistics."""
    try:
        row = db.execute(text("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN sla_status='ON_TIME'  THEN 1 ELSE 0 END) AS on_time,
                   SUM(CASE WHEN sla_status='AT_RISK'  THEN 1 ELSE 0 END) AS at_risk,
                   SUM(CASE WHEN sla_status='BREACHED' THEN 1 ELSE 0 END) AS breached,
                   ROUND(SUM(CASE WHEN sla_status='ON_TIME' THEN 1 ELSE 0 END)::NUMERIC /
                         NULLIF(COUNT(*),0)*100, 2) AS compliance_pct
            FROM shipments
        """)).mappings().fetchone()
        return dict(row) if row else {}
    except Exception as e:
        return {"error": str(e)}


def search_knowledge_base(db: Session, query: str, n_results: int = 5) -> list[dict]:
    """Search the RAG knowledge base for relevant logistics information."""
    try:
        from rag.retrieval.search import search_policies
        results = search_policies(db, query, n_results=n_results)
        return results
    except Exception as e:
        return [{"error": str(e)}]


def generate_logistics_summary(db: Session) -> dict:
    """Generate a comprehensive logistics operations summary."""
    try:
        summary = db.execute(text("""
            SELECT COUNT(*) AS total_shipments,
                   SUM(CASE WHEN status='DELIVERED' THEN 1 ELSE 0 END) AS delivered,
                   SUM(CASE WHEN status NOT IN ('DELIVERED','CANCELLED') THEN 1 ELSE 0 END) AS in_transit,
                   SUM(CASE WHEN sla_status='BREACHED' THEN 1 ELSE 0 END) AS sla_breached,
                   SUM(CASE WHEN sla_status='AT_RISK'  THEN 1 ELSE 0 END) AS at_risk,
                   ROUND(SUM(CASE WHEN sla_status='ON_TIME' THEN 1 ELSE 0 END)::NUMERIC /
                         NULLIF(COUNT(*),0)*100, 2) AS on_time_pct
            FROM shipments
        """)).mappings().fetchone()

        carriers_row = db.execute(text("""
            SELECT c.carrier_name, cp.carrier_score, cp.on_time_rate
            FROM carrier_performance cp
            JOIN carriers c ON cp.carrier_id=c.carrier_id
            WHERE cp.perf_id LIKE 'CP-%-GOLD'
            ORDER BY cp.carrier_score ASC LIMIT 1
        """)).mappings().fetchone()

        alerts_row = db.execute(text(
            "SELECT COUNT(*) FROM alerts WHERE status='OPEN'"
        )).scalar()

        return {
            "operations_summary": dict(summary) if summary else {},
            "worst_carrier": dict(carriers_row) if carriers_row else None,
            "open_alerts": int(alerts_row or 0),
        }
    except Exception as e:
        return {"error": str(e)}


# Registry: maps tool names to functions for the agent to use
TOOL_REGISTRY = {
    "get_shipment":             get_shipment,
    "get_tracking_events":      get_tracking_events,
    "get_eta":                  get_eta,
    "get_delay_risk":           get_delay_risk,
    "get_weather":              get_weather,
    "get_facility_queue":       get_facility_queue,
    "get_carrier_performance":  get_carrier_performance,
    "search_policy":            search_policy,
    "get_sla_status":           get_sla_status,
    "compare_routes":           compare_routes,
    "generate_report":          generate_report,
    # New enhanced tools
    "search_shipments":         search_shipments,
    "get_high_risk_shipments":  get_high_risk_shipments,
    "get_sla_statistics":       get_sla_statistics,
    "search_knowledge_base":    search_knowledge_base,
    "generate_logistics_summary": generate_logistics_summary,
}
