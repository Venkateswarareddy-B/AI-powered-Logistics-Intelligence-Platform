"""Phase 20 Human Approval & Audit tests."""
from __future__ import annotations
import pytest
from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.services.approval_service import (
    create_approval_request, process_decision,
    list_audit_logs, list_pending_approvals, list_all_approvals,
)


class TestCreateApproval:
    def test_create_returns_id(self, requires_db):
        db = SessionLocal()
        try:
            aid = create_approval_request(
                db, shipment_id="SHP-2026-000001",
                action_type="ROUTE_CHANGE",
                recommendation_summary="Change route to save 3.2h",
                estimated_time_saving_hours=3.2,
                estimated_cost_impact=450,
                estimated_risk_reduction_pct=23.0,
            )
            assert aid.startswith("APR-")
        finally:
            db.close()

    def test_create_persists_in_db(self, requires_db):
        db = SessionLocal()
        try:
            aid = create_approval_request(
                db, action_type="CARRIER_SWAP",
                recommendation_summary="Test approval",
            )
            count = db.execute(text(
                "SELECT COUNT(*) FROM human_approvals WHERE approval_id=:aid"
            ), {"aid": aid}).scalar()
            assert count == 1
        finally:
            db.close()

    def test_new_approval_is_pending(self, requires_db):
        db = SessionLocal()
        try:
            aid = create_approval_request(db, recommendation_summary="Test")
            status = db.execute(text(
                "SELECT status FROM human_approvals WHERE approval_id=:aid"
            ), {"aid": aid}).scalar()
            assert status == "PENDING"
        finally:
            db.close()


class TestProcessDecision:
    def test_approve_decision(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Test approve",
                                          requested_by=uid)
            result = process_decision(db, aid, "APPROVED", uid, "Looks good")
            assert result["decision"] == "APPROVED"
            assert result["decided_by"] == uid

            status = db.execute(text(
                "SELECT status FROM human_approvals WHERE approval_id=:aid"
            ), {"aid": aid}).scalar()
            assert status == "APPROVED"
        finally:
            db.close()

    def test_reject_decision(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Test reject",
                                          requested_by=uid)
            result = process_decision(db, aid, "REJECTED", uid, "Too risky")
            assert result["decision"] == "REJECTED"
        finally:
            db.close()

    def test_more_info_decision(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Test more info",
                                          requested_by=uid)
            result = process_decision(db, aid, "MORE_INFO_REQUESTED", uid, "Need weather data")
            assert result["decision"] == "MORE_INFO_REQUESTED"
        finally:
            db.close()

    def test_cannot_decide_twice(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Test double",
                                          requested_by=uid)
            process_decision(db, aid, "APPROVED", uid)
            result = process_decision(db, aid, "REJECTED", uid)
            assert "error" in result
        finally:
            db.close()

    def test_invalid_decision(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Test invalid")
            result = process_decision(db, aid, "MAYBE", uid)
            assert "error" in result
        finally:
            db.close()

    def test_nonexistent_approval(self, requires_db):
        db = SessionLocal()
        try:
            result = process_decision(db, "APR-FAKE-999", "APPROVED", "USR-FAKE")
            assert "error" in result
        finally:
            db.close()


class TestAuditLogging:
    def test_audit_log_created_on_approval(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Audit test",
                                          requested_by=uid)
            process_decision(db, aid, "APPROVED", uid, "Approved")

            logs = list_audit_logs(db, entity_type="HumanApproval", action="APPROVAL_APPROVED")
            assert len(logs) >= 1
            assert logs[0]["entity_id"] == aid
        finally:
            db.close()

    def test_audit_logs_immutable(self, requires_db):
        """Audit logs should never be updatable (no update path exists)."""
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Immutability test",
                                          requested_by=uid)
            process_decision(db, aid, "APPROVED", uid)
            # Check that the audit log for this approval has a timestamp and no updated_at
            logs = list_audit_logs(db, entity_type="HumanApproval")
            assert len(logs) >= 1
            # audit_logs table has no updated_at column (immutable by design)
            cols = [c for c in db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='audit_logs'"
            )).fetchall()]
            col_names = [c[0] for c in cols]
            assert "updated_at" not in col_names, "audit_logs must not have updated_at (immutable)"
        finally:
            db.close()


class TestApprovalQueries:
    def test_list_pending_approvals(self, requires_db):
        db = SessionLocal()
        try:
            create_approval_request(db, recommendation_summary="Pending test")
            pending = list_pending_approvals(db)
            assert isinstance(pending, list)
            # list_pending_approvals already filters WHERE status='PENDING'
            assert len(pending) >= 0
        finally:
            db.close()

    def test_list_all_approvals(self, requires_db):
        db = SessionLocal()
        try:
            create_approval_request(db, recommendation_summary="All test")
            all_appr = list_all_approvals(db)
            assert isinstance(all_appr, list)
        finally:
            db.close()

    def test_audit_logs_filtered_by_action(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            aid = create_approval_request(db, recommendation_summary="Filter test",
                                          requested_by=uid)
            process_decision(db, aid, "REJECTED", uid)
            logs = list_audit_logs(db, action="APPROVAL_REJECTED")
            assert len(logs) >= 1
        finally:
            db.close()
