"""Schema integration tests (Phase 3).

Verify every important structural property of the live database:
- All 27 tables exist.
- Primary keys are defined.
- Foreign keys are present on key relationships.
- Check constraints are in place.
- Unique constraints exist where required.
- Enum values are enforced.

All tests require a live PostgreSQL (skipped otherwise via ``requires_db``).
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from backend.core.database import engine, SessionLocal

# ── helpers ──────────────────────────────────────────────────────────────────

EXPECTED_TABLES = {
    "roles", "users", "service_levels", "carriers", "routes",
    "facilities", "facility_queues", "weather_events",
    "shipments", "shipment_legs", "tracking_events",
    "eta_estimates", "delay_reasons", "route_changes",
    "carrier_performance", "facility_performance",
    "alerts", "notifications", "notification_preferences",
    "audit_logs", "agent_decisions", "human_approvals",
    "model_versions", "prediction_explanations", "data_quality_issues",
    "rag_documents", "rag_ingestion_jobs",
}


def _inspector():
    return inspect(engine)


# ── table existence ──────────────────────────────────────────────────────────

class TestTableExistence:
    def test_all_27_tables_exist(self, requires_db):
        insp = _inspector()
        actual = set(insp.get_table_names())
        missing = EXPECTED_TABLES - actual
        assert not missing, f"Missing tables: {missing}"

    def test_alembic_version_table_exists(self, requires_db):
        insp = _inspector()
        assert "alembic_version" in insp.get_table_names()

    def test_table_count_at_least_27(self, requires_db):
        insp = _inspector()
        actual = {t for t in insp.get_table_names() if t != "alembic_version"}
        assert len(actual) >= 27


# ── primary keys ─────────────────────────────────────────────────────────────

class TestPrimaryKeys:
    @pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
    def test_table_has_primary_key(self, requires_db, table):
        insp = _inspector()
        pk = insp.get_pk_constraint(table)
        assert pk["constrained_columns"], f"{table} has no PK columns"


# ── foreign keys ─────────────────────────────────────────────────────────────

class TestForeignKeys:
    @pytest.mark.parametrize("table,fk_col,ref_table", [
        ("shipments", "carrier_id", "carriers"),
        ("shipments", "service_level_id", "service_levels"),
        ("shipments", "route_id", "routes"),
        ("shipments", "origin_facility_id", "facilities"),
        ("shipments", "destination_facility_id", "facilities"),
        ("shipment_legs", "shipment_id", "shipments"),
        ("tracking_events", "shipment_id", "shipments"),
        ("eta_estimates", "shipment_id", "shipments"),
        ("delay_reasons", "shipment_id", "shipments"),
        ("route_changes", "shipment_id", "shipments"),
        ("facility_queues", "facility_id", "facilities"),
        ("routes", "origin_facility_id", "facilities"),
        ("routes", "destination_facility_id", "facilities"),
        ("users", "role_id", "roles"),
        ("alerts", "shipment_id", "shipments"),
        ("notifications", "user_id", "users"),
        ("carrier_performance", "carrier_id", "carriers"),
        ("facility_performance", "facility_id", "facilities"),
        ("rag_ingestion_jobs", "document_id", "rag_documents"),
        ("human_approvals", "agent_decision_id", "agent_decisions"),
        ("prediction_explanations", "shipment_id", "shipments"),
    ])
    def test_foreign_key_exists(self, requires_db, table, fk_col, ref_table):
        insp = _inspector()
        fks = insp.get_foreign_keys(table)
        matching = [
            fk for fk in fks
            if fk_col in fk["constrained_columns"]
            and fk["referred_table"] == ref_table
        ]
        assert matching, (
            f"{table}.{fk_col} → {ref_table} FK not found. "
            f"Existing FKs: {[(f['constrained_columns'], f['referred_table']) for f in fks]}"
        )


# ── unique constraints ────────────────────────────────────────────────────────

class TestUniqueConstraints:
    @pytest.mark.parametrize("table,col", [
        ("carriers", "carrier_name"),
        ("carriers", "carrier_code"),
        ("service_levels", "name"),
        ("users", "username"),
        ("roles", "role_name"),
    ])
    def test_unique_constraint(self, requires_db, table, col):
        insp = _inspector()
        ucs = insp.get_unique_constraints(table)
        # Unique might also be enforced via unique index
        indexes = insp.get_indexes(table)
        in_uc = any(col in uc["column_names"] for uc in ucs)
        in_idx = any(
            col in idx["column_names"] and idx.get("unique")
            for idx in indexes
        )
        assert in_uc or in_idx, f"No unique constraint/index on {table}.{col}"

    def test_shipment_leg_sequence_unique(self, requires_db):
        insp = _inspector()
        ucs = insp.get_unique_constraints("shipment_legs")
        found = any(
            set(uc["column_names"]) == {"shipment_id", "leg_sequence"}
            for uc in ucs
        )
        assert found, "shipment_legs missing unique(shipment_id, leg_sequence)"


# ── check constraints via live inserts ──────────────────────────────────────

class TestCheckConstraints:
    def test_invalid_shipment_status_rejected(self, requires_db):
        """Inserting a shipment with bad status must fail."""
        db = SessionLocal()
        try:
            db.execute(text("""
                INSERT INTO carriers (carrier_id, carrier_name, carrier_code, created_at, updated_at)
                VALUES ('TEST-CRR-TST', 'Test Carrier TST', 'TCTST99',
                        NOW(), NOW())
                ON CONFLICT DO NOTHING
            """))
            db.execute(text("""
                INSERT INTO service_levels
                    (service_level_id, name, maximum_delivery_hours, allowed_delay_hours,
                     created_at, updated_at)
                VALUES ('STANDARD','Standard',48,2, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """))
            db.execute(text("""
                INSERT INTO facilities
                    (facility_id, facility_name, facility_type, city, state, capacity,
                     created_at, updated_at)
                VALUES ('FAC-TST-001','Test Hub TST','HUB','Chennai','TN',100, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """))
            db.execute(text("""
                INSERT INTO routes
                    (route_id, route_name, origin_facility_id, destination_facility_id,
                     distance_km, base_transit_hours, created_at, updated_at)
                VALUES ('RT-TST-999','Test Route TST','FAC-TST-001','FAC-TST-001',100,5, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """))
            db.commit()
        except Exception:
            db.rollback()

        try:
            db.execute(text("""
                INSERT INTO shipments
                    (shipment_id, carrier_id, service_level_id, route_id,
                     origin_facility_id, destination_facility_id,
                     planned_ship_time, promised_delivery_time, status, priority,
                     sla_status, created_at, updated_at)
                VALUES ('SHP-2026-TST99','TEST-CRR-TST','STANDARD','RT-TST-999',
                        'FAC-TST-001','FAC-TST-001',
                        NOW(), NOW() + INTERVAL '48 hours',
                        'INVALID_STATUS','NORMAL','ON_TIME', NOW(), NOW())
            """))
            db.commit()
            pytest.fail("Expected check constraint violation for invalid status")
        except IntegrityError:
            db.rollback()
        finally:
            # Cleanup test data (cascade handles shipments)
            db.execute(text("DELETE FROM routes WHERE route_id='RT-TST-999'"))
            db.execute(text("DELETE FROM facilities WHERE facility_id='FAC-TST-001'"))
            db.execute(text("DELETE FROM carriers WHERE carrier_id='TEST-CRR-TST'"))
            db.commit()
            db.close()

    def test_weather_type_constraint(self, requires_db):
        """Invalid weather_type must be rejected by check constraint."""
        db = SessionLocal()
        try:
            db.execute(text("""
                INSERT INTO weather_events
                    (weather_event_id, location, start_time, end_time,
                     weather_type, severity, delay_factor, created_at, updated_at)
                VALUES ('WX-TEST-01','Chennai',NOW(), NOW() + INTERVAL '3 hours',
                        'TORNADO', 3, 1.5, NOW(), NOW())
            """))
            db.commit()
            pytest.fail("Expected check constraint violation for invalid weather_type")
        except IntegrityError:
            db.rollback()
        finally:
            db.close()


# ── alembic version recorded ──────────────────────────────────────────────────

class TestMigrationState:
    def test_alembic_has_one_revision(self, requires_db):
        db = SessionLocal()
        try:
            rows = db.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            assert len(rows) == 1, f"Expected 1 alembic revision, got {len(rows)}"
            assert rows[0][0], "Alembic version_num is empty"
        finally:
            db.close()
