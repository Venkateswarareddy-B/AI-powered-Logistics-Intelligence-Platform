# Database Schema — YottaFlex

## PostgreSQL (port 5434 local)
Total tables: 37 (27 core + 5 ETL staging + 4 migration/meta + 1 web sources)

## Core Domain Tables
roles, users, service_levels, carriers, routes, facilities, facility_queues,
weather_events, shipments, shipment_legs, tracking_events, eta_estimates,
delay_reasons, route_changes, carrier_performance, facility_performance,
alerts, notifications, notification_preferences, audit_logs,
agent_decisions, human_approvals, model_versions, prediction_explanations,
data_quality_issues, rag_documents, rag_ingestion_jobs

## ETL Tables
bronze_tracking_events, bronze_shipment_snapshot,
silver_tracking_events, silver_shipments, gold_shipment_features

## New Tables (latest migration)
rag_web_sources — tracks website URLs added as knowledge sources

## Key Constraints
- tracking_events: immutable (no UPDATE/DELETE in app)
- audit_logs: immutable (no updated_at column)
- eta_estimates: feature_cutoff_time <= prediction_time (leakage guard)
- shipments: origin_facility_id != destination_facility_id
- facility_queues: utilization_pct BETWEEN 0 AND 100

## Important Indexes
shipment_id, carrier_id, route_id, facility_id, event_time,
ingestion_time, status, prediction_time, sla_status

## Migration Commands
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic history
