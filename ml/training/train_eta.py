"""Train ETA regression models and evaluate.

Trains three models on gold_shipment_features:
  - Linear Regression
  - Random Forest
  - Gradient Boosting

Uses a time-aware split (train on older shipments, validate on newer).
Saves the best model via joblib and registers a ModelVersion row.

Target: remaining_delivery_hours (regression)
Metrics: MAE, RMSE, R²

Usage:
  python -m ml.training.train_eta
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text

from backend.core.config import get_settings
from backend.core.database import SessionLocal, engine
from backend.core.logging import configure_logging, get_logger
from data_engineering.generator.ids import eta_id

settings = get_settings()
configure_logging(level="INFO", debug=False)
log = get_logger("ml.training.train_eta")

MODEL_VERSION = f"eta_gb_v1_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
ARTIFACT_DIR = os.path.join(settings.ML_MODELS_DIR, "eta")
os.makedirs(ARTIFACT_DIR, exist_ok=True)

FEATURE_COLS = [
    "distance_km", "weight_kg", "base_transit_hours",
    "base_delay_factor", "max_weather_delay_factor",
    "max_facility_utilization_pct", "event_count",
    "late_event_count", "day_of_week", "hour_of_day",
    "service_level_encoded",
]
TARGET_COL = "remaining_delivery_hours"


def _load_data() -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(text(
            "SELECT * FROM gold_shipment_features "
            "WHERE remaining_delivery_hours IS NOT NULL "
            "  AND remaining_delivery_hours >= 0"
        ), conn)
    log.info("loaded %d rows from gold_shipment_features", len(df))
    return df


def _time_aware_split(df: pd.DataFrame, val_frac: float = 0.2):
    """Split by row order (proxy for time) to prevent leakage."""
    df = df.sort_values("shipment_id").reset_index(drop=True)
    split_idx = int(len(df) * (1 - val_frac))
    return df.iloc[:split_idx], df.iloc[split_idx:]


def _train_models(X_train, y_train):
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

    models = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=100, random_state=settings.RANDOM_SEED, n_jobs=-1),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=settings.RANDOM_SEED),
    }
    trained = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        trained[name] = model
        log.info("trained %s", name)
    return trained


def _evaluate(model, X_val, y_val) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    preds = model.predict(X_val)
    return {
        "mae": round(float(mean_absolute_error(y_val, preds)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_val, preds))), 4),
        "r2": round(float(r2_score(y_val, preds)), 6),
    }


def _save_best_model(name, model, metrics, feature_names) -> str:
    artifact_path = os.path.join(ARTIFACT_DIR, f"{MODEL_VERSION}.joblib")
    joblib.dump({
        "model": model,
        "model_name": name,
        "version": MODEL_VERSION,
        "features": feature_names,
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }, artifact_path)
    log.info("saved model artifact: %s", artifact_path)
    return artifact_path


def _register_model_version(db, name, metrics, artifact_path):
    db.execute(text("""
        INSERT INTO model_versions (
            model_version_id, model_type, version_tag, algorithm,
            training_seed, feature_names,
            mae, rmse, r2,
            artifact_path, is_active, trained_at,
            created_at, updated_at
        ) VALUES (
            :vid, 'ETA', :tag, :algo,
            :seed, :features,
            :mae, :rmse, :r2,
            :path, TRUE, :now,
            :now, :now
        ) ON CONFLICT (model_version_id) DO NOTHING
    """), {
        "vid": MODEL_VERSION,
        "tag": MODEL_VERSION.split("_")[-1],
        "algo": name,
        "seed": settings.RANDOM_SEED,
        "features": json.dumps(FEATURE_COLS),
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "r2": metrics["r2"],
        "path": artifact_path,
        "now": datetime.now(timezone.utc),
    })
    # Deactivate previous versions
    db.execute(text("""
        UPDATE model_versions SET is_active=FALSE
        WHERE model_type='ETA' AND model_version_id != :vid
    """), {"vid": MODEL_VERSION})
    db.commit()
    log.info("registered model version: %s", MODEL_VERSION)


def train_and_evaluate() -> dict:
    df = _load_data()
    if len(df) < 10:
        log.error("not enough training data (%d rows). Run ETL pipeline first.", len(df))
        return {"error": "insufficient data", "rows": len(df)}

    # Ensure features exist
    for col in FEATURE_COLS:
        if col not in df.columns:
            log.error("missing feature column: %s", col)
            return {"error": f"missing column {col}"}

    df_clean = df.dropna(subset=FEATURE_COLS + [TARGET_COL])
    X = df_clean[FEATURE_COLS]
    y = df_clean[TARGET_COL]

    # Time-aware split
    train_df, val_df = _time_aware_split(df_clean)
    X_train = train_df[FEATURE_COLS]
    y_train = train_df[TARGET_COL]
    X_val = val_df[FEATURE_COLS]
    y_val = val_df[TARGET_COL]

    log.info("train=%d val=%d", len(X_train), len(X_val))

    # Train all models
    models = _train_models(X_train, y_train)

    # Evaluate
    results = {}
    best_name = None
    best_rmse = float("inf")
    for name, model in models.items():
        metrics = _evaluate(model, X_val, y_val)
        results[name] = metrics
        log.info("%-25s MAE=%.2f RMSE=%.2f R²=%.4f", name, metrics["mae"], metrics["rmse"], metrics["r2"])
        if metrics["rmse"] < best_rmse:
            best_rmse = metrics["rmse"]
            best_name = name

    # Save best model
    best_model = models[best_name]
    best_metrics = results[best_name]
    artifact_path = _save_best_model(best_name, best_model, best_metrics, FEATURE_COLS)

    # Register in DB
    db = SessionLocal()
    try:
        _register_model_version(db, best_name, best_metrics, artifact_path)
    finally:
        db.close()

    report = {
        "model_version": MODEL_VERSION,
        "best_model": best_name,
        "best_metrics": best_metrics,
        "all_results": results,
        "train_size": len(X_train),
        "val_size": len(X_val),
        "feature_count": len(FEATURE_COLS),
        "artifact_path": artifact_path,
    }
    log.info("training complete. best=%s mae=%.2f rmse=%.2f r2=%.4f",
             best_name, best_metrics["mae"], best_metrics["rmse"], best_metrics["r2"])
    return report


if __name__ == "__main__":
    report = train_and_evaluate()
    print("\n" + "=" * 60)
    print("  YottaFlex ETA Model Training Complete")
    print("=" * 60)
    print(f"  Model version : {report.get('model_version','—')}")
    print(f"  Best model    : {report.get('best_model','—')}")
    if "best_metrics" in report:
        m = report["best_metrics"]
        print(f"  MAE           : {m['mae']}")
        print(f"  RMSE          : {m['rmse']}")
        print(f"  R²            : {m['r2']}")
    print(f"  Train / Val   : {report.get('train_size','—')} / {report.get('val_size','—')}")
    print("=" * 60)
