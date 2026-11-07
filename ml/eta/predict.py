"""ETA model inference — load saved model and predict for a shipment."""

from __future__ import annotations

import glob
import logging
import os
from datetime import datetime, timezone

import joblib
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import SessionLocal
from data_engineering.generator.ids import eta_id

settings = get_settings()
log = logging.getLogger("ml.eta.predict")

FEATURE_COLS = [
    "distance_km", "weight_kg", "base_transit_hours",
    "base_delay_factor", "max_weather_delay_factor",
    "max_facility_utilization_pct", "event_count",
    "late_event_count", "day_of_week", "hour_of_day",
    "service_level_encoded",
]


def _load_latest_model() -> dict | None:
    """Load the most recent model artifact from disk."""
    eta_dir = os.path.join(settings.ML_MODELS_DIR, "eta")
    artifacts = sorted(glob.glob(os.path.join(eta_dir, "*.joblib")), reverse=True)
    if not artifacts:
        return None
    return joblib.load(artifacts[0])


def _get_features(db: Session, shipment_id: str) -> dict | None:
    row = db.execute(text("""
        SELECT g.* FROM gold_shipment_features g
        WHERE g.shipment_id = :sid
    """), {"sid": shipment_id}).mappings().fetchone()
    return dict(row) if row else None


def predict_eta_ml(db: Session, shipment_id: str) -> dict | None:
    """Predict ETA using the trained ML model.

    Falls back to the rule-based engine if no model is available.
    Returns None if the shipment isn't found.
    """
    artifact = _load_latest_model()
    if artifact is None:
        log.warning("no ML model trained; falling back to rule-based engine")
        from backend.services.eta_engine import predict_eta as _rule_predict
        return _rule_predict(db, shipment_id)

    features = _get_features(db, shipment_id)
    if features is None:
        log.warning("no gold features for %s; falling back to rule-based", shipment_id)
        from backend.services.eta_engine import predict_eta as _rule_predict
        return _rule_predict(db, shipment_id)

    # Build feature vector
    X = pd.DataFrame([{col: features.get(col, 0) for col in FEATURE_COLS}])
    prediction = artifact["model"].predict(X)[0]

    model_version = artifact.get("version", "unknown")
    model_name = artifact.get("model_name", "unknown")

    # Predicted ETA = last event time + predicted remaining hours
    # Fall back to planned_ship_time + base_transit if no events
    planned_ship = db.execute(text(
        "SELECT planned_ship_time FROM shipments WHERE shipment_id=:sid"
    ), {"sid": shipment_id}).scalar()
    predicted_eta = planned_ship + pd.Timedelta(hours=float(prediction))

    prediction_time = datetime.now(timezone.utc)
    feature_cutoff = prediction_time
    eid = eta_id(shipment_id, prediction_time)

    # Persist
    db.execute(text("""
        INSERT INTO eta_estimates (
            eta_estimate_id, shipment_id,
            prediction_time, feature_cutoff_time,
            predicted_eta, predicted_remaining_hours,
            delay_probability, model_version, model_type,
            base_travel_hours,
            is_demo, created_at
        ) VALUES (
            :eid, :sid,
            :pt, :fct,
            :peta, :prh,
            NULL, :mv, 'GRADIENT_BOOSTING',
            :bh,
            TRUE, :now
        ) ON CONFLICT (eta_estimate_id) DO NOTHING
    """), {
        "eid": eid, "sid": shipment_id,
        "pt": prediction_time, "fct": feature_cutoff,
        "peta": predicted_eta, "prh": round(float(prediction), 4),
        "mv": model_version,
        "bh": float(features.get("base_transit_hours", 0)),
        "now": prediction_time,
    })
    db.commit()

    return {
        "eta_estimate_id": eid,
        "shipment_id": shipment_id,
        "prediction_time": prediction_time.isoformat(),
        "feature_cutoff_time": feature_cutoff.isoformat(),
        "predicted_eta": predicted_eta.isoformat(),
        "predicted_remaining_hours": round(float(prediction), 2),
        "delay_probability": None,
        "model_version": model_version,
        "model_type": "GRADIENT_BOOSTING",
        "model_name": model_name,
        "base_travel_hours": float(features.get("base_transit_hours", 0)),
    }
