"""Rule-based ETA Engine (Phase 8).

Formula:
  predicted_eta = planned_ship_time
                + base_transit_hours * carrier_delay_factor
                * max_weather_delay_factor
                + facility_queue_delay_hours

Feature cutoff (leakage prevention):
  Only events/queues/weather with ingestion_time <= prediction_time are used.

Every prediction is stored as a new ETAEstimate row (append-only).
Previous estimates are NEVER overwritten.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from data_engineering.generator.ids import eta_id

log = logging.getLogger("backend.services.eta_engine")

MODEL_VERSION = "rule_based_v1"

# Queue utilization thresholds → extra delay hours
_QUEUE_DELAY_MAP = [
    (90, 3.0),  # >=90% → +3h
    (75, 1.5),  # >=75% → +1.5h
    (60, 0.5),  # >=60% → +0.5h
]


def _get_shipment(db: Session, shipment_id: str) -> dict | None:
    row = db.execute(text("""
        SELECT s.shipment_id, s.carrier_id, s.planned_ship_time,
               s.promised_delivery_time, s.actual_delivery_time,
               s.status, s.origin_facility_id, s.destination_facility_id,
               r.base_transit_hours, c.base_delay_factor,
               sl.maximum_delivery_hours, sl.allowed_delay_hours
        FROM shipments s
        JOIN routes r ON s.route_id = r.route_id
        JOIN carriers c ON s.carrier_id = c.carrier_id
        JOIN service_levels sl ON s.service_level_id = sl.service_level_id
        WHERE s.shipment_id = :sid
    """), {"sid": shipment_id}).mappings().fetchone()
    return dict(row) if row else None


def _weather_factor(
    db: Session, origin_id: str, dest_id: str,
    ship_time: datetime, promised: datetime, cutoff: datetime,
) -> float:
    """Max weather delay factor on route, respecting feature cutoff."""
    row = db.execute(text("""
        SELECT COALESCE(MAX(we.delay_factor), 1.0) AS max_factor
        FROM weather_events we
        WHERE we.start_time <= :promised
          AND we.end_time   >= :ship_time
          AND we.created_at <= :cutoff
    """), {"promised": promised, "ship_time": ship_time, "cutoff": cutoff}).scalar()
    return float(row or 1.0)


def _queue_delay(
    db: Session, facility_id: str, cutoff: datetime
) -> float:
    """Extra hours from facility queue utilization, respecting cutoff."""
    row = db.execute(text("""
        SELECT utilization_pct
        FROM facility_queues
        WHERE facility_id = :fid
          AND timestamp <= :cutoff
        ORDER BY timestamp DESC
        LIMIT 1
    """), {"fid": facility_id, "cutoff": cutoff}).scalar()
    if row is None:
        return 0.0
    util = float(row)
    for threshold, delay in _QUEUE_DELAY_MAP:
        if util >= threshold:
            return delay
    return 0.0


def predict_eta(
    db: Session,
    shipment_id: str,
    prediction_time: datetime | None = None,
) -> dict | None:
    """Compute rule-based ETA for a shipment and persist the estimate.

    Returns the estimate dict, or None if the shipment isn't found.
    """
    if prediction_time is None:
        prediction_time = datetime.now(timezone.utc)

    # feature_cutoff_time = prediction_time (strict: no future data)
    feature_cutoff = prediction_time

    shp = _get_shipment(db, shipment_id)
    if not shp:
        return None

    base_h = float(shp["base_transit_hours"])
    carrier_factor = float(shp["base_delay_factor"])
    ship_time: datetime = shp["planned_ship_time"]
    promised: datetime = shp["promised_delivery_time"]

    weather_factor = _weather_factor(
        db, shp["origin_facility_id"], shp["destination_facility_id"],
        ship_time, promised, feature_cutoff,
    )
    origin_queue_h = _queue_delay(db, shp["origin_facility_id"], feature_cutoff)
    dest_queue_h   = _queue_delay(db, shp["destination_facility_id"], feature_cutoff)
    facility_queue_delay_h = origin_queue_h + dest_queue_h

    carrier_delay_h = base_h * (carrier_factor - 1.0)
    weather_delay_h = base_h * (weather_factor - 1.0)
    effective_transit_h = (
        base_h + carrier_delay_h + weather_delay_h + facility_queue_delay_h
    )

    predicted_eta = ship_time + timedelta(hours=effective_transit_h)

    # Delay probability: rough heuristic from risk factors
    delay_prob = min(1.0, max(0.0,
        0.3 * (carrier_factor - 1.0) / 0.25 +
        0.3 * (weather_factor - 1.0) / 0.6 +
        0.4 * facility_queue_delay_h / 4.0
    ))

    remaining_h = max(0.0, (predicted_eta - prediction_time).total_seconds() / 3600)

    eid = eta_id(shipment_id, prediction_time)

    # Persist (ON CONFLICT DO NOTHING — IDs are time-based, so collisions are rare)
    db.execute(text("""
        INSERT INTO eta_estimates (
            eta_estimate_id, shipment_id,
            prediction_time, feature_cutoff_time,
            predicted_eta, predicted_remaining_hours,
            delay_probability, model_version, model_type,
            base_travel_hours, carrier_delay_hours,
            weather_delay_hours, facility_queue_delay_hours,
            route_change_delay_hours, is_demo, created_at
        ) VALUES (
            :eid, :sid,
            :pt, :fct,
            :peta, :prh,
            :dp, :mv, 'RULE_BASED',
            :bh, :cdh, :wdh, :fqdh,
            0, TRUE, :now
        ) ON CONFLICT (eta_estimate_id) DO NOTHING
    """), {
        "eid": eid, "sid": shipment_id,
        "pt": prediction_time, "fct": feature_cutoff,
        "peta": predicted_eta, "prh": round(remaining_h, 4),
        "dp": round(delay_prob, 4), "mv": MODEL_VERSION,
        "bh": round(base_h, 4), "cdh": round(carrier_delay_h, 4),
        "wdh": round(weather_delay_h, 4), "fqdh": round(facility_queue_delay_h, 4),
        "now": prediction_time,
    })
    db.commit()

    return {
        "eta_estimate_id": eid,
        "shipment_id": shipment_id,
        "prediction_time": prediction_time.isoformat(),
        "feature_cutoff_time": feature_cutoff.isoformat(),
        "predicted_eta": predicted_eta.isoformat(),
        "predicted_remaining_hours": round(remaining_h, 2),
        "delay_probability": round(delay_prob, 4),
        "model_version": MODEL_VERSION,
        "model_type": "RULE_BASED",
        "base_travel_hours": round(base_h, 2),
        "carrier_delay_hours": round(carrier_delay_h, 2),
        "weather_delay_hours": round(weather_delay_h, 2),
        "facility_queue_delay_hours": round(facility_queue_delay_h, 2),
    }


def predict_eta_batch(
    db: Session,
    shipment_ids: list[str],
    prediction_time: datetime | None = None,
) -> list[dict]:
    """Run ETA prediction for multiple shipments."""
    pt = prediction_time or datetime.now(timezone.utc)
    results = []
    for sid in shipment_ids:
        est = predict_eta(db, sid, pt)
        if est:
            results.append(est)
    return results


def snapshot_all_active(db: Session) -> int:
    """Create ETA snapshots for all non-delivered shipments. Returns count."""
    rows = db.execute(text("""
        SELECT shipment_id FROM shipments
        WHERE status NOT IN ('DELIVERED','CANCELLED')
    """)).fetchall()
    sids = [r[0] for r in rows]
    estimates = predict_eta_batch(db, sids)
    log.info("eta_snapshot: computed %d estimates for %d active shipments",
             len(estimates), len(sids))
    return len(estimates)
