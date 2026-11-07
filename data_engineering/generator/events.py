"""Generate tracking events.

Key design decisions:
1. event_time  = when the event physically occurred.
2. ingestion_time = when the system received it (usually event_time + small lag).
   Late-arriving events have ingestion_time >> event_time.
3. Events follow a deterministic lifecycle order: PICKED_UP → DEPARTED_FACILITY
   → IN_TRANSIT → ARRIVED_FACILITY → OUT_FOR_DELIVERY → DELIVERED.
4. A percentage of events are labelled duplicates (same shipment/type/time).
5. Events are immutable — never updated or deleted.
6. is_demo=True on every row.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from data_engineering.generator import ids as ID
from data_engineering.generator.constants import GENERATION_YEAR

# Lifecycle steps and the fraction of the transit time at which they occur
_LIFECYCLE_FRACTIONS = [
    ("PICKED_UP",          0.00),
    ("DEPARTED_FACILITY",  0.05),
    ("IN_TRANSIT",         0.30),
    ("ARRIVED_FACILITY",   0.70),
    ("OUT_FOR_DELIVERY",   0.85),
    ("DELIVERED",          1.00),
]

# Statuses whose lifecycle we truncate at
_STATUS_CUTOFF = {
    "CREATED":          0,
    "PICKED_UP":        1,
    "IN_TRANSIT":       3,
    "AT_FACILITY":      4,
    "OUT_FOR_DELIVERY": 5,
    "DELIVERED":        6,
    "CANCELLED":        2,
    "EXCEPTION":        3,
}


def generate_events(
    shipments: list[dict],
    routes: list[dict],
    n_events_target: int,
    rng: random.Random,
) -> list[dict]:
    """Generate tracking events for all shipments.

    We first generate lifecycle events for every shipment, then
    pad with extra IN_TRANSIT events to reach n_events_target.
    """
    route_map = {r["route_id"]: r for r in routes}
    all_events: list[dict] = []
    global_event_counter: dict[str, int] = {}  # shipment_id → next event seq

    for shp in shipments:
        shp_id = shp["shipment_id"]
        global_event_counter[shp_id] = 0
        planned_ship = shp["planned_ship_time"]
        promised = shp["promised_delivery_time"]
        transit_hours = (promised - planned_ship).total_seconds() / 3600
        status = shp["status"]
        cutoff = _STATUS_CUTOFF.get(status, 3)

        route = route_map.get(shp["route_id"])
        fac_origin = shp["origin_facility_id"]
        fac_dest = shp["destination_facility_id"]

        lifecycle = _LIFECYCLE_FRACTIONS[:cutoff]

        for evt_type, fraction in lifecycle:
            global_event_counter[shp_id] += 1
            seq = global_event_counter[shp_id]

            event_time = planned_ship + timedelta(hours=transit_hours * fraction)
            # Normal ingestion lag: 1–15 minutes
            lag_minutes = rng.randint(1, 15)
            ingestion_time = event_time + timedelta(minutes=lag_minutes)

            # Facility assignment
            if evt_type in ("PICKED_UP", "DEPARTED_FACILITY"):
                fac_id = fac_origin
            elif evt_type in ("ARRIVED_FACILITY", "OUT_FOR_DELIVERY", "DELIVERED"):
                fac_id = fac_dest
            else:
                fac_id = None

            is_late = False
            is_dup = False

            all_events.append({
                "event_id": ID.event_id(shp_id, seq),
                "shipment_id": shp_id,
                "event_type": evt_type,
                "event_time": event_time,
                "ingestion_time": ingestion_time,
                "facility_id": fac_id,
                "location": None,
                "description": f"DEMO DATA — {evt_type.replace('_', ' ').title()}",
                "source": "SCANNER",
                "is_duplicate": is_dup,
                "is_late_arrival": is_late,
                "is_demo": True,
                "created_at": ingestion_time,
            })

    # Pad to reach n_events_target with extra IN_TRANSIT events
    active_shp = [s for s in shipments if s["status"] not in ("CREATED", "CANCELLED")]
    while len(all_events) < n_events_target and active_shp:
        shp = rng.choice(active_shp)
        shp_id = shp["shipment_id"]
        planned_ship = shp["planned_ship_time"]
        promised = shp["promised_delivery_time"]
        transit_hours = (promised - planned_ship).total_seconds() / 3600
        fraction = rng.uniform(0.1, 0.9)

        global_event_counter[shp_id] = global_event_counter.get(shp_id, 0) + 1
        seq = global_event_counter[shp_id]

        event_time = planned_ship + timedelta(hours=transit_hours * fraction)
        ingestion_time = event_time + timedelta(minutes=rng.randint(1, 15))

        all_events.append({
            "event_id": ID.event_id(shp_id, seq),
            "shipment_id": shp_id,
            "event_type": "IN_TRANSIT",
            "event_time": event_time,
            "ingestion_time": ingestion_time,
            "facility_id": None,
            "location": None,
            "description": "DEMO DATA — In transit update",
            "source": "GPS",
            "is_duplicate": False,
            "is_late_arrival": False,
            "is_demo": True,
            "created_at": ingestion_time,
        })

    # Dedup event_ids (can collide on same shp+seq when padding)
    seen_ids: set[str] = set()
    unique_events = []
    for ev in all_events:
        if ev["event_id"] not in seen_ids:
            seen_ids.add(ev["event_id"])
            unique_events.append(ev)

    return unique_events
