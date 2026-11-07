"""Phase 12 ETA ML model tests."""
from __future__ import annotations
import pytest
import os
import glob
import joblib
from sqlalchemy import text
from backend.core.database import SessionLocal, engine
from backend.core.config import get_settings

settings = get_settings()


class TestModelArtifact:
    def test_model_artifact_exists(self):
        eta_dir = os.path.join(settings.ML_MODELS_DIR, "eta")
        artifacts = glob.glob(os.path.join(eta_dir, "*.joblib"))
        assert len(artifacts) >= 1, "No ETA model artifact found — run training first"

    def test_artifact_has_required_keys(self):
        eta_dir = os.path.join(settings.ML_MODELS_DIR, "eta")
        artifacts = sorted(glob.glob(os.path.join(eta_dir, "*.joblib")), reverse=True)
        if not artifacts:
            pytest.skip("No model artifact")
        data = joblib.load(artifacts[0])
        assert "model" in data
        assert "version" in data
        assert "features" in data
        assert "metrics" in data


class TestModelVersionInDB:
    def test_eta_model_version_registered(self, requires_db):
        db = SessionLocal()
        try:
            count = db.execute(text(
                "SELECT COUNT(*) FROM model_versions WHERE model_type='ETA' AND is_active=TRUE"
            )).scalar()
            assert count >= 1, "No active ETA model version in DB"
        finally:
            db.close()

    def test_model_version_has_metrics(self, requires_db):
        db = SessionLocal()
        try:
            row = db.execute(text("""
                SELECT mae, rmse, r2 FROM model_versions
                WHERE model_type='ETA' AND is_active=TRUE LIMIT 1
            """)).mappings().fetchone()
            assert row is not None
            assert float(row["mae"]) >= 0
            assert float(row["rmse"]) >= 0
        finally:
            db.close()

    def test_feature_names_stored(self, requires_db):
        db = SessionLocal()
        try:
            row = db.execute(text("""
                SELECT feature_names FROM model_versions
                WHERE model_type='ETA' AND is_active=TRUE LIMIT 1
            """)).scalar()
            assert row is not None
            import json
            features = json.loads(row)
            assert "distance_km" in features
            assert "base_transit_hours" in features
            assert len(features) >= 10
        finally:
            db.close()


class TestETAPrediction:
    def test_predict_eta_ml_returns_dict(self, requires_db):
        from ml.eta.predict import predict_eta_ml
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None:
                pytest.skip("No gold features")
            result = predict_eta_ml(db, sid)
            assert result is not None
            assert "predicted_eta" in result
            assert "predicted_remaining_hours" in result
            assert "model_version" in result
        finally:
            db.close()

    def test_predict_persisted_in_db(self, requires_db):
        from ml.eta.predict import predict_eta_ml
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None:
                pytest.skip("No gold features")
            result = predict_eta_ml(db, sid)
            if result:
                count = db.execute(text(
                    "SELECT COUNT(*) FROM eta_estimates WHERE eta_estimate_id=:eid"
                ), {"eid": result["eta_estimate_id"]}).scalar()
                assert count == 1
        finally:
            db.close()

    def test_feature_cutoff_lte_prediction_time(self, requires_db):
        db = SessionLocal()
        try:
            violations = db.execute(text("""
                SELECT COUNT(*) FROM eta_estimates
                WHERE feature_cutoff_time > prediction_time
            """)).scalar()
            assert violations == 0, "Leakage: feature_cutoff > prediction_time"
        finally:
            db.close()
