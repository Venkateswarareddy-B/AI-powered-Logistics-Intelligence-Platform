"""Shipment lifecycle, duplicate event, delayed scan, and missing event validators.

Rules checked:
  LC-001  DELIVERED shipment must have at least one DELIVERED tracking event.
  LC-002  DELIVERED shipment must have a non-null actual_delivery_time.
  LC-003  Duplicate tracking events: same (shipment_id, event_type, event_time).
  LC-004  Delayed scans: ingestion_time > event_time + 48 hours.
  LC-005  Late-arriving events: ingestion_time > event_time + 2 hours.
  LC-006  Shipment with status DELIVERED but last event type is IN_TRANSIT.
  LC-007  Shipment leg sequence gaps (seq should be contiguous from 1).
"""

from __future__ import annotations

import logging
from sqlalchemy import text

from data_engineering.validation.base import BaseValidator, ValidationResult

log = logging.getLogger("data_engineering.validation.lifecycle")

# Delayed scan threshold in hours
DELAYED_SCAN_THRESHOLD_HOURS = 48
LATE_ARRIVAL_THRESHOLD_HOURS = 2


class DeliveredEventValidator(BaseValidator):
    """LC-001/002: DELIVERED shipments must have evidence of delivery."""

    name = "LC-001-002-delivered-events"

    def validate(self, db) -> list[ValidationResult]:
        results = []

        # LC-001: DELIVERED shipment must have ≥1 DELIVERED event
        rows = db.execute(text("""
            SELECT s.shipment_id
            FROM shipments s
            WHERE s.status = 'DELIVERED'
              AND NOT EXISTS (
                  SELECT 1 FROM tracking_events te
                  WHERE te.shipment_id = s.shipment_id
                    AND te.event_type = 'DELIVERED'
              )
            LIMIT 100
        """)).fetchall()
        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="MISSING_TRACKING_EVENT",
                entity_type="Shipment", entity_id="ALL", shipment_id=None,
                description="LC-001 PASS: all DELIVERED shipments have a DELIVERED event",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="MISSING_TRACKING_EVENT",
                entity_type="Shipment", entity_id=str(row[0]), shipment_id=str(row[0]),
                description=f"LC-001 FAIL: shipment {row[0]} is DELIVERED but has no DELIVERED event",
                severity="HIGH",
            ))

        # LC-002: DELIVERED shipment must have actual_delivery_time
        rows = db.execute(text("""
            SELECT shipment_id
            FROM shipments
            WHERE status = 'DELIVERED'
              AND actual_delivery_time IS NULL
            LIMIT 100
        """)).fetchall()
        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DATE_INCONSISTENCY",
                entity_type="Shipment", entity_id="ALL", shipment_id=None,
                description="LC-002 PASS: all DELIVERED shipments have actual_delivery_time",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DATE_INCONSISTENCY",
                entity_type="Shipment", entity_id=str(row[0]), shipment_id=str(row[0]),
                description=f"LC-002 FAIL: shipment {row[0]} is DELIVERED but actual_delivery_time is NULL",
                severity="HIGH",
            ))

        return results


class DuplicateEventValidator(BaseValidator):
    """LC-003: Detect duplicate tracking events (same shipment+type+event_time)."""

    name = "LC-003-duplicate-events"

    def validate(self, db) -> list[ValidationResult]:
        results = []
        rows = db.execute(text("""
            SELECT shipment_id, event_type, event_time, COUNT(*) AS cnt
            FROM tracking_events
            GROUP BY shipment_id, event_type, event_time
            HAVING COUNT(*) > 1
            LIMIT 100
        """)).fetchall()

        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DUPLICATE_TRACKING_EVENT",
                entity_type="TrackingEvent", entity_id="ALL", shipment_id=None,
                description="LC-003 PASS: no duplicate tracking events found",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DUPLICATE_TRACKING_EVENT",
                entity_type="TrackingEvent",
                entity_id=f"{row[0]}-{row[1]}-{row[2]}",
                shipment_id=str(row[0]),
                description=(
                    f"LC-003 FAIL: shipment {row[0]} has {row[3]} events with "
                    f"type={row[1]} at {row[2]}"
                ),
                severity="MEDIUM",
            ))
        return results


class DelayedScanValidator(BaseValidator):
    """LC-004/005: Detect delayed scans and late-arriving events."""

    name = "LC-004-005-delayed-scans"

    def validate(self, db) -> list[ValidationResult]:
        results = []

        # LC-004: ingestion lag > 48 hours (delayed scan)
        rows = db.execute(text(f"""
            SELECT event_id, shipment_id, event_time, ingestion_time,
                   EXTRACT(EPOCH FROM (ingestion_time - event_time)) / 3600 AS lag_hours
            FROM tracking_events
            WHERE ingestion_time > event_time + INTERVAL '{DELAYED_SCAN_THRESHOLD_HOURS} hours'
            LIMIT 100
        """)).fetchall()

        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DELAYED_SCAN",
                entity_type="TrackingEvent", entity_id="ALL", shipment_id=None,
                description=f"LC-004 PASS: no delayed scans (lag > {DELAYED_SCAN_THRESHOLD_HOURS}h)",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DELAYED_SCAN",
                entity_type="TrackingEvent", entity_id=str(row[0]), shipment_id=str(row[1]),
                description=(
                    f"LC-004 FAIL: event {row[0]} ingestion lag={row[4]:.1f}h "
                    f"(threshold={DELAYED_SCAN_THRESHOLD_HOURS}h)"
                ),
                severity="MEDIUM",
            ))

        # LC-005: late arrival (lag > 2h, less severe)
        rows_late = db.execute(text(f"""
            SELECT event_id, shipment_id,
                   EXTRACT(EPOCH FROM (ingestion_time - event_time)) / 3600 AS lag_hours
            FROM tracking_events
            WHERE ingestion_time > event_time + INTERVAL '{LATE_ARRIVAL_THRESHOLD_HOURS} hours'
              AND ingestion_time <= event_time + INTERVAL '{DELAYED_SCAN_THRESHOLD_HOURS} hours'
            LIMIT 200
        """)).fetchall()

        if not rows_late:
            results.append(ValidationResult(
                passed=True, issue_type="DELAYED_SCAN",
                entity_type="TrackingEvent", entity_id="ALL", shipment_id=None,
                description=f"LC-005 PASS: no late-arriving events (lag {LATE_ARRIVAL_THRESHOLD_HOURS}-{DELAYED_SCAN_THRESHOLD_HOURS}h)",
            ))
        for row in rows_late:
            results.append(ValidationResult(
                passed=False, issue_type="DELAYED_SCAN",
                entity_type="TrackingEvent", entity_id=str(row[0]), shipment_id=str(row[1]),
                description=f"LC-005 INFO: late-arriving event lag={row[2]:.1f}h",
                severity="LOW",
            ))

        return results


class DeliveredButInTransitValidator(BaseValidator):
    """LC-006: Shipment with status=DELIVERED but last event is IN_TRANSIT."""

    name = "LC-006-delivered-still-in-transit"

    def validate(self, db) -> list[ValidationResult]:
        results = []
        rows = db.execute(text("""
            WITH last_events AS (
                SELECT shipment_id, event_type,
                       ROW_NUMBER() OVER (
                           PARTITION BY shipment_id
                           ORDER BY event_time DESC, ingestion_time DESC
                       ) AS rn
                FROM tracking_events
            )
            SELECT s.shipment_id, le.event_type
            FROM shipments s
            JOIN last_events le ON s.shipment_id = le.shipment_id AND le.rn = 1
            WHERE s.status = 'DELIVERED'
              AND le.event_type = 'IN_TRANSIT'
            LIMIT 100
        """)).fetchall()

        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DELIVERED_STILL_IN_TRANSIT",
                entity_type="Shipment", entity_id="ALL", shipment_id=None,
                description="LC-006 PASS: no DELIVERED shipments with last event IN_TRANSIT",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DELIVERED_STILL_IN_TRANSIT",
                entity_type="Shipment", entity_id=str(row[0]), shipment_id=str(row[0]),
                description=f"LC-006 FAIL: shipment {row[0]} status=DELIVERED but last event=IN_TRANSIT",
                severity="HIGH",
            ))
        return results


class LegSequenceValidator(BaseValidator):
    """LC-007: Shipment leg sequences must be contiguous from 1."""

    name = "LC-007-leg-sequence-gaps"

    def validate(self, db) -> list[ValidationResult]:
        results = []
        rows = db.execute(text("""
            SELECT shipment_id,
                   array_agg(leg_sequence ORDER BY leg_sequence) AS seqs
            FROM shipment_legs
            GROUP BY shipment_id
            HAVING array_agg(leg_sequence ORDER BY leg_sequence) <>
                   (SELECT array_agg(gs) FROM generate_series(1, max(leg_sequence)) gs)
            LIMIT 100
        """)).fetchall()

        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="IMPOSSIBLE_ROUTE_ORDER",
                entity_type="ShipmentLeg", entity_id="ALL", shipment_id=None,
                description="LC-007 PASS: all shipment leg sequences are contiguous",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="IMPOSSIBLE_ROUTE_ORDER",
                entity_type="ShipmentLeg", entity_id=str(row[0]), shipment_id=str(row[0]),
                description=f"LC-007 FAIL: shipment {row[0]} has non-contiguous leg sequences: {row[1]}",
                severity="MEDIUM",
            ))
        return results
