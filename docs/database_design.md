# YottaFlex — Database Design

## ER Diagram

```mermaid
erDiagram
    roles ||--o{ users : "has"
    carriers ||--o{ shipments : "carries"
    service_levels ||--o{ shipments : "defines SLA"
    routes ||--o{ shipments : "uses"
    facilities ||--o{ routes : "origin"
    facilities ||--o{ routes : "destination"
    facilities ||--o{ facility_queues : "has"
    facilities ||--o{ shipments : "origin"
    facilities ||--o{ shipments : "destination"
    shipments ||--o{ shipment_legs : "has legs"
    shipments ||--o{ tracking_events : "has events"
    shipments ||--o{ eta_estimates : "has predictions"
    shipments ||--o{ delay_reasons : "has delays"
    shipments ||--o{ route_changes : "may change"
    shipments ||--o{ alerts : "may trigger"
    shipments ||--o{ human_approvals : "may require"
    carriers ||--o{ carrier_performance : "has KPIs"
    facilities ||--o{ facility_performance : "has KPIs"
    alerts ||--o{ notifications : "creates"
    users ||--o{ notifications : "receives"
    users ||--o{ audit_logs : "performs"
    shipments ||--o{ prediction_explanations : "explained by"
    model_versions ||--o{ prediction_explanations : "produces"
    agent_decisions ||--o{ human_approvals : "may require"
    rag_documents ||--o{ rag_ingestion_jobs : "has jobs"
    weather_events }o--|| facilities : "near"

    roles {
        string role_id PK
        string role_name
        boolean is_active
    }
    users {
        string user_id PK
        string username UK
        string hashed_password
        string role_id FK
        boolean is_demo
    }
    shipments {
        string shipment_id PK
        string carrier_id FK
        string service_level_id FK
        string route_id FK
        string origin_facility_id FK
        string destination_facility_id FK
        datetime planned_ship_time
        datetime promised_delivery_time
        datetime actual_delivery_time
        string status
        string sla_status
        boolean is_demo
    }
    tracking_events {
        string event_id PK
        string shipment_id FK
        string event_type
        datetime event_time
        datetime ingestion_time
        boolean is_duplicate
        boolean is_late_arrival
    }
    eta_estimates {
        string eta_estimate_id PK
        string shipment_id FK
        datetime prediction_time
        datetime feature_cutoff_time
        datetime predicted_eta
        float delay_probability
        string model_version
    }
```

## Key Design Principles

1. **Immutable history**: `tracking_events` and `audit_logs` are never updated or deleted.
2. **Append-only predictions**: `eta_estimates` rows are never overwritten — every prediction is a new row.
3. **Leakage prevention**: `feature_cutoff_time <= prediction_time` enforced by DB check constraint.
4. **Deterministic IDs**: All IDs follow documented formats (SHP-YYYY-NNNNNN, EVT-..., ETA-...).
5. **Derived values calculated**: utilization, carrier_score, delay_label — never independently generated.
6. **Ground truth separation**: `data_quality_issues.ground_truth_label` is never an ML input feature.
7. **Anomaly preservation**: Anomalies are labelled, not deleted. Silver layer has `is_anomaly` flag.

## Indexes

Key indexes on: `shipment_id`, `carrier_id`, `route_id`, `facility_id`, `event_time`, `ingestion_time`, `status`, `prediction_time`.

## Migrations

Alembic manages all schema changes:
```powershell
python -m alembic upgrade head      # apply all
python -m alembic history           # view history
```
