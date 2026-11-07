"""CLI entry point for the YottaFlex synthetic data generator.

Usage (from project root):
    python -m data_engineering.generator [options]

Examples:
    # Default small dataset (Phase 4 development)
    python -m data_engineering.generator --shipments 100 --events 500 \
        --facilities 10 --disruptions 20 --seed 20261022

    # Larger dataset
    python -m data_engineering.generator --shipments 1000 --events 5000 \
        --facilities 20 --disruptions 100 --seed 20261022

    # Reset and regenerate (drops all DEMO DATA rows first)
    python -m data_engineering.generator --shipments 100 --reset

All generated data is labelled DEMO DATA. Coordinates are simulated.
Never present synthetic output as real logistics information.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.core.config import get_settings
from backend.core.logging import configure_logging, get_logger
from data_engineering.generator.anomalies import inject_anomalies
from data_engineering.generator.events import generate_events
from data_engineering.generator.queues_weather import (
    generate_facility_queues,
    generate_weather_events,
)
from data_engineering.generator.reference import generate_all_reference
from data_engineering.generator.shipments import generate_shipments
from data_engineering.generator.summary import build_and_write
from data_engineering.generator.writer import write_all

settings = get_settings()
configure_logging(level="INFO", debug=False)
log = get_logger("data_engineering.generator")

DATA_DIR = Path(settings.DEMO_DATA_DIR)
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"
SUMMARY_PATH = DATA_DIR / "validation_summary.json"


def _reset_demo_data() -> None:
    """Delete all demo rows in reverse-FK order using TRUNCATE CASCADE."""
    from sqlalchemy import text
    from backend.core.database import engine

    with engine.begin() as conn:
        # TRUNCATE CASCADE handles FK order automatically.
        # We only truncate tables that are entirely demo-owned.
        conn.execute(text("""
            TRUNCATE TABLE
                data_quality_issues,
                tracking_events,
                shipment_legs,
                eta_estimates,
                delay_reasons,
                route_changes,
                shipments,
                facility_queues,
                weather_events,
                routes,
                facilities,
                carriers,
                service_levels,
                roles
            CASCADE
        """))
    log.info("reset complete — all demo tables truncated")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m data_engineering.generator",
        description="YottaFlex synthetic logistics data generator",
    )
    p.add_argument("--shipments",   type=int, default=100,      help="Number of shipments (default: 100)")
    p.add_argument("--events",      type=int, default=500,      help="Target tracking events (default: 500)")
    p.add_argument("--facilities",  type=int, default=10,       help="Number of facilities (default: 10)")
    p.add_argument("--disruptions", type=int, default=20,       help="Weather disruptions (default: 20)")
    p.add_argument("--carriers",    type=int, default=8,        help="Number of carriers (default: 8)")
    p.add_argument("--seed",        type=int, default=20261022, help="Random seed (default: 20261022)")
    p.add_argument("--batch-size",  type=int, default=500,      help="DB insert batch size (default: 500)")
    p.add_argument("--reset",       action="store_true",        help="Delete existing demo data before generating")
    p.add_argument("--dry-run",     action="store_true",        help="Generate data in memory only (no DB writes)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log.info(
        "YottaFlex generator starting",
        extra={"props": {
            "shipments": args.shipments, "events": args.events,
            "facilities": args.facilities, "disruptions": args.disruptions,
            "seed": args.seed, "dry_run": args.dry_run, "reset": args.reset,
        }},
    )

    if args.reset and not args.dry_run:
        log.info("resetting demo data (--reset flag)")
        _reset_demo_data()

    # ── Deterministic RNG ────────────────────────────────────────────────────
    rng = random.Random(args.seed)

    # ── Reference data ───────────────────────────────────────────────────────
    log.info("generating reference data ...")
    ref = generate_all_reference(
        n_carriers=args.carriers,
        n_facilities=args.facilities,
        rng=rng,
    )
    routes = ref["routes"]
    facilities = ref["facilities"]
    carriers = ref["carriers"]
    service_levels = ref["service_levels"]

    if not routes:
        log.error("No routes generated — check facilities count (need ≥ 2)")
        return 1

    # ── Shipments + legs ─────────────────────────────────────────────────────
    log.info("generating %d shipments ...", args.shipments)
    shipments, legs = generate_shipments(
        n=args.shipments,
        carriers=carriers,
        service_levels=service_levels,
        routes=routes,
        rng=rng,
    )

    # ── Tracking events ──────────────────────────────────────────────────────
    log.info("generating tracking events (target=%d) ...", args.events)
    events = generate_events(
        shipments=shipments,
        routes=routes,
        n_events_target=args.events,
        rng=rng,
    )

    # ── Facility queues + weather ─────────────────────────────────────────────
    log.info("generating facility queues and weather events ...")
    queues = generate_facility_queues(facilities=facilities, rng=rng)
    weather = generate_weather_events(
        facilities=facilities, n_disruptions=args.disruptions, rng=rng
    )

    # ── Anomaly injection ────────────────────────────────────────────────────
    log.info("injecting labelled anomalies ...")
    events, queues, weather, dq_issues, _ = inject_anomalies(
        shipments=shipments,
        events=events,
        queues=queues,
        weather_events=weather,
        rng=rng,
        ground_truth_path=GROUND_TRUTH_PATH,
    )

    # ── Summary of generated counts ──────────────────────────────────────────
    generated = {
        "roles": len(ref["roles"]),
        "service_levels": len(ref["service_levels"]),
        "carriers": len(carriers),
        "facilities": len(facilities),
        "routes": len(routes),
        "shipments": len(shipments),
        "shipment_legs": len(legs),
        "tracking_events": len(events),
        "facility_queues": len(queues),
        "weather_events": len(weather),
        "data_quality_issues": len(dq_issues),
    }
    for k, v in generated.items():
        log.info("  generated %s = %d", k, v)

    if args.dry_run:
        log.info("DRY RUN — skipping database writes")
        print("\nDRY RUN complete. Generated row counts:")
        for k, v in generated.items():
            print(f"  {k:<30} {v:>6}")
        return 0

    # ── Write to PostgreSQL ───────────────────────────────────────────────────
    log.info("writing to PostgreSQL ...")
    all_data = {
        **ref,
        "shipments": shipments,
        "shipment_legs": legs,
        "tracking_events": events,
        "facility_queues": queues,
        "weather_events": weather,
        "data_quality_issues": dq_issues,
    }
    inserted = write_all(all_data, batch_size=args.batch_size)

    # ── Validation summary ────────────────────────────────────────────────────
    log.info("writing validation_summary.json ...")
    summary = build_and_write(
        seed=args.seed,
        output_path=SUMMARY_PATH,
        extra_counts=inserted,
    )

    print("\n" + "=" * 60)
    print("  YottaFlex — DEMO DATA Generation Complete")
    print("=" * 60)
    print(f"  Seed            : {args.seed}")
    print(f"  Generated at    : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    for table, cnt in summary["row_counts"].items():
        print(f"  {table:<30} {cnt:>6} rows")
    print()
    print(f"  Anomalies       : {sum(summary['anomaly_counts'].values())}")
    print(f"  Date errors     : {summary['date_errors']}")
    print(f"  Ground truth    : {GROUND_TRUTH_PATH}")
    print(f"  Summary         : {SUMMARY_PATH}")
    print()
    print("  *** ALL DATA IS SYNTHETIC DEMO DATA — NOT REAL LOGISTICS INFO ***")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
