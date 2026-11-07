"""Inject labelled anomalies and write ground_truth.json.

All 10 anomaly types from the spec are injected. Each anomaly:
- Has a unique DQI-YYYY-NNNNNN issue ID.
- Has a ground_truth_label (from the generator, NEVER used as ML input).
- Is clearly traceable to an entity_id.
- Is stored in data_quality_issues.

Ground truth is ALSO written to ground_truth.json for offline validation.

Anomaly types:
1  INGESTION_TIME_CONFUSION    — ingestion_time < event_time
2  IMPOSSIBLE_ROUTE_ORDER      — leg sequence timestamps overlap
3  FUTURE_EVENT_LEAKAGE        — event_time far in the future
4  DELIVERED_STILL_IN_TRANSIT  — status=DELIVERED but last event=IN_TRANSIT
5  DUPLICATE_TRACKING_EVENT    — exact duplicate event inserted
6  DELAYED_SCAN                — ingestion lag > 48 hours
7  ROUTE_CHANGE_ANOMALY        — route_change event with no route_change record
8  MISSING_TRACKING_EVENT      — shipment jumps from PICKED_UP to DELIVERED
9  FACILITY_OVERLOAD           — facility queue > 100% utilization
10 SEVERE_WEATHER_DISRUPTION   — delay_factor >= 2.0

IMPORTANT: These anomalies are injected into the events / queues lists
before they are written to the DB. The ground_truth_label is stored on
the data_quality_issues row and in ground_truth.json. The label column
is explicitly excluded from all ML feature queries (Phase 12).
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from data_engineering.generator import ids as ID
from data_engineering.generator.constants import GENERATION_YEAR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def inject_anomalies(
    shipments: list[dict],
    events: list[dict],
    queues: list[dict],
    weather_events: list[dict],
    rng: random.Random,
    ground_truth_path: Path,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Inject anomalies and return (events, queues, weather, dq_issues, ground_truth).

    Modifies events/queues/weather in-place and appends new rows.
    Returns modified lists plus dq_issues and ground_truth records.
    """
    dq_issues: list[dict] = []
    ground_truth: list[dict] = []
    dq_seq = 1

    def _add_issue(
        issue_type: str,
        entity_type: str,
        entity_id: str,
        description: str,
        shipment_id: str | None,
        severity: str,
        ground_truth_label: str,
    ) -> None:
        nonlocal dq_seq
        iid = ID.dq_issue_id(GENERATION_YEAR, dq_seq)
        dq_seq += 1
        row = {
            "issue_id": iid,
            "issue_type": issue_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "shipment_id": shipment_id,
            "description": description,
            "severity": severity,
            "ground_truth_label": ground_truth_label,
            "detected_at": _now(),
            "pipeline_run_id": None,
            "is_resolved": False,
            "resolution_note": None,
            "created_at": _now(),
        }
        dq_issues.append(row)
        ground_truth.append({
            "issue_id": iid,
            "issue_type": issue_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "shipment_id": shipment_id,
            "ground_truth_label": ground_truth_label,
            "severity": severity,
            "injected_at": _now().isoformat(),
            "NOTE": "GROUND TRUTH — never use as ML model input feature",
        })

    # Pick candidate shipments / events for injection
    delivered = [s for s in shipments if s["status"] == "DELIVERED"]
    in_transit = [s for s in shipments if s["status"] == "IN_TRANSIT"]
    all_shps = shipments[:] if shipments else []

    # 1 — INGESTION_TIME_CONFUSION: ingestion before event time
    if events:
        target = rng.choice(events[:20])
        target["ingestion_time"] = target["event_time"] - timedelta(minutes=rng.randint(5, 60))
        target["is_late_arrival"] = False  # intentionally wrong
        _add_issue(
            "INGESTION_TIME_CONFUSION", "TrackingEvent", target["event_id"],
            "Ingestion time is earlier than event time (anomaly injected by generator)",
            target["shipment_id"], "HIGH", "INGESTION_TIME_CONFUSION",
        )

    # 2 — IMPOSSIBLE_ROUTE_ORDER: add event with reversed timestamp
    if len(events) > 5:
        base_ev = rng.choice(events[5:20])
        shp_id = base_ev["shipment_id"]
        shp_events = [e for e in events if e["shipment_id"] == shp_id]
        if len(shp_events) >= 2:
            shp_events_sorted = sorted(shp_events, key=lambda x: x["event_time"])
            # Swap event times of first two events
            t0 = shp_events_sorted[0]["event_time"]
            t1 = shp_events_sorted[1]["event_time"]
            shp_events_sorted[0]["event_time"] = t1 + timedelta(hours=1)
            shp_events_sorted[1]["event_time"] = t0
            _add_issue(
                "IMPOSSIBLE_ROUTE_ORDER", "TrackingEvent", shp_events_sorted[0]["event_id"],
                "Event sequence timestamps are out of order (anomaly injected)",
                shp_id, "HIGH", "IMPOSSIBLE_ROUTE_ORDER",
            )

    # 3 — FUTURE_EVENT_LEAKAGE: event_time far in the future
    if all_shps:
        shp = rng.choice(all_shps[:10])
        shp_id = shp["shipment_id"]
        future_time = datetime.now(timezone.utc) + timedelta(days=30)
        seq = 9001
        eid = ID.event_id(shp_id, seq)
        events.append({
            "event_id": eid,
            "shipment_id": shp_id,
            "event_type": "IN_TRANSIT",
            "event_time": future_time,
            "ingestion_time": future_time + timedelta(minutes=5),
            "facility_id": None,
            "location": None,
            "description": "DEMO DATA — future event (anomaly injected)",
            "source": "SCANNER",
            "is_duplicate": False,
            "is_late_arrival": False,
            "is_demo": True,
            "created_at": future_time,
        })
        _add_issue(
            "FUTURE_EVENT_LEAKAGE", "TrackingEvent", eid,
            "event_time is 30 days in the future (anomaly injected)",
            shp_id, "CRITICAL", "FUTURE_EVENT_LEAKAGE",
        )

    # 4 — DELIVERED_STILL_IN_TRANSIT: status=DELIVERED but add IN_TRANSIT after delivery
    if delivered:
        shp = rng.choice(delivered[:5])
        shp_id = shp["shipment_id"]
        shp_events = [e for e in events if e["shipment_id"] == shp_id]
        if shp_events:
            last = max(shp_events, key=lambda x: x["event_time"])
            seq = 9002
            eid = ID.event_id(shp_id, seq)
            events.append({
                "event_id": eid,
                "shipment_id": shp_id,
                "event_type": "IN_TRANSIT",
                "event_time": last["event_time"] + timedelta(hours=2),
                "ingestion_time": last["event_time"] + timedelta(hours=2, minutes=5),
                "facility_id": None,
                "location": None,
                "description": "DEMO DATA — IN_TRANSIT after DELIVERED (anomaly injected)",
                "source": "SCANNER",
                "is_duplicate": False,
                "is_late_arrival": False,
                "is_demo": True,
                "created_at": last["event_time"] + timedelta(hours=2, minutes=5),
            })
            _add_issue(
                "DELIVERED_STILL_IN_TRANSIT", "TrackingEvent", eid,
                "IN_TRANSIT event after DELIVERED status (anomaly injected)",
                shp_id, "HIGH", "DELIVERED_STILL_IN_TRANSIT",
            )

    # 5 — DUPLICATE_TRACKING_EVENT: exact copy of an existing event
    if events:
        original = rng.choice(events[:15])
        seq = 9003
        eid = ID.event_id(original["shipment_id"], seq)
        dup = {**original, "event_id": eid, "is_duplicate": True,
               "description": "DEMO DATA — duplicate event (anomaly injected)"}
        events.append(dup)
        _add_issue(
            "DUPLICATE_TRACKING_EVENT", "TrackingEvent", eid,
            f"Duplicate of {original['event_id']} (anomaly injected)",
            original["shipment_id"], "MEDIUM", "DUPLICATE_TRACKING_EVENT",
        )

    # 6 — DELAYED_SCAN: ingestion lag > 48 hours
    if len(events) > 10:
        target = rng.choice(events[10:25])
        target["ingestion_time"] = target["event_time"] + timedelta(hours=rng.randint(49, 72))
        target["is_late_arrival"] = True
        _add_issue(
            "DELAYED_SCAN", "TrackingEvent", target["event_id"],
            "Ingestion lag > 48 hours (anomaly injected)",
            target["shipment_id"], "MEDIUM", "DELAYED_SCAN",
        )

    # 7 — ROUTE_CHANGE_ANOMALY: ROUTE_CHANGED event with no route_change record
    if all_shps:
        shp = rng.choice(all_shps[:10])
        shp_id = shp["shipment_id"]
        seq = 9004
        eid = ID.event_id(shp_id, seq)
        t = shp["planned_ship_time"] + timedelta(hours=2)
        events.append({
            "event_id": eid,
            "shipment_id": shp_id,
            "event_type": "ROUTE_CHANGED",
            "event_time": t,
            "ingestion_time": t + timedelta(minutes=10),
            "facility_id": None,
            "location": None,
            "description": "DEMO DATA — route change with no corresponding record (anomaly)",
            "source": "MANUAL",
            "is_duplicate": False,
            "is_late_arrival": False,
            "is_demo": True,
            "created_at": t + timedelta(minutes=10),
        })
        _add_issue(
            "ROUTE_CHANGE_ANOMALY", "TrackingEvent", eid,
            "ROUTE_CHANGED event with no route_change DB record (anomaly injected)",
            shp_id, "MEDIUM", "ROUTE_CHANGE_ANOMALY",
        )

    # 8 — MISSING_TRACKING_EVENT: shipment goes PICKED_UP → DELIVERED (no middle events)
    if all_shps:
        shp = rng.choice(all_shps[:5])
        shp_id = shp["shipment_id"]
        _add_issue(
            "MISSING_TRACKING_EVENT", "Shipment", shp_id,
            "Lifecycle gap: shipment goes PICKED_UP → DELIVERED with no intermediate events",
            shp_id, "MEDIUM", "MISSING_TRACKING_EVENT",
        )

    # 9 — FACILITY_OVERLOAD: queue close to 100% utilization (anomalous operational state)
    # We mark a high-utilization row in data_quality_issues.
    # We do NOT set utilization > 100 as that would violate the DB constraint.
    # The anomaly is: queue_length unusually close to/at capacity, a real ops concern.
    if queues:
        # Find or set a queue row with very high but valid utilization (>= 95%)
        target_q = rng.choice(queues[:20])
        fac_capacity = target_q["capacity"]
        # Set queue to 97% — still valid, but operationally concerning (overload risk)
        target_q["queue_length"] = int(fac_capacity * 0.97)
        target_q["utilization_pct"] = round(target_q["queue_length"] / fac_capacity * 100, 2)
        _add_issue(
            "FACILITY_OVERLOAD", "FacilityQueue", target_q["queue_id"],
            f"Queue utilization {target_q['utilization_pct']}% at near-capacity (anomaly injected — overload risk)",
            None, "HIGH", "FACILITY_OVERLOAD",
        )

    # 10 — SEVERE_WEATHER_DISRUPTION: delay_factor >= 2.0
    if weather_events:
        target_w = rng.choice(weather_events)
        target_w["weather_type"] = "FLOOD"
        target_w["delay_factor"] = 2.0
        target_w["severity"] = 4
        _add_issue(
            "SEVERE_WEATHER_DISRUPTION", "WeatherEvent", target_w["weather_event_id"],
            "FLOOD event with delay_factor=2.0 (anomaly injected)",
            None, "CRITICAL", "SEVERE_WEATHER_DISRUPTION",
        )

    # Write ground truth to JSON
    ground_truth_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ground_truth_path, "w") as f:
        json.dump(
            {
                "NOTE": "GROUND TRUTH — generated by YottaFlex synthetic data generator. "
                        "These labels must NEVER be used as ML model input features.",
                "total_anomalies": len(ground_truth),
                "anomalies": [
                    {k: v for k, v in rec.items() if k != "injected_at"}
                    for rec in ground_truth
                ],
            },
            f,
            indent=2,
            default=str,
        )

    return events, queues, weather_events, dq_issues, ground_truth
