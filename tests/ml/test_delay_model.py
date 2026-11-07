"""Phase 13 Delay ML model tests."""
from __future__ import annotations
import pytest
import os
import glob
import joblib
from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.core.config import get_settings

settings = get_settings()


class TestDelayModelArtifact:
    def test_artifact_exists(self):
        d = os.path.join(settings.ML_MODELS_DIR, "delay")
        arts = glob.glob(os.path.join(d, "*.joblib"))
        assert len(arts) >= 1, "No delay model artifact — run training first"

    def test_artifact_has_required_keys(self):
        d = os.path.join(settings.ML_MODELS_DIR, "delay")
        arts = sorted(glob.glob(os.path.join(d, "*.joblib")), reverse=True)
        if not arts: pytest.skip("No artifact")
        data = joblib.load(arts[0])
        assert "model" in data
        assert "version" in data
        assert "features" in data
        assert "metrics" in data


class TestDelayModelVersionInDB:
    def test_active_delay_version_registered(self, requires_db):
        db = SessionLocal()
        try:
            c = db.execute(text(
                "SELECT COUNT(*) FROM model_versions WHERE model_type='DELAY' AND is_active=TRUE"
            )).scalar()
            assert c >= 1, "No active DELAY model version in DB"
        finally:
            db.close()

    def test_has_classification_metrics(self, requires_db):
        db = SessionLocal()
        try:
            row = db.execute(text("""
                SELECT accuracy, precision, recall, f1, roc_auc, pr_auc
                FROM model_versions WHERE model_type='DELAY' AND is_active=TRUE LIMIT 1
            """)).mappings().fetchone()
            assert row is not None
            for k in ("accuracy","precision","recall","f1","roc_auc","pr_auc"):
                assert float(row[k]) >= 0
        finally:
            db.close()


class TestDelayPrediction:
    def test_predict_returns_dict(self, requires_db):
        from ml.delay.predict import predict_delay_ml
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = predict_delay_ml(db, sid)
            assert result is not None
            assert "delay_probability" in result
        finally:
            db.close()

    def test_delay_probability_in_range(self, requires_db):
        from ml.delay.predict import predict_delay_ml
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = predict_delay_ml(db, sid)
            if result and result.get("delay_probability") is not None:
                assert 0.0 <= result["delay_probability"] <= 1.0
        finally:
            db.close()

    def test_delay_label_binary(self, requires_db):
        from ml.delay.predict import predict_delay_ml
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = predict_delay_ml(db, sid)
            if result and "delay_label" in result:
                assert result["delay_label"] in (0, 1)
        finally:
            db.close()
