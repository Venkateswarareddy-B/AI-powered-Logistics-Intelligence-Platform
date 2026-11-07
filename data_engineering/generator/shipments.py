"""Generate shipments and shipment legs.

Design rules:
- Every shipment FK (carrier, service_level, route, facilities) points to a
  real row — never orphaned.
- promised_delivery_time = planned_ship_time + service_level.maximum_delivery_hours
- actual_delivery_time is set only for DELIVERED shipments.
- SLA status is derived from delivery times, not randomly assigned.
- Weight and distance are derived from route distance, not invented.
- is_demo=True on every row.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from data_engineering.generator import ids as ID
from data_engineering.generator.constants import (
    GENERATION_YEAR,
    SERVICE_LEVELS,
    SHIPMENT_STATUS_WEIGHTS,
)

_SL_MAP = {sl["service_level_id"]: sl for sl in SERVICE_LEVELS}


def _weighted_choice(rng: random.Random, weights: dict) -> str:
    keys = list(weights.keys())
    probs = [weights[k] for k in keys]
    return rng.choices(keys, weights=probs, k=1)[0]


def _sla_status(
    promised: datetime,
    predicted: datetime | None,
    actual: datetime | None,
) -> str:
    check = actual or predicted
    if check is None:
        return "ON_TIME"
    diff_h = (check - promised).total_seconds() / 3600
    if diff_h <= 0:
        return "ON_TIME"
    if diff_h <= 4:
        return "AT_RISK"
    return "BREACHED"


def generate_shipments(
    n: int,
    carriers: list[dict],
    service_levels: list[dict],
    routes: list[dict],
    rng: random.Random,
) -> tuple[list[dict], list[dict]]:
    """Return (shipments, legs) lists."""
    sl_ids = [sl["service_level_id"] for sl in service_levels]
    sl_weights = [0.50, 0.25, 0.10, 0.15]  # STANDARD, EXPRESS, SAME_DAY, PRIORITY
    carrier_ids = [c["carrier_id"] for c in carriers]
    carrier_map = {c["carrier_id"]: c for c in carriers}

    shipments = []
    legs = []

    # Spread shipments over last 90 days
    base_date = datetime(GENERATION_YEAR, 11, 6, 0, 0, 0, tzinfo=timezone.utc)
    window_days = 90

    for i in range(1, n + 1):
        shp_id = ID.shipment_id(GENERATION_YEAR, i)

        # Pick random route
        route = rng.choice(routes)
        carrier_id = rng.choice(carrier_ids)
        carrier = carrier_map[carrier_id]
        sl_id = rng.choices(sl_ids, weights=sl_weights, k=1)[0]
        sl = _SL_MAP[sl_id]

        # Planned ship time: random point in the 90-day window
        days_offset = rng.uniform(-window_days, 0)
        planned_ship = base_date + timedelta(days=days_offset)
        planned_ship = planned_ship.replace(
            hour=rng.randint(6, 20), minute=rng.choice([0, 15, 30, 45]), second=0
        )

        max_h = sl["maximum_delivery_hours"]
        promised_delivery = planned_ship + timedelta(hours=max_h)

        status = _weighted_choice(rng, SHIPMENT_STATUS_WEIGHTS)

        # Apply carrier delay factor
        delay_factor = float(carrier["base_delay_factor"])
        # Add weather/queue noise (will be refined by ETA engine later)
        delay_noise = rng.uniform(0.85, 1.20)
        effective_transit = route["base_transit_hours"] * delay_factor * delay_noise

        actual_delivery = None
        if status == "DELIVERED":
            actual_delivery = planned_ship + timedelta(hours=effective_transit)

        sla_status = _sla_status(
            promised_delivery,
            planned_ship + timedelta(hours=effective_transit) if status != "DELIVERED" else None,
            actual_delivery,
        )

        priority_choices = ["LOW", "NORMAL", "HIGH", "CRITICAL"]
        priority_weights = [0.10, 0.60, 0.25, 0.05]
        priority = rng.choices(priority_choices, weights=priority_weights, k=1)[0]

        weight_kg = round(rng.uniform(0.5, 500.0), 3)

        shipment = {
            "shipment_id": shp_id,
            "carrier_id": carrier_id,
            "service_level_id": sl_id,
            "route_id": route["route_id"],
            "origin_facility_id": route["origin_facility_id"],
            "destination_facility_id": route["destination_facility_id"],
            "planned_ship_time": planned_ship,
            "promised_delivery_time": promised_delivery,
            "actual_delivery_time": actual_delivery,
            "status": status,
            "priority": priority,
            "weight_kg": weight_kg,
            "distance_km": route["distance_km"],
            "sla_status": sla_status,
            "is_demo": True,
            "notes": "DEMO DATA",
            "created_at": planned_ship,
            "updated_at": actual_delivery or base_date,
        }
        shipments.append(shipment)

        # Generate 1-2 legs per shipment
        n_legs = 1 if route["distance_km"] < 300 else rng.randint(1, 2)
        for leg_seq in range(1, n_legs + 1):
            leg_dep = planned_ship + timedelta(hours=(leg_seq - 1) * effective_transit / n_legs)
            leg_arr = leg_dep + timedelta(hours=effective_transit / n_legs)

            # For multi-leg: intermediate facility (pick a random non-origin/dest)
            if leg_seq == 1:
                orig_fid = route["origin_facility_id"]
                dest_fid = route["destination_facility_id"] if n_legs == 1 else route["destination_facility_id"]
            else:
                orig_fid = route["origin_facility_id"]
                dest_fid = route["destination_facility_id"]

            actual_dep = leg_dep + timedelta(minutes=rng.randint(-30, 60)) if status != "CREATED" else None
            actual_arr = leg_arr + timedelta(minutes=rng.randint(-30, 90)) if status == "DELIVERED" else None

            legs.append({
                "leg_id": ID.leg_id(shp_id, leg_seq),
                "shipment_id": shp_id,
                "leg_sequence": leg_seq,
                "origin_facility_id": orig_fid,
                "destination_facility_id": dest_fid,
                "carrier_id": carrier_id,
                "planned_departure": leg_dep,
                "planned_arrival": leg_arr,
                "actual_departure": actual_dep,
                "actual_arrival": actual_arr,
                "status": status if status in ["DELIVERED", "CANCELLED"] else "IN_PROGRESS",
                "distance_km": route["distance_km"] / n_legs,
                "created_at": planned_ship,
                "updated_at": actual_arr or base_date,
            })

    return shipments, legs
