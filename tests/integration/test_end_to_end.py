"""End-to-end workflow tests (Phase 22).

Tests the complete pipeline: generate → validate → ETL → predict →
explain → SLA monitor → alerts → approve → audit.
"""
from __future__ import annotations
import pytest
from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.services.eta_engine import predict_eta
from backend.services.sla_monitor import run_sla_monitor
from backend.services.alert_service import run_alert_generation
from backend.services.approval_service import (
    create_approval_request, process_decision, list_audit_logs,
)
from backend.services.explainability import explain_prediction


class TestFullWorkflow:
    """Verify the complete operational workflow works end-to-end."""

    def test_eta_to_sla_to_alerts_chain(self, requires_db):
        """ETA prediction → SLA evaluation → alert generation."""
        db = SessionLocal()
        try:
            # 1. Get an active shipment
            sid = db.execute(text("""
                SELECT shipment_id FROM shipments
                WHERE status NOT IN ('DELIVERED','CANCELLED') LIMIT 1
            """)).scalar()
            if not sid:
                pytest.skip("No active shipments")

            # 2. Predict ETA
            eta_result = predict_eta(db, sid)
            assert eta_result is not None
            assert "predicted_eta" in eta_result

            # 3. Evaluate SLA
            from backend.services.sla_monitor import evaluate_shipment
            sla_result = evaluate_shipment(db, sid)
            assert sla_result["new_sla_status"] in ("ON_TIME", "AT_RISK", "BREACHED")

            # 4. Generate alerts
            alert_result = run_alert_generation(db)
            assert "new_alerts" in alert_result
        finally:
            db.close()

    def test_eta_to_explanation_chain(self, requires_db):
        """ETA prediction → explanation."""
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if not sid:
                pytest.skip("No gold features")
            explanation = explain_prediction(db, sid, "DELAY")
            assert explanation is not None
            assert "explanation_method" in explanation
        finally:
            db.close()

    def test_approval_to_audit_chain(self, requires_db):
        """Approval creation → decision → audit log."""
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            if not uid: pytest.skip("No users")

            # Create approval
            aid = create_approval_request(
                db, shipment_id="SHP-2026-000001",
                action_type="ROUTE_CHANGE",
                recommendation_summary="E2E test: change route",
                requested_by=uid,
            )

            # Approve it
            result = process_decision(db, aid, "APPROVED", uid, "E2E test approved")
            assert result["decision"] == "APPROVED"

            # Verify audit log
            logs = list_audit_logs(db, entity_type="HumanApproval", action="APPROVAL_APPROVED")
            found = [l for l in logs if l["entity_id"] == aid]
            assert len(found) >= 1
        finally:
            db.close()

    def test_full_agent_workflow(self, requires_db):
        """Agent → tools → recommendation → persisted decision."""
        db = SessionLocal()
        try:
            from agents.agent import run_agent
            result = run_agent(db, "Summarize today's logistics situation and recommend actions")
            assert "agent_decision_id" in result
            assert "recommendation" in result
            assert "tools_used" in result
            assert len(result["tools_used"]) > 0

            # Verify persisted
            count = db.execute(text(
                "SELECT COUNT(*) FROM agent_decisions WHERE agent_decision_id=:aid"
            ), {"aid": result["agent_decision_id"]}).scalar()
            assert count == 1
        finally:
            db.close()

    def test_route_comparison_to_approval_chain(self, requires_db):
        """Route comparison → approval request."""
        db = SessionLocal()
        try:
            from backend.services.route_service import compare_routes
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            comparison = compare_routes(db, sid)
            if "current_route" in comparison:
                # Create an approval for the route change
                uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
                aid = create_approval_request(
                    db, shipment_id=sid,
                    action_type="ROUTE_CHANGE",
                    recommendation_summary=f"Route comparison for {sid}",
                    requested_by=uid,
                )
                assert aid.startswith("APR-")
        finally:
            db.close()


class TestDataIntegrityRegression:
    """Verify data integrity is maintained across the full pipeline."""

    def test_all_shipments_have_valid_carrier(self, requires_db):
        db = SessionLocal()
        try:
            orphans = db.execute(text("""
                SELECT COUNT(*) FROM shipments s
                LEFT JOIN carriers c ON s.carrier_id = c.carrier_id
                WHERE c.carrier_id IS NULL
            """)).scalar()
            assert orphans == 0
        finally:
            db.close()

    def test_all_tracking_events_have_valid_shipment(self, requires_db):
        db = SessionLocal()
        try:
            orphans = db.execute(text("""
                SELECT COUNT(*) FROM tracking_events te
                LEFT JOIN shipments s ON te.shipment_id = s.shipment_id
                WHERE s.shipment_id IS NULL
            """)).scalar()
            assert orphans == 0
        finally:
            db.close()

    def test_gold_features_subset_of_silver(self, requires_db):
        """Every gold feature row must correspond to a usable silver shipment."""
        db = SessionLocal()
        try:
            orphans = db.execute(text("""
                SELECT COUNT(*) FROM gold_shipment_features g
                LEFT JOIN silver_shipments s
                  ON g.shipment_id = s.shipment_id AND s.is_usable_for_ml = TRUE
                WHERE s.shipment_id IS NULL
            """)).scalar()
            assert orphans == 0
        finally:
            db.close()

    def test_no_eta_leakage(self, requires_db):
        """No ETA estimate has feature_cutoff_time > prediction_time."""
        db = SessionLocal()
        try:
            violations = db.execute(text("""
                SELECT COUNT(*) FROM eta_estimates
                WHERE feature_cutoff_time > prediction_time
            """)).scalar()
            assert violations == 0
        finally:
            db.close()

    def test_sla_statuses_valid(self, requires_db):
        db = SessionLocal()
        try:
            invalid = db.execute(text("""
                SELECT COUNT(*) FROM shipments
                WHERE sla_status NOT IN ('ON_TIME','AT_RISK','BREACHED')
            """)).scalar()
            assert invalid == 0
        finally:
            db.close()

    def test_no_duplicate_open_alerts(self, requires_db):
        """No two OPEN alerts with the same dedup_key."""
        db = SessionLocal()
        try:
            dupes = db.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT dedup_key FROM alerts
                    WHERE status='OPEN' AND dedup_key IS NOT NULL
                    GROUP BY dedup_key HAVING COUNT(*) > 1
                ) t
            """)).scalar()
            assert dupes == 0
        finally:
            db.close()

    def test_active_model_versions_exist(self, requires_db):
        """Both ETA and DELAY models must have an active version."""
        db = SessionLocal()
        try:
            eta_count = db.execute(text(
                "SELECT COUNT(*) FROM model_versions WHERE model_type='ETA' AND is_active=TRUE"
            )).scalar()
            delay_count = db.execute(text(
                "SELECT COUNT(*) FROM model_versions WHERE model_type='DELAY' AND is_active=TRUE"
            )).scalar()
            assert eta_count >= 1, "No active ETA model"
            assert delay_count >= 1, "No active DELAY model"
        finally:
            db.close()
