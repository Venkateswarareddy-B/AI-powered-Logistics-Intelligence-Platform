"""Route What-If Analysis Service (Phase 19).

Compares the current route with alternative routes and calculates:
  - Estimated delivery time (current vs alternative)
  - Delay probability (current vs alternative)
  - Additional cost
  - Risk reduction
  - Time saved
  - Recommended route

All numbers are calculated from documented simulation rules:
  - Base transit time from routes.base_transit_hours
  - Carrier delay factor from carriers.base_delay_factor
  - Weather delay factor from weather_events (active during shipment window)
  - Facility queue delay from facility_queues (utilization thresholds)
  - Cost estimate: ₹8/km (documented simulation rule, not a verified carrier quotation)

Never presents hypothetical calculations as verified carrier quotations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("backend.services.route_service")

# Documented simulation constants
COST_PER_KM = 8.0  # ₹8 per km — simulation rule, not a real carrier rate
_QUEUE_DELAY_MAP = [(90, 3.0), (75, 1.5), (60, 0.5)]  # utilization% → delay hours


def _get_route_info(db: Session, route_id: str) -> dict | None:
    row = db.execute(text("""
        SELECT route_id, route_name, origin_facility_id, destination_facility_id,
               distance_km, base_transit_hours
        FROM routes WHERE route_id = :rid
    """), {"rid": route_id}).mappings().fetchone()
    return dict(row) if row else None


def _get_weather_factor(db: Session, origin_id: str, dest_id: str,
                        ship_time: datetime, promised: datetime) -> float:
    row = db.execute(text("""
        SELECT COALESCE(MAX(we.delay_factor), 1.0)
        FROM weather_events we
        WHERE we.start_time <= :promised AND we.end_time >= :ship_time
    """), {"promised": promised, "ship_time": ship_time}).scalar()
    return float(row or 1.0)


def _get_queue_delay(db: Session, facility_id: str) -> float:
    row = db.execute(text("""
        SELECT utilization_pct
        FROM facility_queues WHERE facility_id = :fid
        ORDER BY timestamp DESC LIMIT 1
    """), {"fid": facility_id}).scalar()
    if row is None:
        return 0.0
    for threshold, delay in _QUEUE_DELAY_MAP:
        if float(row) >= threshold:
            return delay
    return 0.0


def _calculate_eta_hours(
    base_transit_hours: float,
    carrier_factor: float,
    weather_factor: float,
    origin_id: str,
    dest_id: str,
    db: Session,
) -> dict:
    """Calculate estimated delivery time and delay probability."""
    carrier_delay = base_transit_hours * (carrier_factor - 1.0)
    weather_delay = base_transit_hours * (weather_factor - 1.0)
    queue_delay = _get_queue_delay(db, origin_id) + _get_queue_delay(db, dest_id)

    total_hours = base_transit_hours + carrier_delay + weather_delay + queue_delay

    # Delay probability heuristic
    delay_prob = min(1.0, max(0.0,
        0.3 * (carrier_factor - 1.0) / 0.25 +
        0.3 * (weather_factor - 1.0) / 0.6 +
        0.4 * queue_delay / 4.0
    ))

    return {
        "estimated_hours": round(total_hours, 2),
        "carrier_delay_hours": round(carrier_delay, 2),
        "weather_delay_hours": round(weather_delay, 2),
        "queue_delay_hours": round(queue_delay, 2),
        "delay_probability": round(delay_prob, 4),
    }


def compare_routes(
    db: Session,
    shipment_id: str,
    alternative_route_id: str | None = None,
) -> dict:
    """Compare current route with all alternatives or a specific one.

    Args:
        db: Active session.
        shipment_id: The shipment to analyze.
        alternative_route_id: Specific alternative route. If None, finds all
                              routes between the same origin/destination.

    Returns:
        Comparison dict with current_route, alternatives, recommendation.
    """
    # Get shipment
    shp = db.execute(text("""
        SELECT s.shipment_id, s.route_id, s.planned_ship_time,
               s.promised_delivery_time, s.origin_facility_id,
               s.destination_facility_id, c.carrier_id, c.base_delay_factor,
               r.distance_km, r.base_transit_hours, r.route_name
        FROM shipments s
        JOIN routes r ON s.route_id = r.route_id
        JOIN carriers c ON s.carrier_id = c.carrier_id
        WHERE s.shipment_id = :sid
    """), {"sid": shipment_id}).mappings().fetchone()

    if not shp:
        return {"error": f"Shipment {shipment_id} not found"}

    shp = dict(shp)
    ship_time = shp["planned_ship_time"]
    promised = shp["promised_delivery_time"]
    carrier_factor = float(shp["base_delay_factor"])

    # Current route calculation
    weather_factor = _get_weather_factor(
        db, shp["origin_facility_id"], shp["destination_facility_id"],
        ship_time, promised,
    )
    current_calc = _calculate_eta_hours(
        float(shp["base_transit_hours"]), carrier_factor, weather_factor,
        shp["origin_facility_id"], shp["destination_facility_id"], db,
    )
    current_cost = round(float(shp["distance_km"]) * COST_PER_KM, 0)

    current_route = {
        "route_id": shp["route_id"],
        "route_name": shp["route_name"],
        "distance_km": float(shp["distance_km"]),
        "estimated_delivery_hours": current_calc["estimated_hours"],
        "delay_probability": current_calc["delay_probability"],
        "cost": current_cost,
        "breakdown": current_calc,
    }

    # Find alternative routes
    if alternative_route_id:
        alt_routes = [_get_route_info(db, alternative_route_id)]
        if alt_routes[0] is None:
            return {"error": f"Alternative route {alternative_route_id} not found"}
    else:
        # Find all routes that end at the same destination
        rows = db.execute(text("""
            SELECT * FROM routes
            WHERE destination_facility_id = :dest
              AND route_id != :current
              AND is_active = TRUE
            LIMIT 5
        """), {
            "dest": shp["destination_facility_id"],
            "current": shp["route_id"],
        }).mappings().fetchall()
        alt_routes = [dict(r) for r in rows]

    alternatives = []
    for alt in alt_routes:
        if alt is None:
            continue
        alt_weather = _get_weather_factor(
            db, alt["origin_facility_id"], alt["destination_facility_id"],
            ship_time, promised,
        )
        alt_calc = _calculate_eta_hours(
            float(alt["base_transit_hours"]), carrier_factor, alt_weather,
            alt["origin_facility_id"], alt["destination_facility_id"], db,
        )
        alt_cost = round(float(alt["distance_km"]) * COST_PER_KM, 0)

        time_saved = round(current_route["estimated_delivery_hours"] - alt_calc["estimated_hours"], 2)
        risk_reduction = round(current_route["delay_probability"] - alt_calc["delay_probability"], 4)
        additional_cost = alt_cost - current_cost

        alternatives.append({
            "route_id": alt["route_id"],
            "route_name": alt["route_name"],
            "distance_km": float(alt["distance_km"]),
            "estimated_delivery_hours": alt_calc["estimated_hours"],
            "delay_probability": alt_calc["delay_probability"],
            "cost": alt_cost,
            "time_saved_hours": time_saved,
            "risk_reduction": risk_reduction,
            "additional_cost": additional_cost,
            "breakdown": alt_calc,
        })

    # Sort by estimated delivery time (fastest first)
    alternatives.sort(key=lambda x: x["estimated_delivery_hours"])

    # Determine recommendation
    recommendation = None
    if alternatives:
        best = alternatives[0]
        if best["time_saved_hours"] > 0 or best["risk_reduction"] > 0:
            recommendation = {
                "recommended_route_id": best["route_id"],
                "reason": (
                    f"Route {best['route_id']} saves {best['time_saved_hours']}h "
                    f"and reduces risk by {round(best['risk_reduction']*100, 1)}pp "
                    f"for ₹{best['additional_cost']} additional cost."
                ),
                "time_saved_hours": best["time_saved_hours"],
                "risk_reduction": best["risk_reduction"],
                "additional_cost": best["additional_cost"],
                "requires_approval": True,
            }

    return {
        "shipment_id": shipment_id,
        "current_route": current_route,
        "alternatives": alternatives,
        "recommendation": recommendation,
        "simulation_note": (
            "All calculations use documented simulation rules (transit time from route data, "
            "cost at ₹8/km). These are NOT verified carrier quotations."
        ),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
