"""ETL pipeline orchestrator — Bronze → Silver → Gold.

Runs all ETL jobs in the correct order, collects results, and logs a
comprehensive pipeline report. Safe to re-run (all jobs are idempotent).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from backend.core.database import SessionLocal
from data_engineering.ingestion.bronze import (
    BronzeShipmentSnapshotJob,
    BronzeTrackingEventsJob,
)
from data_engineering.pipelines.base import ETLJob, JobResult
from data_engineering.transformation.gold import (
    GoldCarrierPerformanceJob,
    GoldFacilityPerformanceJob,
    GoldShipmentFeaturesJob,
)
from data_engineering.transformation.silver import (
    SilverShipmentsJob,
    SilverTrackingEventsJob,
)

log = logging.getLogger("data_engineering.pipelines.etl_pipeline")

BRONZE_JOBS: list[ETLJob] = [
    BronzeTrackingEventsJob(),
    BronzeShipmentSnapshotJob(),
]

SILVER_JOBS: list[ETLJob] = [
    SilverTrackingEventsJob(),
    SilverShipmentsJob(),
]

GOLD_JOBS: list[ETLJob] = [
    GoldCarrierPerformanceJob(),
    GoldFacilityPerformanceJob(),
    GoldShipmentFeaturesJob(),
]

ALL_JOBS = BRONZE_JOBS + SILVER_JOBS + GOLD_JOBS


def _run_stage(
    jobs: list[ETLJob],
    run_id: str,
    db,
) -> list[JobResult]:
    results = []
    for job in jobs:
        job_result = JobResult(
            job_name=job.name,
            stage=job.stage,
            started_at=datetime.now(timezone.utc),
            extra={"run_id": run_id},
        )
        # Pass run_id into the job via the result object
        try:
            job_result = job.run(db)
            job_result.extra["run_id"] = run_id
        except Exception as exc:
            job_result.errors.append(str(exc))
            log.error("job=%s failed: %s", job.name, exc, exc_info=True)
        results.append(job_result)
        status = "OK" if job_result.success else "FAILED"
        log.info(
            "job=%s stage=%s status=%s rows_read=%d rows_written=%d duration=%.2fs",
            job_result.job_name, job_result.stage, status,
            job_result.rows_read, job_result.rows_written,
            job_result.duration_seconds or 0,
        )
    return results


def run_etl(
    stages: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full or partial ETL pipeline.

    Args:
        stages: Subset of ['bronze', 'silver', 'gold']. None = all.

    Returns:
        Pipeline report dict.
    """
    run_id = f"ETL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    stages_to_run = set(stages or ["bronze", "silver", "gold"])
    log.info("ETL pipeline starting run_id=%s stages=%s", run_id, stages_to_run)

    all_results: list[JobResult] = []
    db = SessionLocal()
    try:
        if "bronze" in stages_to_run:
            log.info("=== BRONZE stage ===")
            all_results.extend(_run_stage(BRONZE_JOBS, run_id, db))
        if "silver" in stages_to_run:
            log.info("=== SILVER stage ===")
            all_results.extend(_run_stage(SILVER_JOBS, run_id, db))
        if "gold" in stages_to_run:
            log.info("=== GOLD stage ===")
            all_results.extend(_run_stage(GOLD_JOBS, run_id, db))
    finally:
        db.close()

    total_rows_written = sum(r.rows_written for r in all_results)
    failed_jobs = [r for r in all_results if not r.success]

    report: dict[str, Any] = {
        "run_id": run_id,
        "stages_run": sorted(stages_to_run),
        "total_jobs": len(all_results),
        "failed_jobs": len(failed_jobs),
        "total_rows_written": total_rows_written,
        "jobs": [
            {
                "name": r.job_name,
                "stage": r.stage,
                "rows_read": r.rows_read,
                "rows_written": r.rows_written,
                "rows_skipped": r.rows_skipped,
                "duration_s": round(r.duration_seconds or 0, 3),
                "success": r.success,
                "errors": r.errors,
                "extra": r.extra,
            }
            for r in all_results
        ],
    }
    log.info(
        "ETL pipeline complete run_id=%s jobs=%d failed=%d rows_written=%d",
        run_id, len(all_results), len(failed_jobs), total_rows_written,
    )
    return report
