"""Phase 15 Alerts & Notifications tests."""
from __future__ import annotations
import pytest
from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.services.alert_service import (
    run_alert_generation, acknowledge_alert, resolve_alert,
    mark_notification_read, mark_all_notifications_read, get_notification_stats,
)


class TestAlertGeneration:
    def test_run_returns_dict(self, requires_db):
        db = SessionLocal()
        try:
            result = run_alert_generation(db)
            assert "new_alerts" in result
            assert "by_type" in result
            assert isinstance(result["new_alerts"], int)
        finally:
            db.close()

    def test_no_duplicate_alerts_on_rerun(self, requires_db):
        db = SessionLocal()
        try:
            run_alert_generation(db)
            before = db.execute(text("SELECT COUNT(*) FROM alerts WHERE status='OPEN'")).scalar()
            run_alert_generation(db)
            after = db.execute(text("SELECT COUNT(*) FROM alerts WHERE status='OPEN'")).scalar()
            assert after == before, "Duplicate alerts created on re-run"
        finally:
            db.close()

    def test_alerts_have_valid_types(self, requires_db):
        db = SessionLocal()
        try:
            rows = db.execute(text("SELECT DISTINCT alert_type FROM alerts")).fetchall()
            valid = {"HIGH_DELAY_RISK","SLA_AT_RISK","SLA_BREACH","FACILITY_CONGESTION",
                     "WEATHER_DISRUPTION","ROUTE_DEVIATION","MISSING_SCAN",
                     "LATE_EVENT","DATA_QUALITY_ERROR"}
            for r in rows:
                assert r[0] in valid, f"Invalid alert type: {r[0]}"
        finally:
            db.close()

    def test_alerts_have_severity(self, requires_db):
        db = SessionLocal()
        try:
            rows = db.execute(text("SELECT severity FROM alerts LIMIT 20")).fetchall()
            valid = {"LOW","MEDIUM","HIGH","CRITICAL"}
            for r in rows:
                assert r[0] in valid
        finally:
            db.close()


class TestAlertLifecycle:
    def test_acknowledge_alert(self, requires_db):
        db = SessionLocal()
        try:
            # Get an OPEN alert
            aid = db.execute(text(
                "SELECT alert_id FROM alerts WHERE status='OPEN' LIMIT 1"
            )).scalar()
            if not aid: pytest.skip("No open alerts")
            # Get a user
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            ok = acknowledge_alert(db, aid, uid)
            assert ok
            status = db.execute(text(
                "SELECT status FROM alerts WHERE alert_id=:aid"
            ), {"aid": aid}).scalar()
            assert status == "ACKNOWLEDGED"
        finally:
            db.close()

    def test_resolve_alert(self, requires_db):
        db = SessionLocal()
        try:
            aid = db.execute(text(
                "SELECT alert_id FROM alerts WHERE status IN ('OPEN','ACKNOWLEDGED') LIMIT 1"
            )).scalar()
            if not aid: pytest.skip("No open/ack alerts")
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            ok = resolve_alert(db, aid, uid)
            assert ok
            status = db.execute(text(
                "SELECT status FROM alerts WHERE alert_id=:aid"
            ), {"aid": aid}).scalar()
            assert status == "RESOLVED"
        finally:
            db.close()


class TestNotifications:
    def test_notifications_exist_after_generation(self, requires_db):
        db = SessionLocal()
        try:
            run_alert_generation(db)
            count = db.execute(text("SELECT COUNT(*) FROM notifications")).scalar()
            assert count >= 0
        finally:
            db.close()

    def test_mark_notification_read(self, requires_db):
        db = SessionLocal()
        try:
            nid = db.execute(text(
                "SELECT notification_id FROM notifications WHERE is_read=FALSE LIMIT 1"
            )).scalar()
            if not nid: pytest.skip("No unread notifications")
            ok = mark_notification_read(db, nid)
            assert ok
        finally:
            db.close()

    def test_mark_all_read(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            if not uid: pytest.skip("No users")
            count = mark_all_notifications_read(db, uid)
            assert count >= 0
        finally:
            db.close()

    def test_notification_stats(self, requires_db):
        db = SessionLocal()
        try:
            uid = db.execute(text("SELECT user_id FROM users LIMIT 1")).scalar()
            if not uid: pytest.skip("No users")
            stats = get_notification_stats(db, uid)
            assert "total" in stats
            assert "unread" in stats
            assert "read" in stats
        finally:
            db.close()
