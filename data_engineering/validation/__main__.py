"""CLI entry point for the YottaFlex data validation pipeline.

Usage (from project root):
    python -m data_engineering.validation [options]

Examples:
    # Run all validators against the live DB
    python -m data_engineering.validation

    # Dry run (no DB writes, no summary update)
    python -m data_engineering.validation --dry-run

    # Run only specific validator groups
    python -m data_engineering.validation --validators pk_fk enum_date lifecycle

Exit codes:
    0 — validation passed (or dry run)
    1 — validation found failures
    2 — pipeline error
"""

from __future__ import annotations

import argparse
import sys

from backend.core.logging import configure_logging, get_logger
from data_engineering.validation.pk_fk import DuplicatePKValidator, FKIntegrityValidator
from data_engineering.validation.enum_date import EnumValidator, DateConsistencyValidator
from data_engineering.validation.lifecycle import (
    DeliveredEventValidator, DuplicateEventValidator,
    DelayedScanValidator, DeliveredButInTransitValidator,
    LegSequenceValidator,
)
from data_engineering.validation.leakage import FutureEventLeakageValidator, ETACutoffValidator
from data_engineering.validation.pipeline import ALL_VALIDATORS, run_pipeline

configure_logging(level="INFO", debug=False)
log = get_logger("data_engineering.validation")

_VALIDATOR_GROUPS = {
    "pk_fk":     [DuplicatePKValidator(), FKIntegrityValidator()],
    "enum_date": [EnumValidator(), DateConsistencyValidator()],
    "lifecycle": [
        DeliveredEventValidator(), DuplicateEventValidator(),
        DelayedScanValidator(), DeliveredButInTransitValidator(),
        LegSequenceValidator(),
    ],
    "leakage":   [FutureEventLeakageValidator(), ETACutoffValidator()],
    "all":       ALL_VALIDATORS,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m data_engineering.validation",
        description="YottaFlex data validation pipeline",
    )
    parser.add_argument(
        "--validators", nargs="+",
        choices=list(_VALIDATOR_GROUPS.keys()),
        default=["all"],
        help="Validator groups to run (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true",
        help="Do not persist issues or update summary")
    args = parser.parse_args(argv)

    # Collect validators (deduplicate by name)
    seen: set[str] = set()
    validators = []
    for group in args.validators:
        for v in _VALIDATOR_GROUPS[group]:
            if v.name not in seen:
                seen.add(v.name)
                validators.append(v)

    log.info("starting validation pipeline groups=%s dry_run=%s", args.validators, args.dry_run)
    try:
        report = run_pipeline(
            validators=validators,
            persist=not args.dry_run,
            update_summary=not args.dry_run,
        )
    except Exception as exc:
        log.error("pipeline error: %s", exc, exc_info=True)
        return 2

    # Print summary
    print("\n" + "=" * 60)
    print("  YottaFlex — Data Validation Report")
    print("=" * 60)
    print(f"  Run ID         : {report['pipeline_run_id']}")
    print(f"  Total checks   : {report['total_checks']}")
    print(f"  Passed         : {report['passed']}")
    print(f"  Failed         : {report['failed']}")
    if not args.dry_run:
        print(f"  New issues     : {report['new_issues_persisted']}")
    print()
    if report["failures_by_type"]:
        print("  Failures by type:")
        for itype, cnt in sorted(report["failures_by_type"].items()):
            print(f"    {itype:<40} {cnt}")
    else:
        print("  No failures found.")
    print()
    for v in report["validators"]:
        if "error" in v:
            print(f"  [ERROR] {v['validator']}: {v['error']}")
        else:
            status = "PASS" if v["failed"] == 0 else "FAIL"
            print(f"  [{status}] {v['validator']}: {v['passed']} pass / {v['failed']} fail")
    print("=" * 60)

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
