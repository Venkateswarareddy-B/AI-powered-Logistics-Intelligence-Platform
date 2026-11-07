"""Generate facility queue snapshots and weather disruption windows.

Queue design:
- Utilization is ALWAYS calculated as queue_length / capacity * 100.
  It is never independently invented.
- Snapshots are taken every 2 hours over the last 7 days.

Weather design:
- delay_factor is ALWAYS looked up from the WEATHER_DELAY_FACTORS map.
- Disruption windows have realistic durations per type.
- Coordinates are the facility's coordinates ± small noise.
- is_demo=True on every row.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from data_engineering.generator import ids as ID
from data_engineering.generator.constants import (
    GENERATION_YEAR,
    WEATHER_DELAY_FACTORS,
)

# How long each weather type typically lasts (min_h, max_h)
_WEATHER_DURATION = {
    "NORMAL":       (1,  3),
    "RAIN":         (2,  6),
    "HEAVY_RAIN":   (3,  8),
    "STORM":        (4, 12),
    "FLOOD":        (6, 24),
    "EXTREME_HEAT": (4, 12),
    "FOG":          (2,  6),
}

# Severity by weather type
_WEATHER_SEVERITY = {
    "NORMAL": 1, "RAIN": 1, "HEAVY_RAIN": 2,
    "STORM": 3, "FLOOD": 4, "EXTREME_HEAT": 2, "FOG": 2,
}

_WEATHER_WEIGHTS = [0.05, 0.25, 0.20, 0.15, 0.05, 0.15, 0.15]
_WEATHER_TYPES = list(WEATHER_DELAY_FACTORS.keys())


def generate_facility_queues(
    facilities: list[dict],
    rng: random.Random,
    days: int = 7,
    interval_hours: int = 2,
) -> list[dict]:
    """Generate point-in-time queue snapshots for every facility."""
    base = datetime(GENERATION_YEAR, 11, 6, 0, 0, 0, tzinfo=timezone.utc)
    rows = []

    for fac in facilities:
        fac_id = fac["facility_id"]
        capacity = int(fac["capacity"])
        n_snapshots = (days * 24) // interval_hours

        # Simulate a daily utilization pattern (higher during work hours)
        for snap_i in range(n_snapshots):
            ts = base - timedelta(hours=(n_snapshots - snap_i) * interval_hours)
            hour = ts.hour
            # Utilization follows a bell curve: peak around 10:00 and 14:00
            base_util = 0.3 + 0.4 * (
                0.5 * max(0, 1 - abs(hour - 10) / 6) +
                0.5 * max(0, 1 - abs(hour - 14) / 6)
            )
            noise = rng.uniform(-0.1, 0.15)
            util_frac = max(0.05, min(1.0, base_util + noise))

            queue_length = int(capacity * util_frac)
            util_pct = round(queue_length / capacity * 100, 2)
            avg_proc = round(rng.uniform(10, 45), 2)

            qid = ID.queue_id(fac_id, ts)
            rows.append({
                "queue_id": qid,
                "facility_id": fac_id,
                "timestamp": ts,
                "queue_length": queue_length,
                "capacity": capacity,
                "average_processing_time_minutes": avg_proc,
                "utilization_pct": util_pct,
                "created_at": ts,
            })

    return rows


def generate_weather_events(
    facilities: list[dict],
    n_disruptions: int,
    rng: random.Random,
) -> list[dict]:
    """Generate n_disruptions weather disruption windows.

    Each disruption is anchored to a facility location ± noise.
    delay_factor comes from WEATHER_DELAY_FACTORS — never invented.
    """
    base = datetime(GENERATION_YEAR, 11, 6, 0, 0, 0, tzinfo=timezone.utc)
    rows = []
    date_counter: dict[str, int] = {}

    for _ in range(n_disruptions):
        fac = rng.choice(facilities)
        lat = float(fac["latitude"]) + rng.uniform(-0.5, 0.5)
        lon = float(fac["longitude"]) + rng.uniform(-0.5, 0.5)

        w_type = rng.choices(_WEATHER_TYPES, weights=_WEATHER_WEIGHTS, k=1)[0]
        dur_min, dur_max = _WEATHER_DURATION[w_type]
        duration_h = rng.uniform(dur_min, dur_max)

        days_back = rng.uniform(0, 30)
        start = base - timedelta(days=days_back)
        start = start.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=duration_h)

        date_key = start.strftime("%Y%m%d")
        date_counter[date_key] = date_counter.get(date_key, 0) + 1
        wid = ID.weather_id(start, date_counter[date_key])

        rows.append({
            "weather_event_id": wid,
            "location": fac["city"],
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "start_time": start,
            "end_time": end,
            "weather_type": w_type,
            "severity": _WEATHER_SEVERITY[w_type],
            "delay_factor": float(WEATHER_DELAY_FACTORS[w_type]),
            "description": f"DEMO DATA — {w_type.replace('_',' ').title()} near {fac['city']}",
            "is_demo": True,
            "created_at": start,
            "updated_at": start,
        })

    return rows
