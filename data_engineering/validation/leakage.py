"""Future data leakage detector.

This is a critical correctness requirement. ML models must never see
information that was not available at prediction time.

Rules:
  LK-001  For every ETA estimate, no tracking event with
          ingestion_time > feature_cutoff_time should have been usable.
          We verify the constraint: feature_cutoff_time <= prediction_time.
  LK-002  Detect tracking events with event_time in the future
          (> NOW() + 1 hour) that could leak into training features.
  LK-003  The feature_cutoff_time constraint on eta_estimates must hold:
          feature_cutoff_time <= prediction_time.

These checks produce FUTURE_EVENT_LEAKAGE issue records when violations
are found. The ground truth file already contains one intentionally injected
leakage event (from Phase 4) — this validator detects it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from data_engineering.validation.base import BaseValidator, ValidationResult

log = logging.getLogger("data_engineering.validation.leakage")


class FutureEventLeakageValidator(BaseValidator):
    """LK-002: Detect tracking events with event_time in the future."""

    name = "LK-002-future-event-time"

    # Allow 1-hour clock skew before flagging
    SKEW_TOLERANCE_HOURS = 1

    def validate(self, db) -> list[ValidationResult]:
        results = []
        cutoff = datetime.now(timezone.utc) + timedelta(hours=self.SKEW_TOLERANCE_HOURS)

        rows = db.execute(text("""
            SELECT event_id, shipment_id, event_time, ingestion_time
            FROM tracking_events
            WHERE event_time > :cutoff
            ORDER BY event_time DESC
            LIMIT 100
        """), {"cutoff": cutoff}).fetchall()

        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="FUTURE_EVENT_LEAKAGE",
                entity_type="TrackingEvent", entity_id="ALL", shipment_id=None,
                description="LK-002 PASS: no tracking events with event_time in the future",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="FUTURE_EVENT_LEAKAGE",
                entity_type="TrackingEvent", entity_id=str(row[0]), shipment_id=str(row[1]),
                description=(
                    f"LK-002 FAIL: event {row[0]} event_time={row[2]} is in the future "
                    f"(ingestion_time={row[3]})"
                ),
                severity="CRITICAL",
            ))
        return results


class ETACutoffValidator(BaseValidator):
    """LK-001/003: ETA estimates must not use future data.

    Validates: feature_cutoff_time <= prediction_time for all ETA estimates.
    This is enforced at the DB level (Phase 3 check constraint) but we also
    verify it programmatically so the validation report catches any bypass.
    """

    name = "LK-001-003-eta-cutoff-integrity"

    def validate(self, db) -> list[ValidationResult]:
        results = []

        # LK-003: feature_cutoff_time <= prediction_time
        rows = db.execute(text("""
            SELECT eta_estimate_id, shipment_id, prediction_time, feature_cutoff_time
            FROM eta_estimates
            WHERE feature_cutoff_time > prediction_time
            LIMIT 100
        """)).fetchall()

        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="FUTURE_EVENT_LEAKAGE",
                entity_type="ETAEstimate", entity_id="ALL", shipment_id=None,
                description="LK-003 PASS: all feature_cutoff_time <= prediction_time",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="FUTURE_EVENT_LEAKAGE",
                entity_type="ETAEstimate", entity_id=str(row[0]), shipment_id=str(row[1]),
                description=(
                    f"LK-003 FAIL: eta {row[0]} feature_cutoff_time={row[3]} > "
                    f"prediction_time={row[2]} — potential leakage"
                ),
                severity="CRITICAL",
            ))

        # LK-001: No event with ingestion_time > feature_cutoff_time
        # linked to the same shipment as an ETA estimate
        # (This is enforced by the ETA engine in Phase 8; here we audit it.)
        rows2 = db.execute(text("""
            SELECT eta.eta_estimate_id, eta.shipment_id,
                   eta.feature_cutoff_time, te.event_id, te.ingestion_time
            FROM eta_estimates eta
            JOIN tracking_events te ON te.shipment_id = eta.shipment_id
            WHERE te.ingestion_time > eta.feature_cutoff_time
              AND te.ingestion_time <= eta.prediction_time + INTERVAL '1 minute'
            LIMIT 50
        """)).fetchall()

        # Note: these are not errors in themselves — the ETA engine MUST
        # filter them. We report them as informational findings.
        for row in rows2:
            results.append(ValidationResult(
                passed=True,  # informational only
                issue_type="FUTURE_EVENT_LEAKAGE",
                entity_type="ETAEstimate", entity_id=str(row[0]),
                shipment_id=str(row[1]),
                description=(
                    f"LK-001 INFO: eta {row[0]} has event {row[3]} "
                    f"with ingestion_time={row[4]} > cutoff={row[2]} "
                    f"— must be excluded by ETA engine"
                ),
                severity="LOW",
            ))

        return results
