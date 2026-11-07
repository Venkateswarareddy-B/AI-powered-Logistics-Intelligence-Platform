"""Deterministic ID formatters for every entity type.

All ID functions produce the same output for the same inputs — they are
pure functions that do not depend on random state.

Patterns (from the master spec):
  Shipment    : SHP-YYYY-NNNNNN
  Leg         : LEG-SHP-YYYY-NNNNNN-NN
  Event       : EVT-SHP-YYYY-NNNNNN-NNNNNN
  ETA         : ETA-SHP-YYYY-NNNNNN-YYYYMMDDHHmm
  Delay reason: DLY-YYYY-NNNNNN
  Facility    : FAC-NNN
  Carrier     : CRR-NNN
  Route       : RT-NNN
  Weather     : WX-YYYYMMDD-NNN
  Alert       : ALT-YYYYMMDD-NNN
  Queue       : FQ-FACNNN-YYYYMMDDHHmm
  DQ issue    : DQI-YYYY-NNNNNN
"""

from __future__ import annotations

from datetime import datetime


def shipment_id(year: int, seq: int) -> str:
    return f"SHP-{year}-{seq:06d}"


def leg_id(shp_id: str, seq: int) -> str:
    return f"LEG-{shp_id}-{seq:02d}"


def event_id(shp_id: str, seq: int) -> str:
    return f"EVT-{shp_id}-{seq:06d}"


def eta_id(shp_id: str, prediction_time: datetime) -> str:
    ts = prediction_time.strftime("%Y%m%d%H%M")
    return f"ETA-{shp_id}-{ts}"


def delay_id(year: int, seq: int) -> str:
    return f"DLY-{year}-{seq:06d}"


def facility_id(seq: int) -> str:
    return f"FAC-{seq:03d}"


def carrier_id(seq: int) -> str:
    return f"CRR-{seq:03d}"


def route_id(seq: int) -> str:
    return f"RT-{seq:03d}"


def weather_id(date: datetime, seq: int) -> str:
    return f"WX-{date.strftime('%Y%m%d')}-{seq:03d}"


def alert_id(date: datetime, seq: int) -> str:
    return f"ALT-{date.strftime('%Y%m%d')}-{seq:03d}"


def queue_id(fac_id: str, ts: datetime) -> str:
    return f"FQ-{fac_id}-{ts.strftime('%Y%m%d%H%M')}"


def dq_issue_id(year: int, seq: int) -> str:
    return f"DQI-{year}-{seq:06d}"


def perf_id(prefix: str, entity_id: str, period_start: str) -> str:
    safe = entity_id.replace("-", "")
    return f"{prefix}-{safe}-{period_start}"
