"""CLI entry point for the YottaFlex ETL pipeline.

Usage (from project root):
    python -m data_engineering.pipelines [options]

Examples:
    # Run full pipeline (Bronze → Silver → Gold)
    python -m data_engineering.pipelines

    # Run specific stage(s) only
    python -m data_engineering.pipelines --stage bronze
    python -m data_engineering.pipelines --stage silver gold

Exit codes:
    0 — all jobs succeeded
    1 — one or more jobs failed
    2 — pipeline error
"""

from __future__ import annotations

import argparse
import sys

from backend.core.logging import configure_logging, get_logger
from data_engineering.pipelines.etl_pipeline import run_etl

configure_logging(level="INFO", debug=False)
log = get_logger("data_engineering.pipelines")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m data_engineering.pipelines",
        description="YottaFlex ETL pipeline (Bronze -> Silver -> Gold)",
    )
    parser.add_argument(
        "--stage", nargs="+",
        choices=["bronze", "silver", "gold"],
        default=None,
        help="Stages to run (default: all)",
    )
    args = parser.parse_args(argv)

    try:
        report = run_etl(stages=args.stage)
    except Exception as exc:
        log.error("pipeline error: %s", exc, exc_info=True)
        return 2

    print("\n" + "=" * 65)
    print("  YottaFlex ETL Pipeline Report")
    print("=" * 65)
    print(f"  Run ID         : {report['run_id']}")
    print(f"  Stages run     : {', '.join(report['stages_run'])}")
    print(f"  Total jobs     : {report['total_jobs']}")
    print(f"  Failed jobs    : {report['failed_jobs']}")
    print(f"  Total rows out : {report['total_rows_written']}")
    print()
    print(f"  {'Job':<40} {'Stage':<8} {'Read':>6} {'Written':>8} {'Dur(s)':>7} Status")
    print(f"  {'-'*40} {'-'*8} {'-'*6} {'-'*8} {'-'*7} ------")
    for j in report["jobs"]:
        status = "OK" if j["success"] else "FAIL"
        print(
            f"  {j['name']:<40} {j['stage']:<8} {j['rows_read']:>6} "
            f"{j['rows_written']:>8} {j['duration_s']:>7.3f} {status}"
        )
        if j["errors"]:
            for err in j["errors"]:
                print(f"    ERROR: {err[:80]}")
        if j.get("extra"):
            for k, v in j["extra"].items():
                if k != "run_id":
                    print(f"    {k}: {v}")
    print("=" * 65)

    return 0 if report["failed_jobs"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
