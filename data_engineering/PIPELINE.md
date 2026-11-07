# Data Engineering Pipeline — YottaFlex

## Stages
Bronze → Silver → Gold

### Bronze
Raw data copy with audit metadata:
- bronze_ingested_at, bronze_run_id, bronze_source, bronze_is_anomaly
- Tables: bronze_tracking_events, bronze_shipment_snapshot

### Silver
Cleaned and enriched:
- ingestion_lag_hours calculated (event_time vs ingestion_time)
- is_anomaly flag (future events, time confusion, bronze-flagged)
- is_usable_for_ml flag (clean, non-duplicate, valid timestamps)
- Tables: silver_tracking_events, silver_shipments

### Gold
Business-ready aggregates:
- Carrier KPIs (on_time_rate, late_scan_rate, carrier_score formula)
- Facility KPIs (utilization, processing time, delay contribution)
- ML feature rows (one per usable delivered shipment)
- Table: gold_shipment_features (delay_label, remaining_delivery_hours)

## Anomaly Types (10 labelled)
INGESTION_TIME_CONFUSION, IMPOSSIBLE_ROUTE_ORDER, FUTURE_EVENT_LEAKAGE,
DELIVERED_STILL_IN_TRANSIT, DUPLICATE_TRACKING_EVENT, DELAYED_SCAN,
ROUTE_CHANGE_ANOMALY, MISSING_TRACKING_EVENT, FACILITY_OVERLOAD,
SEVERE_WEATHER_DISRUPTION

## Generator
python -m data_engineering.generator --shipments 100 --seed 20261022

## Validation
python -m data_engineering.validation
