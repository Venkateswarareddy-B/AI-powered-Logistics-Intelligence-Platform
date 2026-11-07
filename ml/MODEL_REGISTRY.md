# ML Models — YottaFlex

## ETA Prediction (Regression)
- Target: remaining_delivery_hours
- Algorithms: Linear Regression, Random Forest, Gradient Boosting
- Best selected by lowest RMSE on time-aware validation split (80/20)
- Artifact: ml/models/eta/<version>.joblib

## Delay Classification (Binary)
- Target: delay_label (0=on_time, 1=delayed)
- Algorithms: Logistic Regression, Random Forest, Gradient Boosting
- Best selected by highest F1 score
- Artifact: ml/models/delay/<version>.joblib

## Features (Gold layer — gold_shipment_features)
distance_km, weight_kg, base_transit_hours, base_delay_factor,
max_weather_delay_factor, max_facility_utilization_pct,
event_count, late_event_count, day_of_week, hour_of_day,
service_level_encoded (STANDARD=0 EXPRESS=1 SAME_DAY=2 PRIORITY=3)

## Leakage Prevention
- Time-aware split: train on older shipments, validate on newer
- feature_cutoff_time <= prediction_time enforced by DB constraint
- ground_truth_label excluded from all feature columns

## Reproducibility
- Fixed seed: 20261022
- Feature names stored in model_versions.feature_names (JSON)
- Training dataset description recorded per version
