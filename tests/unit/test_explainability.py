"""Phase 14 Explainable AI tests."""
from __future__ import annotations
import pytest
from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.services.explainability import explain_prediction


class TestExplainPrediction:
    def test_explain_delay_returns_dict(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = explain_prediction(db, sid, "DELAY")
            assert result is not None
            assert "explanation_method" in result
            assert result["explanation_method"] in ("SHAP_TREE", "SHAP_LINEAR", "RULE_BASED")
        finally:
            db.close()

    def test_explain_eta_returns_dict(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = explain_prediction(db, sid, "ETA")
            assert result is not None
            assert "explanation_method" in result
        finally:
            db.close()

    def test_top_factors_populated(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = explain_prediction(db, sid, "DELAY")
            assert "top_factors" in result
            assert len(result["top_factors"]) > 0
            # Each factor should have a display string
            for f in result["top_factors"]:
                assert "feature" in f
                assert "display" in f
                assert "percentage points" in f["display"]
        finally:
            db.close()

    def test_explanation_persisted_in_db(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = explain_prediction(db, sid, "DELAY")
            if result and "explanation_id" in result:
                count = db.execute(text(
                    "SELECT COUNT(*) FROM prediction_explanations WHERE explanation_id=:eid"
                ), {"eid": result["explanation_id"]}).scalar()
                assert count == 1
        finally:
            db.close()

    def test_factors_sorted_by_impact(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            result = explain_prediction(db, sid, "DELAY")
            impacts = [f["impact_pct"] for f in result["top_factors"]]
            assert impacts == sorted(impacts, reverse=True)
        finally:
            db.close()

    def test_no_features_returns_message(self, requires_db):
        db = SessionLocal()
        try:
            result = explain_prediction(db, "SHP-FAKE-999999", "DELAY")
            assert "message" in result
        finally:
            db.close()

    def test_shap_values_stored_as_json(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text(
                "SELECT shipment_id FROM gold_shipment_features LIMIT 1"
            )).scalar()
            if sid is None: pytest.skip("No gold features")
            explain_prediction(db, sid, "DELAY")
            row = db.execute(text("""
                SELECT shap_values_json FROM prediction_explanations
                WHERE shipment_id=:sid ORDER BY created_at DESC LIMIT 1
            """), {"sid": sid}).scalar()
            if row:
                import json
                parsed = json.loads(row)
                assert isinstance(parsed, list)
                assert len(parsed) > 0
        finally:
            db.close()
