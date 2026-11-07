"""Explainable AI service using SHAP.

Provides per-prediction explanations derived from the actual SHAP method —
never manually fabricated. Falls back to a rule-based explanation if SHAP
cannot run (e.g. model not loaded, incompatible model type).

Each explanation is persisted as a PredictionExplanation row with:
  - shap_values_json: [{feature, shap_value, display_impact_pct}, ...]
  - base_value: the model's expected value
  - prediction_value: the actual prediction
  - explanation_method: SHAP_TREE | SHAP_LINEAR | RULE_BASED

Usage:
  from backend.services.explainability import explain_prediction
  result = explain_prediction(db, shipment_id, prediction_type="DELAY")
"""

from __future__ import annotations

import json
import logging
import os
import glob
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import SessionLocal

settings = get_settings()
log = logging.getLogger("backend.services.explainability")

FEATURE_COLS = [
    "distance_km", "weight_kg", "base_transit_hours",
    "base_delay_factor", "max_weather_delay_factor",
    "max_facility_utilization_pct", "event_count",
    "late_event_count", "day_of_week", "hour_of_day",
    "service_level_encoded",
]


def _load_model(model_type: str) -> dict | None:
    """Load the latest model artifact for a given type (ETA or DELAY)."""
    model_dir = os.path.join(settings.ML_MODELS_DIR, model_type.lower())
    artifacts = sorted(glob.glob(os.path.join(model_dir, "*.joblib")), reverse=True)
    if not artifacts:
        return None
    return joblib.load(artifacts[0])


def _get_features(db: Session, shipment_id: str) -> dict | None:
    row = db.execute(text("""
        SELECT g.* FROM gold_shipment_features g
        WHERE g.shipment_id = :sid
    """), {"sid": shipment_id}).mappings().fetchone()
    return dict(row) if row else None


def _compute_shap(artifact: dict, X: pd.DataFrame) -> dict | None:
    """Try to compute SHAP values for the loaded model. Returns None on failure."""
    model = artifact["model"]
    model_name = artifact.get("model_name", "")

    try:
        import shap

        # Tree-based models (Random Forest, Gradient Boosting)
        if hasattr(model, "estimators_") or "GradientBoosting" in type(model).__name__ or "RandomForest" in type(model).__name__:
            explainer = shap.TreeExplainer(model)
            shap_vals = explainer.shap_values(X)
            # For classifiers, shap_values may be a list [class0, class1]
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[-1]  # positive class
            base_val = float(explainer.expected_value[-1] if isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value)
            method = "SHAP_TREE"
        # Linear models
        elif "Linear" in type(model).__name__ or "Logistic" in type(model).__name__:
            explainer = shap.LinearExplainer(model, X)
            shap_vals = explainer.shap_values(X)
            base_val = float(explainer.expected_value)
            method = "SHAP_LINEAR"
        else:
            return None

        shap_arr = np.array(shap_vals)
        if shap_arr.ndim > 1:
            shap_arr = shap_arr[0]  # first (and only) sample

        return {
            "shap_values": shap_arr.tolist(),
            "base_value": base_val,
            "method": method,
        }
    except Exception as exc:
        log.warning("SHAP computation failed: %s", exc)
        return None


def _rule_based_explanation(features: dict) -> dict:
    """Fallback explanation when SHAP is unavailable.

    Derives impact percentages from the feature values themselves using
    documented business rules — clearly labelled as rule-based, not SHAP.
    """
    factors = []

    weather_factor = float(features.get("max_weather_delay_factor", 1.0))
    if weather_factor > 1.0:
        factors.append({"feature": "max_weather_delay_factor",
                        "impact": round((weather_factor - 1.0) * 100, 2)})

    util = float(features.get("max_facility_utilization_pct", 0))
    if util > 60:
        factors.append({"feature": "max_facility_utilization_pct",
                        "impact": round((util - 60) * 0.5, 2)})

    carrier_factor = float(features.get("base_delay_factor", 1.0))
    if carrier_factor > 1.0:
        factors.append({"feature": "base_delay_factor",
                        "impact": round((carrier_factor - 1.0) * 100, 2)})

    late_events = int(features.get("late_event_count", 0))
    if late_events > 0:
        factors.append({"feature": "late_event_count",
                        "impact": round(late_events * 5, 2)})

    base_transit = float(features.get("base_transit_hours", 0))
    if base_transit > 20:
        factors.append({"feature": "base_transit_hours",
                        "impact": round(base_transit * 0.5, 2)})

    # Normalize to percentages
    total = sum(abs(f["impact"]) for f in factors) or 1.0
    for f in factors:
        f["display_impact_pct"] = round(abs(f["impact"]) / total * 100, 1)

    factors.sort(key=lambda x: x["display_impact_pct"], reverse=True)

    return {
        "shap_values": factors,
        "base_value": 0.0,
        "method": "RULE_BASED",
    }


def explain_prediction(
    db: Session,
    shipment_id: str,
    prediction_type: str = "DELAY",
) -> dict | None:
    """Generate and persist a SHAP-based explanation for a shipment prediction.

    Args:
        db: Active SQLAlchemy session.
        shipment_id: The shipment to explain.
        prediction_type: "ETA" or "DELAY".

    Returns:
        Explanation dict with shap_values_json, base_value, prediction_value,
        explanation_method, and per-factor display impacts.
    """
    features = _get_features(db, shipment_id)
    if features is None:
        return {"shipment_id": shipment_id,
                "message": "No ML features available for this shipment"}

    artifact = _load_model(prediction_type)
    if artifact is None:
        return {"shipment_id": shipment_id,
                "message": f"No {prediction_type} model trained yet"}

    X = pd.DataFrame([{col: features.get(col, 0) for col in FEATURE_COLS}])
    model = artifact["model"]

    # Get the prediction value
    if prediction_type == "DELAY":
        pred_val = float(model.predict_proba(X)[0, 1]) if hasattr(model, "predict_proba") else float(model.predict(X)[0])
    else:
        pred_val = float(model.predict(X)[0])

    # Try SHAP
    shap_result = _compute_shap(artifact, X)

    if shap_result is not None:
        # Build display impacts from SHAP values
        shap_vals = shap_result["shap_values"]
        factors = []
        for i, fname in enumerate(FEATURE_COLS):
            sv = float(shap_vals[i]) if i < len(shap_vals) else 0.0
            factors.append({
                "feature": fname,
                "shap_value": round(sv, 6),
            })
        # Normalize to display percentages
        total_abs = sum(abs(f["shap_value"]) for f in factors) or 1.0
        for f in factors:
            f["display_impact_pct"] = round(abs(f["shap_value"]) / total_abs * 100, 1)
        factors.sort(key=lambda x: x["display_impact_pct"], reverse=True)
        method = shap_result["method"]
        base_val = shap_result["base_value"]
    else:
        # Fallback to rule-based
        rb = _rule_based_explanation(features)
        factors = rb["shap_values"]
        method = rb["method"]
        base_val = rb["base_value"]

    # Build the display format from the spec example:
    # "Heavy rain: +28 percentage points"
    top_factors = []
    for f in factors[:5]:
        sign = "+" if f.get("shap_value", f.get("impact", 0)) >= 0 else "-"
        top_factors.append({
            "feature": f["feature"],
            "display": f"{sign}{f['display_impact_pct']:.0f} percentage points",
            "impact_pct": f["display_impact_pct"],
        })

    explanation_id = f"EXP-{shipment_id}-{prediction_type}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # Get latest ETA estimate for this shipment (for FK if ETA type)
    eta_estimate_id = None
    if prediction_type == "ETA":
        eta_row = db.execute(text("""
            SELECT eta_estimate_id FROM eta_estimates
            WHERE shipment_id=:sid ORDER BY prediction_time DESC LIMIT 1
        """), {"sid": shipment_id}).scalar()
        eta_estimate_id = eta_row

    model_version = artifact.get("version", "unknown")

    # Persist
    db.execute(text("""
        INSERT INTO prediction_explanations (
            explanation_id, eta_estimate_id, shipment_id, model_version_id,
            prediction_type, shap_values_json, base_value, prediction_value,
            explanation_method, created_at
        ) VALUES (
            :eid, :eta_id, :sid, NULL,
            :ptype, :shap_json, :base_val, :pred_val,
            :method, :now
        ) ON CONFLICT (explanation_id) DO NOTHING
    """), {
        "eid": explanation_id,
        "eta_id": eta_estimate_id,
        "sid": shipment_id,
        "ptype": prediction_type,
        "shap_json": json.dumps(factors, default=str),
        "base_val": round(base_val, 4),
        "pred_val": round(pred_val, 4),
        "method": method,
        "now": datetime.now(timezone.utc),
    })
    db.commit()

    return {
        "explanation_id": explanation_id,
        "shipment_id": shipment_id,
        "prediction_type": prediction_type,
        "explanation_method": method,
        "base_value": round(base_val, 4),
        "prediction_value": round(pred_val, 4),
        "model_version": model_version,
        "top_factors": top_factors,
        "all_factors": factors,
    }
