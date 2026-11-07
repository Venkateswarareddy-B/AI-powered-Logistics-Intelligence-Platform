"""Train delay classification models and evaluate.

Trains three classifiers on gold_shipment_features:
  - Logistic Regression
  - Random Forest
  - Gradient Boosting

Target: delay_label (0=on_time, 1=delayed)
Metrics: Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC

Time-aware split (train on older, validate on newer).
Saves best model via joblib and registers ModelVersion.

Usage:
  python -m ml.training.train_delay
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

settings = get_settings()
configure_logging(level="INFO", debug=False)
log = get_logger("ml.training.train_delay")

MODEL_VERSION = f"delay_gb_v1_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
ARTIFACT_DIR = os.path.join(settings.ML_MODELS_DIR, "delay")
os.makedirs(ARTIFACT_DIR, exist_ok=True)

FEATURE_COLS = [
    "distance_km", "weight_kg", "base_transit_hours",
    "base_delay_factor", "max_weather_delay_factor",
    "max_facility_utilization_pct", "event_count",
    "late_event_count", "day_of_week", "hour_of_day",
    "service_level_encoded",
]
TARGET_COL = "delay_label"


def _load_data() -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(text(
            "SELECT * FROM gold_shipment_features "
            "WHERE delay_label IS NOT NULL"
        ), conn)
    log.info("loaded %d rows from gold_shipment_features", len(df))
    return df


def _time_aware_split(df: pd.DataFrame, val_frac: float = 0.2):
    df = df.sort_values("shipment_id").reset_index(drop=True)
    split_idx = int(len(df) * (1 - val_frac))
    return df.iloc[:split_idx], df.iloc[split_idx:]


def _train_models(X_train, y_train):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

    models = {
        "logistic_regression": LogisticRegression(max_iter=500, random_state=settings.RANDOM_SEED),
        "random_forest": RandomForestClassifier(n_estimators=100, random_state=settings.RANDOM_SEED, n_jobs=-1),
        "gradient_boosting": GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=settings.RANDOM_SEED),
    }
    trained = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        trained[name] = model
        log.info("trained %s", name)
    return trained


def _evaluate(model, X_val, y_val) -> dict:
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score,
        f1_score, roc_auc_score, average_precision_score,
    )
    preds = model.predict(X_val)
    probs = model.predict_proba(X_val)[:, 1] if hasattr(model, "predict_proba") else preds
    metrics = {
        "accuracy": round(float(accuracy_score(y_val, preds)), 6),
        "precision": round(float(precision_score(y_val, preds, zero_division=0)), 6),
        "recall": round(float(recall_score(y_val, preds, zero_division=0)), 6),
        "f1": round(float(f1_score(y_val, preds, zero_division=0)), 6),
    }
    try:
        metrics["roc_auc"] = round(float(roc_auc_score(y_val, probs)), 6)
    except Exception:
        metrics["roc_auc"] = 0.0
    try:
        metrics["pr_auc"] = round(float(average_precision_score(y_val, probs)), 6)
    except Exception:
        metrics["pr_auc"] = 0.0
    return metrics


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
            training_seed, training_dataset_description, feature_names,
            accuracy, precision, recall, f1, roc_auc, pr_auc,
            artifact_path, is_active, trained_at,
            created_at, updated_at
        ) VALUES (
            :vid, 'DELAY', :tag, :algo,
            :seed, :ds, :features,
            :acc, :prec, :rec, :f1, :roc, :pr,
            :path, TRUE, :now,
            :now, :now
        ) ON CONFLICT (model_version_id) DO NOTHING
    """), {
        "vid": MODEL_VERSION,
        "tag": MODEL_VERSION.split("_")[-1],
        "algo": name,
        "seed": settings.RANDOM_SEED,
        "ds": f"gold_shipment_features ({len(FEATURE_COLS)} features)",
        "features": json.dumps(FEATURE_COLS),
        "acc": metrics["accuracy"],
        "prec": metrics["precision"],
        "rec": metrics["recall"],
        "f1": metrics["f1"],
        "roc": metrics["roc_auc"],
        "pr": metrics["pr_auc"],
        "path": artifact_path,
        "now": datetime.now(timezone.utc),
    })
    db.execute(text("""
        UPDATE model_versions SET is_active=FALSE
        WHERE model_type='DELAY' AND model_version_id != :vid
    """), {"vid": MODEL_VERSION})
    db.commit()
    log.info("registered model version: %s", MODEL_VERSION)


def train_and_evaluate() -> dict:
    df = _load_data()
    if len(df) < 10:
        log.error("not enough training data (%d rows). Run ETL pipeline first.", len(df))
        return {"error": "insufficient data", "rows": len(df)}

    for col in FEATURE_COLS:
        if col not in df.columns:
            return {"error": f"missing column {col}"}

    df_clean = df.dropna(subset=FEATURE_COLS + [TARGET_COL])
    X = df_clean[FEATURE_COLS]
    y = df_clean[TARGET_COL].astype(int)

    train_df, val_df = _time_aware_split(df_clean)
    X_train = train_df[FEATURE_COLS]
    y_train = train_df[TARGET_COL].astype(int)
    X_val = val_df[FEATURE_COLS]
    y_val = val_df[TARGET_COL].astype(int)

    log.info("train=%d val=%d pos_rate=%.2f", len(X_train), len(X_val), y_train.mean())

    models = _train_models(X_train, y_train)

    results = {}
    best_name = None
    best_f1 = -1.0
    for name, model in models.items():
        metrics = _evaluate(model, X_val, y_val)
        results[name] = metrics
        log.info("%-25s acc=%.2f prec=%.2f rec=%.2f f1=%.2f auc=%.2f pr=%.2f",
                 name, metrics["accuracy"], metrics["precision"], metrics["recall"],
                 metrics["f1"], metrics["roc_auc"], metrics["pr_auc"])
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_name = name

    best_model = models[best_name]
    best_metrics = results[best_name]
    artifact_path = _save_best_model(best_name, best_model, best_metrics, FEATURE_COLS)

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
        "positive_rate": round(float(y_train.mean()), 4),
        "feature_count": len(FEATURE_COLS),
        "artifact_path": artifact_path,
    }
    log.info("training complete. best=%s f1=%.4f", best_name, best_f1)
    return report


if __name__ == "__main__":
    report = train_and_evaluate()
    print("\n" + "=" * 60)
    print("  YottaFlex Delay Model Training Complete")
    print("=" * 60)
    print(f"  Model version : {report.get('model_version','—')}")
    print(f"  Best model    : {report.get('best_model','—')}")
    if "best_metrics" in report:
        m = report["best_metrics"]
        print(f"  Accuracy      : {m['accuracy']}")
        print(f"  Precision     : {m['precision']}")
        print(f"  Recall        : {m['recall']}")
        print(f"  F1            : {m['f1']}")
        print(f"  ROC-AUC       : {m['roc_auc']}")
        print(f"  PR-AUC        : {m['pr_auc']}")
    print(f"  Train / Val   : {report.get('train_size','—')} / {report.get('val_size','—')}")
    print(f"  Positive rate : {report.get('positive_rate','—')}")
    print("=" * 60)
