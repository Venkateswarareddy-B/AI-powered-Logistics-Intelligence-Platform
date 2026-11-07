"""Phase 8 ETA engine tests."""
from __future__ import annotations
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from backend.services.eta_engine import predict_eta, predict_eta_batch, snapshot_all_active
from backend.core.database import SessionLocal
from sqlalchemy import text


# ── Unit tests (no DB) ────────────────────────────────────────────────────────

class TestETAEngineUnit:
    def test_predict_eta_missing_shipment_returns_none(self):
        db = MagicMock()
        db.execute.return_value.mappings.return_value.fetchone.return_value = None
        result = predict_eta(db, "SHP-FAKE-000000")
        assert result is None

    def test_feature_cutoff_equals_prediction_time(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM shipments LIMIT 1"
            )).scalar()
            pt = datetime.now(timezone.utc)
            est = predict_eta(db, sid, pt)
            if est:
                assert est["feature_cutoff_time"] == est["prediction_time"]
        finally:
            db.close()


# ── Integration tests ─────────────────────────────────────────────────────────

class TestETAEngineIntegration:
    def test_predict_eta_returns_dict(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM shipments LIMIT 1"
            )).scalar()
            est = predict_eta(db, sid)
            assert isinstance(est, dict)
            assert "predicted_eta" in est
            assert "delay_probability" in est
        finally:
            db.close()

    def test_delay_probability_in_range(self, requires_db):
        db = SessionLocal()
        try:
            rows = db.execute(text(
                "SELECT shipment_id FROM shipments LIMIT 5"
            )).fetchall()
            for r in rows:
                est = predict_eta(db, r[0])
                if est:
                    dp = est["delay_probability"]
                    assert 0.0 <= dp <= 1.0, f"delay_probability={dp} out of range"
        finally:
            db.close()

    def test_predicted_eta_after_ship_time(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM shipments LIMIT 1"
            )).scalar()
            est = predict_eta(db, sid)
            if est:
                planned = db.execute(text(
                    "SELECT planned_ship_time FROM shipments WHERE shipment_id=:s"
                ), {"s": sid}).scalar()
                pred = datetime.fromisoformat(est["predicted_eta"])
                assert pred > planned
        finally:
            db.close()

    def test_estimate_persisted_in_db(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM shipments LIMIT 1"
            )).scalar()
            pt = datetime.now(timezone.utc)
            est = predict_eta(db, sid, pt)
            if est:
                count = db.execute(text(
                    "SELECT COUNT(*) FROM eta_estimates WHERE eta_estimate_id=:eid"
                ), {"eid": est["eta_estimate_id"]}).scalar()
                assert count == 1
        finally:
            db.close()

    def test_feature_cutoff_lte_prediction_time_in_db(self, requires_db):
        """Leakage contract: feature_cutoff_time <= prediction_time always."""
        db = SessionLocal()
        try:
            violations = db.execute(text("""
                SELECT COUNT(*) FROM eta_estimates
                WHERE feature_cutoff_time > prediction_time
            """)).scalar()
            assert violations == 0
        finally:
            db.close()

    def test_batch_prediction(self, requires_db):
        db = SessionLocal()
        try:
            sids = [r[0] for r in db.execute(text(
                "SELECT shipment_id FROM shipments LIMIT 3"
            )).fetchall()]
            estimates = predict_eta_batch(db, sids)
            assert len(estimates) == len(sids)
        finally:
            db.close()

    def test_snapshot_all_active(self, requires_db):
        db = SessionLocal()
        try:
            count = snapshot_all_active(db)
            assert count >= 0
        finally:
            db.close()

    def test_model_version_recorded(self, requires_db):
        db = SessionLocal()
        try:
            mv = db.execute(text(
                "SELECT DISTINCT model_version FROM eta_estimates LIMIT 1"
            )).scalar()
            assert mv is not None
            assert "v1" in mv or "rule_based" in mv or "eta_gb" in mv
        finally:
            db.close()

    def test_base_travel_hours_positive(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM shipments LIMIT 1"
            )).scalar()
            est = predict_eta(db, sid)
            if est:
                assert est["base_travel_hours"] > 0
        finally:
            db.close()
