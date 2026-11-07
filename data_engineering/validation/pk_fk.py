"""PK uniqueness and FK integrity validators.

These validators run SQL-level checks directly against the database so they
catch any inconsistency regardless of how data arrived (generator, manual
insert, external feed).

Rules checked:
  PK-001  No duplicate primary keys in any tracked table.
  FK-001  All shipments.carrier_id reference a real carrier.
  FK-002  All shipments.service_level_id reference a real service_level.
  FK-003  All shipments.route_id reference a real route.
  FK-004  All shipments.origin_facility_id reference a real facility.
  FK-005  All shipments.destination_facility_id reference a real facility.
  FK-006  All tracking_events.shipment_id reference a real shipment.
  FK-007  All tracking_events.facility_id (when not NULL) reference a real facility.
  FK-008  All shipment_legs.shipment_id reference a real shipment.
  FK-009  All eta_estimates.shipment_id reference a real shipment.
  FK-010  All facility_queues.facility_id reference a real facility.
"""

from __future__ import annotations

import logging
from sqlalchemy import text

from data_engineering.validation.base import BaseValidator, ValidationResult

log = logging.getLogger("data_engineering.validation.pk_fk")


class DuplicatePKValidator(BaseValidator):
    """PK-001: Detect duplicate primary keys per table."""

    name = "PK-001-duplicate-pks"

    # (table, pk_column) pairs to check
    _TABLES = [
        ("shipments",       "shipment_id"),
        ("tracking_events", "event_id"),
        ("facilities",      "facility_id"),
        ("carriers",        "carrier_id"),
        ("routes",          "route_id"),
        ("weather_events",  "weather_event_id"),
        ("shipment_legs",   "leg_id"),
        ("eta_estimates",   "eta_estimate_id"),
        ("facility_queues", "queue_id"),
        ("roles",           "role_id"),
        ("users",           "user_id"),
    ]

    def validate(self, db) -> list[ValidationResult]:
        results = []
        for table, pk_col in self._TABLES:
            rows = db.execute(text(f"""
                SELECT {pk_col}, COUNT(*) AS cnt
                FROM {table}
                GROUP BY {pk_col}
                HAVING COUNT(*) > 1
                LIMIT 100
            """)).fetchall()

            if not rows:
                results.append(ValidationResult(
                    passed=True,
                    issue_type="DUPLICATE_PK",
                    entity_type=table,
                    entity_id="ALL",
                    shipment_id=None,
                    description=f"PK-001 PASS: no duplicate PKs in {table}",
                    severity="LOW",
                ))
            else:
                for row in rows:
                    results.append(ValidationResult(
                        passed=False,
                        issue_type="DUPLICATE_PK",
                        entity_type=table,
                        entity_id=str(row[0]),
                        shipment_id=str(row[0]) if table == "shipments" else None,
                        description=f"PK-001 FAIL: {table}.{pk_col}={row[0]} appears {row[1]} times",
                        severity="CRITICAL",
                    ))
        return results


class FKIntegrityValidator(BaseValidator):
    """FK-001 through FK-010: Detect orphaned foreign key references."""

    name = "FK-001-010-fk-integrity"

    # (child_table, fk_col, parent_table, parent_pk, nullable, rule_id)
    _CHECKS = [
        ("shipments",       "carrier_id",             "carriers",      "carrier_id",    False, "FK-001"),
        ("shipments",       "service_level_id",       "service_levels","service_level_id",False,"FK-002"),
        ("shipments",       "route_id",               "routes",        "route_id",      False, "FK-003"),
        ("shipments",       "origin_facility_id",     "facilities",    "facility_id",   False, "FK-004"),
        ("shipments",       "destination_facility_id","facilities",    "facility_id",   False, "FK-005"),
        ("tracking_events", "shipment_id",            "shipments",     "shipment_id",   False, "FK-006"),
        ("tracking_events", "facility_id",            "facilities",    "facility_id",   True,  "FK-007"),
        ("shipment_legs",   "shipment_id",            "shipments",     "shipment_id",   False, "FK-008"),
        ("eta_estimates",   "shipment_id",            "shipments",     "shipment_id",   False, "FK-009"),
        ("facility_queues", "facility_id",            "facilities",    "facility_id",   False, "FK-010"),
    ]

    def validate(self, db) -> list[ValidationResult]:
        results = []
        for child_tbl, fk_col, parent_tbl, parent_pk, nullable, rule in self._CHECKS:
            null_clause = f"AND c.{fk_col} IS NOT NULL" if nullable else ""
            sql = f"""
                SELECT c.{fk_col}
                FROM {child_tbl} c
                LEFT JOIN {parent_tbl} p ON c.{fk_col} = p.{parent_pk}
                WHERE p.{parent_pk} IS NULL
                  {null_clause}
                LIMIT 50
            """
            orphans = db.execute(text(sql)).fetchall()
            if not orphans:
                results.append(ValidationResult(
                    passed=True,
                    issue_type="FK_VIOLATION",
                    entity_type=child_tbl,
                    entity_id="ALL",
                    shipment_id=None,
                    description=f"{rule} PASS: all {child_tbl}.{fk_col} are valid",
                    severity="LOW",
                ))
            else:
                for row in orphans:
                    results.append(ValidationResult(
                        passed=False,
                        issue_type="FK_VIOLATION",
                        entity_type=child_tbl,
                        entity_id=str(row[0]) if row[0] else "NULL",
                        shipment_id=None,
                        description=(
                            f"{rule} FAIL: {child_tbl}.{fk_col}={row[0]} "
                            f"has no matching {parent_tbl}.{parent_pk}"
                        ),
                        severity="HIGH",
                    ))
        return results
