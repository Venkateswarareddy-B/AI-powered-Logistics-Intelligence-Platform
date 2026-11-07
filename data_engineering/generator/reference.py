"""Generate reference / lookup data.

Creates:
  - roles          (5 fixed rows)
  - service_levels (4 fixed rows)
  - carriers       (n_carriers synthetic rows)
  - facilities     (n_facilities synthetic rows from INDIAN_CITIES)
  - routes         (generated between facility pairs)

All rows are marked is_demo=True where the column exists.
Reference data uses deterministic IDs so they are stable across reruns.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import numpy as np
from faker import Faker

from data_engineering.generator import ids as ID
from data_engineering.generator.constants import (
    CARRIER_BASE_DELAY_FACTORS,
    FACILITY_CAPACITY_RANGE,
    FACILITY_TYPES,
    INDIAN_CITIES,
    ROLES,
    SERVICE_LEVELS,
)

NOW = datetime.now(timezone.utc)


def _now() -> datetime:
    return NOW


def generate_roles() -> list[dict]:
    rows = []
    for r in ROLES:
        rows.append({**r, "is_active": True, "created_at": _now(), "updated_at": _now()})
    return rows


def generate_service_levels() -> list[dict]:
    rows = []
    for sl in SERVICE_LEVELS:
        rows.append({**sl, "created_at": _now(), "updated_at": _now()})
    return rows


def generate_carriers(n: int, rng: random.Random) -> list[dict]:
    fake = Faker("en_IN")
    fake.seed_instance(rng.randint(0, 2**31))
    rows = []
    used_codes: set[str] = set()
    for i in range(1, n + 1):
        cid = ID.carrier_id(i)
        company = fake.company().replace(",", "").replace(".", "")[:60]
        # Ensure unique 6-char code
        base = company[:3].upper().replace(" ", "X")
        code = f"{base}{i:03d}"
        while code in used_codes:
            code = f"{base}{i:03d}X"
        used_codes.add(code)
        rows.append({
            "carrier_id": cid,
            "carrier_name": f"{company} Logistics",
            "carrier_code": code,
            "contact_email": fake.email(),
            "contact_phone": fake.phone_number()[:50],
            "country": "India",
            "is_active": True,
            "base_delay_factor": float(rng.choice(CARRIER_BASE_DELAY_FACTORS)),
            "notes": "DEMO DATA — synthetic carrier",
            "created_at": _now(),
            "updated_at": _now(),
        })
    return rows


def generate_facilities(n: int, rng: random.Random) -> list[dict]:
    """Generate n facilities from INDIAN_CITIES. Cycles if n > len(cities)."""
    rows = []
    cities = INDIAN_CITIES[:] 
    rng.shuffle(cities)
    for i in range(1, n + 1):
        city, state, lat, lon = cities[(i - 1) % len(cities)]
        ftype = rng.choice(FACILITY_TYPES)
        cap_min, cap_max = FACILITY_CAPACITY_RANGE[ftype]
        capacity = rng.randint(cap_min, cap_max)
        rows.append({
            "facility_id": ID.facility_id(i),
            "facility_name": f"{city} {ftype.replace('_',' ').title()}",
            "facility_type": ftype,
            "city": city,
            "state": state,
            "country": "India",
            "latitude": float(lat + rng.uniform(-0.05, 0.05)),
            "longitude": float(lon + rng.uniform(-0.05, 0.05)),
            "capacity": capacity,
            "operating_hours": rng.choice(["06:00-22:00", "00:00-24:00", "08:00-20:00"]),
            "status": "ACTIVE",
            "notes": "DEMO DATA — simulated coordinates",
            "created_at": _now(),
            "updated_at": _now(),
        })
    return rows


def generate_routes(
    facilities: list[dict], rng: random.Random
) -> list[dict]:
    """Generate a realistic mesh of routes between facilities.

    Rules:
    - Every facility appears as origin at least once.
    - No self-loops (origin ≠ destination).
    - distance_km is derived from rough lat/lon Euclidean distance × 111.
    - base_transit_hours = distance_km / 60 (avg 60 km/h road speed).
    """
    rows = []
    fac_ids = [f["facility_id"] for f in facilities]
    fac_map = {f["facility_id"]: f for f in facilities}
    seq = 1

    # Create routes: each facility connects to 2-3 random others
    seen_pairs: set[tuple] = set()
    for fac in facilities:
        n_connections = rng.randint(2, min(3, len(fac_ids) - 1))
        others = [f for f in fac_ids if f != fac["facility_id"]]
        rng.shuffle(others)
        for dest_id in others[:n_connections]:
            pair = (fac["facility_id"], dest_id)
            rev = (dest_id, fac["facility_id"])
            if pair in seen_pairs or rev in seen_pairs:
                continue
            seen_pairs.add(pair)

            orig = fac_map[fac["facility_id"]]
            dest = fac_map[dest_id]
            # Rough km from lat/lon (1° ≈ 111 km)
            dlat = abs(float(orig["latitude"]) - float(dest["latitude"]))
            dlon = abs(float(orig["longitude"]) - float(dest["longitude"]))
            dist_km = round((dlat**2 + dlon**2) ** 0.5 * 111, 1)
            dist_km = max(dist_km, 50.0)  # minimum 50 km
            transit_h = round(dist_km / 60.0, 2)

            rows.append({
                "route_id": ID.route_id(seq),
                "route_name": f"{orig['city']} → {dest['city']}",
                "origin_facility_id": fac["facility_id"],
                "destination_facility_id": dest_id,
                "distance_km": dist_km,
                "base_transit_hours": transit_h,
                "is_active": True,
                "notes": "DEMO DATA — calculated from simulated coordinates",
                "created_at": _now(),
                "updated_at": _now(),
            })
            seq += 1

    return rows


def generate_all_reference(
    n_carriers: int,
    n_facilities: int,
    rng: random.Random,
) -> dict[str, list[dict]]:
    """Return all reference data as a dict keyed by table name."""
    facilities = generate_facilities(n_facilities, rng)
    routes = generate_routes(facilities, rng)
    return {
        "roles": generate_roles(),
        "service_levels": generate_service_levels(),
        "carriers": generate_carriers(n_carriers, rng),
        "facilities": facilities,
        "routes": routes,
    }
