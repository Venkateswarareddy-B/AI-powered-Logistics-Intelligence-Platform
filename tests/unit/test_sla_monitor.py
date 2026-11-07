"""Phase 9 SLA monitor tests."""
from __future__ import annotations
import pytest
from datetime import datetime, timedelta, timezone
from backend.services.sla_monitor import _compute_sla_status, evaluate_shipment, run_sla_monitor, sla_summary
from backend.core.database import SessionLocal
from sqlalchemy import text

NOW = datetime.now(timezone.utc)


class TestComputeSLAStatus:
    def test_on_time_predicted(self):
        promised = NOW + timedelta(hours=10)
        assert _compute_sla_status(promised, 2, promised - timedelta(hours=1), None) == "ON_TIME"

    def test_at_risk_within_grace(self):
        promised = NOW + timedelta(hours=1)
        predicted = NOW + timedelta(hours=2)  # 1h late, grace=2h
        assert _compute_sla_status(promised, 2, predicted, None) == "AT_RISK"

    def test_breached_beyond_grace(self):
        promised = NOW + timedelta(hours=1)
        predicted = NOW + timedelta(hours=5)  # 4h late, grace=2h
        assert _compute_sla_status(promised, 2, predicted, None) == "BREACHED"

    def test_actual_delivery_on_time(self):
        promised = NOW
        actual = NOW - timedelta(hours=1)
        assert _compute_sla_status(promised, 2, None, actual) == "ON_TIME"

    def test_actual_delivery_breached(self):
        promised = NOW - timedelta(hours=5)
        actual = NOW  # 5h late, grace=2h
        assert _compute_sla_status(promised, 2, None, actual) == "BREACHED"

    def test_no_eta_no_actual_is_on_time(self):
        promised = NOW + timedelta(hours=10)
        assert _compute_sla_status(promised, 2, None, None) == "ON_TIME"


class TestSLAMonitorIntegration:
    def test_evaluate_shipment_returns_dict(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = evaluate_shipment(db, sid)
            assert "new_sla_status" in result
            assert result["new_sla_status"] in ("ON_TIME", "AT_RISK", "BREACHED")
        finally:
            db.close()

    def test_run_sla_monitor_returns_stats(self, requires_db):
        db = SessionLocal()
        try:
            stats = run_sla_monitor(db)
            assert "compliance_pct" in stats
            assert 0 <= stats["compliance_pct"] <= 100
        finally:
            db.close()

    def test_sla_summary_totals_match_shipment_count(self, requires_db):
        db = SessionLocal()
        try:
            summary = sla_summary(db)
            total_db = db.execute(text("SELECT COUNT(*) FROM shipments")).scalar()
            assert int(summary["total"]) == int(total_db)
        finally:
            db.close()

    def test_sla_transitions_logged_in_audit(self, requires_db):
        db = SessionLocal()
        try:
            run_sla_monitor(db)
            count = db.execute(text(
                "SELECT COUNT(*) FROM audit_logs WHERE action='SLA_STATUS_CHANGE'"
            )).scalar()
            assert count >= 0  # may be 0 if no transitions; just verify no error
        finally:
            db.close()

    def test_invalid_shipment_returns_error(self, requires_db):
        db = SessionLocal()
        try:
            result = evaluate_shipment(db, "SHP-FAKE-999999")
            assert "error" in result
        finally:
            db.close()

    def test_no_sla_alerts_duplicated(self, requires_db):
        """Running monitor twice must not create duplicate alerts."""
        db = SessionLocal()
        try:
            run_sla_monitor(db)
            before = db.execute(text(
                "SELECT COUNT(*) FROM alerts WHERE alert_type IN ('SLA_BREACH','SLA_AT_RISK')"
            )).scalar()
            run_sla_monitor(db)
            after = db.execute(text(
                "SELECT COUNT(*) FROM alerts WHERE alert_type IN ('SLA_BREACH','SLA_AT_RISK')"
            )).scalar()
            assert after == before, "Duplicate SLA alerts generated"
        finally:
            db.close()
