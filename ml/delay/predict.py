"""Delay model inference — load saved model and predict delay probability."""

from __future__ import annotations

import glob
import logging
import os

import joblib
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings

settings = get_settings()
log = logging.getLogger("ml.delay.predict")

FEATURE_COLS = [
    "distance_km", "weight_kg", "base_transit_hours",
    "base_delay_factor", "max_weather_delay_factor",
    "max_facility_utilization_pct", "event_count",
    "late_event_count", "day_of_week", "hour_of_day",
    "service_level_encoded",
]


def _load_latest_model() -> dict | None:
    delay_dir = os.path.join(settings.ML_MODELS_DIR, "delay")
    artifacts = sorted(glob.glob(os.path.join(delay_dir, "*.joblib")), reverse=True)
    if not artifacts:
        return None
    return joblib.load(artifacts[0])


def predict_delay_ml(db: Session, shipment_id: str) -> dict | None:
    """Predict delay probability for a shipment.

    Returns dict with delay_probability (0-1), predicted label, and model info.
    Falls back to rule-based delay probability if no model is available.
    """
    artifact = _load_latest_model()
    if artifact is None:
        log.warning("no ML delay model trained")
        return {"shipment_id": shipment_id, "delay_probability": None,
                "message": "No delay model trained yet. Run: python -m ml.training.train_delay"}

    row = db.execute(text("""
        SELECT g.* FROM gold_shipment_features g
        WHERE g.shipment_id = :sid
    """), {"sid": shipment_id}).mappings().fetchone()

    if row is None:
        log.warning("no gold features for %s", shipment_id)
        return {"shipment_id": shipment_id, "delay_probability": None,
                "message": "No ML features available for this shipment"}

    features = dict(row)
    X = pd.DataFrame([{col: features.get(col, 0) for col in FEATURE_COLS}])

    model = artifact["model"]
    prob = float(model.predict_proba(X)[0, 1]) if hasattr(model, "predict_proba") else float(model.predict(X)[0])
    label = int(prob > 0.5)

    return {
        "shipment_id": shipment_id,
        "delay_probability": round(prob, 4),
        "delay_label": label,
        "model_version": artifact.get("version", "unknown"),
        "model_name": artifact.get("model_name", "unknown"),
    }
