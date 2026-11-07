"""Enum value and date consistency validators.

Rules checked:
  ENUM-001  shipments.status must be one of the allowed lifecycle values.
  ENUM-002  shipments.priority must be LOW | NORMAL | HIGH | CRITICAL.
  ENUM-003  shipments.sla_status must be ON_TIME | AT_RISK | BREACHED.
  ENUM-004  tracking_events.event_type must be one of the allowed types.
  ENUM-005  weather_events.weather_type must be one of the allowed types.
  ENUM-006  facilities.facility_type must be one of the allowed types.
  DATE-001  shipments.promised_delivery_time > planned_ship_time.
  DATE-002  shipments.actual_delivery_time >= planned_ship_time (when set).
  DATE-003  shipment_legs.planned_arrival > planned_departure.
  DATE-004  tracking_events.ingestion_time >= event_time (normal case; flag when violated).
  DATE-005  weather_events.end_time > start_time.
"""

from __future__ import annotations

import logging
from sqlalchemy import text

from data_engineering.validation.base import BaseValidator, ValidationResult

log = logging.getLogger("data_engineering.validation.enum_date")

_SHIPMENT_STATUSES = (
    "CREATED", "PICKED_UP", "IN_TRANSIT", "AT_FACILITY",
    "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "EXCEPTION",
)
_PRIORITIES = ("LOW", "NORMAL", "HIGH", "CRITICAL")
_SLA_STATUSES = ("ON_TIME", "AT_RISK", "BREACHED")
_EVENT_TYPES = (
    "PICKED_UP", "DEPARTED_FACILITY", "ARRIVED_FACILITY", "IN_TRANSIT",
    "DELAYED", "ROUTE_CHANGED", "OUT_FOR_DELIVERY", "DELIVERED",
)
_WEATHER_TYPES = ("NORMAL", "RAIN", "HEAVY_RAIN", "STORM", "FLOOD", "EXTREME_HEAT", "FOG")
_FACILITY_TYPES = ("WAREHOUSE", "HUB", "DISTRIBUTION_CENTER", "SORTING_CENTER", "DELIVERY_CENTER")


def _in_list(values: tuple) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"({quoted})"


class EnumValidator(BaseValidator):
    """ENUM-001 through ENUM-006: Validate enum columns."""

    name = "ENUM-001-006-enum-values"

    _CHECKS = [
        ("shipments",       "shipment_id",       "status",        _SHIPMENT_STATUSES, "ENUM-001"),
        ("shipments",       "shipment_id",       "priority",      _PRIORITIES,        "ENUM-002"),
        ("shipments",       "shipment_id",       "sla_status",    _SLA_STATUSES,      "ENUM-003"),
        ("tracking_events", "event_id",          "event_type",    _EVENT_TYPES,       "ENUM-004"),
        ("weather_events",  "weather_event_id",  "weather_type",  _WEATHER_TYPES,     "ENUM-005"),
        ("facilities",      "facility_id",       "facility_type", _FACILITY_TYPES,    "ENUM-006"),
    ]

    def validate(self, db) -> list[ValidationResult]:
        results = []
        for table, pk_col, col, allowed, rule in self._CHECKS:
            allowed_sql = _in_list(allowed)
            rows = db.execute(text(f"""
                SELECT {pk_col}, {col}
                FROM {table}
                WHERE {col} NOT IN {allowed_sql}
                LIMIT 100
            """)).fetchall()

            if not rows:
                results.append(ValidationResult(
                    passed=True,
                    issue_type="ENUM_VIOLATION",
                    entity_type=table,
                    entity_id="ALL",
                    shipment_id=None,
                    description=f"{rule} PASS: all {table}.{col} values are valid",
                    severity="LOW",
                ))
            else:
                for row in rows:
                    shp_id = str(row[0]) if table == "shipments" else None
                    results.append(ValidationResult(
                        passed=False,
                        issue_type="ENUM_VIOLATION",
                        entity_type=table,
                        entity_id=str(row[0]),
                        shipment_id=shp_id,
                        description=(
                            f"{rule} FAIL: {table}.{col}={row[1]!r} is not in allowed values"
                        ),
                        severity="HIGH",
                    ))
        return results


class DateConsistencyValidator(BaseValidator):
    """DATE-001 through DATE-005: Validate timestamp ordering."""

    name = "DATE-001-005-date-consistency"

    def validate(self, db) -> list[ValidationResult]:
        results = []

        # DATE-001: promised_delivery_time > planned_ship_time
        rows = db.execute(text("""
            SELECT shipment_id, planned_ship_time, promised_delivery_time
            FROM shipments
            WHERE promised_delivery_time <= planned_ship_time
            LIMIT 100
        """)).fetchall()
        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DATE_INCONSISTENCY",
                entity_type="Shipment", entity_id="ALL", shipment_id=None,
                description="DATE-001 PASS: all promised_delivery_time > planned_ship_time",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DATE_INCONSISTENCY",
                entity_type="Shipment", entity_id=str(row[0]), shipment_id=str(row[0]),
                description=f"DATE-001 FAIL: promised_delivery_time={row[2]} <= planned_ship_time={row[1]}",
                severity="HIGH",
            ))

        # DATE-002: actual_delivery_time >= planned_ship_time (when set)
        rows = db.execute(text("""
            SELECT shipment_id, planned_ship_time, actual_delivery_time
            FROM shipments
            WHERE actual_delivery_time IS NOT NULL
              AND actual_delivery_time < planned_ship_time
            LIMIT 100
        """)).fetchall()
        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DATE_INCONSISTENCY",
                entity_type="Shipment", entity_id="ALL", shipment_id=None,
                description="DATE-002 PASS: all actual_delivery_time >= planned_ship_time",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DATE_INCONSISTENCY",
                entity_type="Shipment", entity_id=str(row[0]), shipment_id=str(row[0]),
                description=f"DATE-002 FAIL: actual_delivery_time={row[2]} < planned_ship_time={row[1]}",
                severity="HIGH",
            ))

        # DATE-003: leg planned_arrival > planned_departure
        rows = db.execute(text("""
            SELECT leg_id, planned_departure, planned_arrival
            FROM shipment_legs
            WHERE planned_arrival <= planned_departure
            LIMIT 100
        """)).fetchall()
        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DATE_INCONSISTENCY",
                entity_type="ShipmentLeg", entity_id="ALL", shipment_id=None,
                description="DATE-003 PASS: all leg planned_arrival > planned_departure",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DATE_INCONSISTENCY",
                entity_type="ShipmentLeg", entity_id=str(row[0]), shipment_id=None,
                description=f"DATE-003 FAIL: leg {row[0]} arrival={row[2]} <= departure={row[1]}",
                severity="HIGH",
            ))

        # DATE-004: ingestion_time < event_time (anomalous — should be flagged)
        rows = db.execute(text("""
            SELECT event_id, shipment_id, event_time, ingestion_time
            FROM tracking_events
            WHERE ingestion_time < event_time
            LIMIT 100
        """)).fetchall()
        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="INGESTION_TIME_CONFUSION",
                entity_type="TrackingEvent", entity_id="ALL", shipment_id=None,
                description="DATE-004 PASS: no events where ingestion_time < event_time",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="INGESTION_TIME_CONFUSION",
                entity_type="TrackingEvent", entity_id=str(row[0]), shipment_id=str(row[1]),
                description=(
                    f"DATE-004 FAIL: event {row[0]} ingestion_time={row[3]} < event_time={row[2]}"
                ),
                severity="HIGH",
            ))

        # DATE-005: weather end_time > start_time
        rows = db.execute(text("""
            SELECT weather_event_id, start_time, end_time
            FROM weather_events
            WHERE end_time <= start_time
            LIMIT 100
        """)).fetchall()
        if not rows:
            results.append(ValidationResult(
                passed=True, issue_type="DATE_INCONSISTENCY",
                entity_type="WeatherEvent", entity_id="ALL", shipment_id=None,
                description="DATE-005 PASS: all weather end_time > start_time",
            ))
        for row in rows:
            results.append(ValidationResult(
                passed=False, issue_type="DATE_INCONSISTENCY",
                entity_type="WeatherEvent", entity_id=str(row[0]), shipment_id=None,
                description=f"DATE-005 FAIL: weather {row[0]} end_time={row[2]} <= start_time={row[1]}",
                severity="MEDIUM",
            ))

        return results
