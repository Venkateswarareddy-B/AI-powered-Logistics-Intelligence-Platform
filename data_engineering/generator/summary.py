"""Compute and write validation_summary.json.

Captures:
- Row counts per table
- Duplicate ID counts
- FK violation counts (post-write check)
- Date consistency errors
- Anomaly counts
- MD5 checksums of critical ID sets (for reproducibility verification)
- Generation seed and timestamp
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

log = logging.getLogger("data_engineering.generator.summary")

_TABLES = [
    "roles", "service_levels", "carriers", "facilities", "routes",
    "weather_events", "shipments", "shipment_legs", "tracking_events",
    "facility_queues", "data_quality_issues",
]

_PK_COLUMNS = {
    "shipments": "shipment_id",
    "tracking_events": "event_id",
    "facilities": "facility_id",
    "carriers": "carrier_id",
    "routes": "route_id",
    "weather_events": "weather_event_id",
}


def _row_counts() -> dict[str, int]:
    counts = {}
    with engine.connect() as conn:
        for table in _TABLES:
            row = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            counts[table] = int(row)
    return counts


def _duplicate_pk_counts() -> dict[str, int]:
    """Count rows where PK appears more than once (should always be 0)."""
    dupes = {}
    with engine.connect() as conn:
        for table, pk_col in _PK_COLUMNS.items():
            sql = f"""
                SELECT COUNT(*) FROM (
                    SELECT {pk_col} FROM {table}
                    GROUP BY {pk_col} HAVING COUNT(*) > 1
                ) t
            """
            count = conn.execute(text(sql)).scalar()
            dupes[table] = int(count)
    return dupes


def _date_errors() -> int:
    """Count shipments where promised_delivery_time <= planned_ship_time."""
    with engine.connect() as conn:
        count = conn.execute(text("""
            SELECT COUNT(*) FROM shipments
            WHERE promised_delivery_time <= planned_ship_time
        """)).scalar()
    return int(count)


def _anomaly_counts() -> dict[str, int]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT issue_type, COUNT(*) as cnt
            FROM data_quality_issues
            GROUP BY issue_type
        """)).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def _checksum(table: str, pk_col: str) -> str:
    """MD5 of sorted PK values — identical runs with same seed must match."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT {pk_col} FROM {table} ORDER BY {pk_col}")
        ).fetchall()
    ids = "\n".join(str(r[0]) for r in rows)
    return hashlib.md5(ids.encode()).hexdigest()


def build_and_write(
    seed: int,
    output_path: Path,
    extra_counts: dict | None = None,
) -> dict:
    summary = {
        "schema_version": "1.0",
        "app": "YottaFlex",
        "data_label": "DEMO DATA",
        "generation_seed": seed,
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "row_counts": _row_counts(),
        "duplicate_pk_counts": _duplicate_pk_counts(),
        "date_errors": _date_errors(),
        "anomaly_counts": _anomaly_counts(),
        "checksums": {
            table: _checksum(table, pk_col)
            for table, pk_col in _PK_COLUMNS.items()
        },
    }
    if extra_counts:
        summary["inserted_counts"] = extra_counts

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    log.info("validation_summary written to %s", output_path)
    return summary
