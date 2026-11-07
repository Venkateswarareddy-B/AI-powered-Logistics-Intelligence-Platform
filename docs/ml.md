# YottaFlex — ML Architecture

## Overview

Two ML models trained on `gold_shipment_features`:
- **ETA Model**: Regression → predicts `remaining_delivery_hours`
- **Delay Model**: Classification → predicts `delay_label` (0=on_time, 1=delayed)

## Feature Engineering

Features are computed in the Gold ETL layer from Silver-cleaned data:

| Feature | Source | Description |
|---------|--------|-------------|
| `distance_km` | routes.distance_km | Route distance |
| `weight_kg` | shipments.weight_kg | Shipment weight |
| `base_transit_hours` | routes.base_transit_hours | Planned transit time |
| `base_delay_factor` | carriers.base_delay_factor | Carrier delay multiplier |
| `max_weather_delay_factor` | weather_events.delay_factor | Max weather impact during shipment window |
| `max_facility_utilization_pct` | facility_queues.utilization_pct | Max queue utilization at origin/dest |
| `event_count` | tracking_events COUNT | Total tracking events |
| `late_event_count` | tracking_events WHERE lag > 2h | Late-arriving events |
| `day_of_week` | EXTRACT(DOW FROM planned_ship_time) | Day of week (0-6) |
| `hour_of_day` | EXTRACT(HOUR FROM planned_ship_time) | Hour of day (0-23) |
| `service_level_encoded` | service_level_id mapping | STANDARD=0, EXPRESS=1, SAME_DAY=2, PRIORITY=3 |

**Ground truth labels are excluded from features.**

## Time-Aware Split

Train on older shipments, validate on newer ones (prevents temporal leakage):
```python
df = df.sort_values("shipment_id")
split_idx = int(len(df) * 0.8)
train, val = df.iloc[:split_idx], df.iloc[split_idx:]
```

## Models

### ETA Regression
- Linear Regression (baseline)
- Random Forest (100 trees)
- Gradient Boosting (100 estimators, depth 5)
- Best selected by lowest RMSE

### Delay Classification
- Logistic Regression (baseline)
- Random Forest (100 trees)
- Gradient Boosting (100 estimators, depth 5)
- Best selected by highest F1

## Evaluation Metrics

| Model | Metrics |
|-------|---------|
| ETA | MAE, RMSE, R² |
| Delay | Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC |

## Model Registry

All trained models are registered in `model_versions` with:
- `model_version_id`, `algorithm`, `feature_names`
- All evaluation metrics
- `artifact_path` (Joblib file location)
- `is_active` flag (only one active per type)

## Inference

```python
from ml.eta.predict import predict_eta_ml
result = predict_eta_ml(db, "SHP-2026-000001")

from ml.delay.predict import predict_delay_ml
result = predict_delay_ml(db, "SHP-2026-000001")
```

Falls back to rule-based engine if no model is trained.

## Reproducibility

- Fixed seed: `RANDOM_SEED = 20261022`
- Feature definitions stored in `model_versions.feature_names`
- Training dataset described in `model_versions.training_dataset_description`
