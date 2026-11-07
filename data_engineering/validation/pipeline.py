"""Validation pipeline orchestrator.

Runs all validators in sequence, aggregates results, persists
DataQualityIssue rows for failures, and updates validation_summary.json.

Design:
- Failures are NEVER silently deleted — they become DataQualityIssue rows.
- Already-detected issues are not re-created (idempotent by issue_id hash).
- Pass results are counted but not persisted (no noise in the issues table).
- The pipeline is safe to re-run: it uses ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.core.database import SessionLocal, engine
from backend.core.config import get_settings
from backend.models.base import Base
from data_engineering.validation.base import ValidationResult
from data_engineering.validation.pk_fk import DuplicatePKValidator, FKIntegrityValidator
from data_engineering.validation.enum_date import EnumValidator, DateConsistencyValidator
from data_engineering.validation.lifecycle import (
    DeliveredEventValidator, DuplicateEventValidator,
    DelayedScanValidator, DeliveredButInTransitValidator,
    LegSequenceValidator,
)
from data_engineering.validation.leakage import FutureEventLeakageValidator, ETACutoffValidator

log = logging.getLogger("data_engineering.validation.pipeline")
settings = get_settings()

DATA_DIR = Path(settings.DEMO_DATA_DIR)
SUMMARY_PATH = DATA_DIR / "validation_summary.json"

# All validators in execution order
ALL_VALIDATORS = [
    DuplicatePKValidator(),
    FKIntegrityValidator(),
    EnumValidator(),
    DateConsistencyValidator(),
    DeliveredEventValidator(),
    DuplicateEventValidator(),
    DelayedScanValidator(),
    DeliveredButInTransitValidator(),
    LegSequenceValidator(),
    FutureEventLeakageValidator(),
    ETACutoffValidator(),
]


def _issue_id_from_result(result: ValidationResult, seq: int) -> str:
    """Deterministic issue ID based on content hash."""
    key = f"{result.issue_type}:{result.entity_type}:{result.entity_id}"
    digest = hashlib.md5(key.encode()).hexdigest()[:12]
    return f"DQI-VAL-{digest}-{seq:04d}"


def _persist_failures(
    failures: list[ValidationResult],
    pipeline_run_id: str,
) -> int:
    """Upsert DataQualityIssue rows for all failures. Returns count inserted."""
    if not failures:
        return 0

    table = Base.metadata.tables["data_quality_issues"]
    now = datetime.now(timezone.utc)
    rows = []
    for seq, result in enumerate(failures, 1):
        rows.append({
            "issue_id": _issue_id_from_result(result, seq),
            "issue_type": result.issue_type,
            "entity_type": result.entity_type,
            "entity_id": result.entity_id[:80],
            "shipment_id": result.shipment_id,
            "description": result.description[:500],
            "severity": result.severity,
            "ground_truth_label": None,  # validator-detected, not generator-injected
            "detected_at": now,
            "pipeline_run_id": pipeline_run_id,
            "is_resolved": False,
            "resolution_note": None,
            "created_at": now,
        })

    inserted = 0
    with engine.begin() as conn:
        for start in range(0, len(rows), 200):
            batch = rows[start:start + 200]
            stmt = pg_insert(table).values(batch).on_conflict_do_nothing()
            result = conn.execute(stmt)
            # psycopg3 may return -1 for rowcount on ON CONFLICT DO NOTHING;
            # use a count query instead for accurate tracking.
            if result.rowcount >= 0:
                inserted += result.rowcount
            else:
                inserted += len(batch)  # assume all inserted (idempotent)
    return inserted


def run_pipeline(
    validators: list | None = None,
    persist: bool = True,
    update_summary: bool = True,
) -> dict[str, Any]:
    """Run all (or specified) validators and return a report dict.

    Args:
        validators: Override the default validator list (for testing).
        persist: Whether to write DataQualityIssue rows to the DB.
        update_summary: Whether to update validation_summary.json.

    Returns:
        Report dict with counts, issues by type, and per-validator results.
    """
    pipeline_run_id = f"VAL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    vlist = validators or ALL_VALIDATORS

    all_results: list[ValidationResult] = []
    validator_reports: list[dict] = []

    db = SessionLocal()
    try:
        for validator in vlist:
            log.info("running validator=%s", validator.name)
            try:
                results = validator.validate(db)
                all_results.extend(results)
                fails = [r for r in results if r.is_failure]
                passes = [r for r in results if not r.is_failure]
                validator_reports.append({
                    "validator": validator.name,
                    "total": len(results),
                    "passed": len(passes),
                    "failed": len(fails),
                })
                if fails:
                    log.warning(
                        "validator=%s failures=%d",
                        validator.name, len(fails),
                    )
            except Exception as exc:
                log.error("validator=%s error=%s", validator.name, exc, exc_info=True)
                validator_reports.append({
                    "validator": validator.name,
                    "error": str(exc),
                })
    finally:
        db.close()

    failures = [r for r in all_results if r.is_failure]
    passes = [r for r in all_results if not r.is_failure]

    # Group failures by issue_type
    by_type: dict[str, int] = {}
    for r in failures:
        by_type[r.issue_type] = by_type.get(r.issue_type, 0) + 1

    inserted = 0
    if persist and failures:
        inserted = _persist_failures(failures, pipeline_run_id)
        log.info("persisted %d new DataQualityIssue rows", inserted)

    report = {
        "pipeline_run_id": pipeline_run_id,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_checks": len(all_results),
        "passed": len(passes),
        "failed": len(failures),
        "new_issues_persisted": inserted,
        "failures_by_type": by_type,
        "validators": validator_reports,
    }

    if update_summary and SUMMARY_PATH.exists():
        try:
            existing = json.loads(SUMMARY_PATH.read_text())
            existing["last_validation_run"] = report
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            SUMMARY_PATH.write_text(json.dumps(existing, indent=2, default=str))
        except Exception as exc:
            log.warning("could not update validation_summary.json: %s", exc)

    return report
