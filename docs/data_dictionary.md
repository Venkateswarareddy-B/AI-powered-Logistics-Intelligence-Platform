# YottaFlex — Data Dictionary

> Phase 3. Updated as new fields are added in subsequent phases.

All timestamps are stored as **timezone-aware UTC**. IDs use deterministic
formats documented per entity. Every table has `created_at`; mutable tables
also have `updated_at` (both managed by `TimestampMixin`).

---

## ID Conventions

| Pattern | Example | Entity |
|---------|---------|--------|
| `SHP-YYYY-NNNNNN` | `SHP-2026-000001` | Shipment |
| `LEG-SHP-YYYY-NNNNNN-NN` | `LEG-SHP-2026-000001-01` | ShipmentLeg |
| `EVT-SHP-YYYY-NNNNNN-NNNNNN` | `EVT-SHP-2026-000001-000001` | TrackingEvent |
| `ETA-SHP-YYYY-NNNNNN-YYYYMMDDHHmm` | `ETA-SHP-2026-000001-202611061200` | ETAEstimate |
| `DLY-YYYY-NNNNNN` | `DLY-2026-000001` | DelayReason |
| `FAC-NNN` | `FAC-001` | Facility |
| `CRR-NNN` | `CRR-001` | Carrier |
| `RT-NNN` | `RT-001` | Route |
| `WX-YYYYMMDD-NNN` | `WX-20261022-001` | WeatherEvent |
| `ALT-YYYYMMDD-NNN` | `ALT-20261022-001` | Alert |

Counters are **zero-padded** to maintain sort order.

---

## Tables

### roles
Reference rows for access control. Seeded at startup.

| Column | Type | Notes |
|--------|------|-------|
| `role_id` | VARCHAR(50) PK | ADMIN \| PLANNER \| ANALYST \| OPERATOR \| MANAGER |
| `role_name` | VARCHAR(100) UNIQUE | Human-readable label |
| `description` | TEXT | — |
| `is_active` | BOOLEAN | Default true |
| `created_at` | TIMESTAMPTZ | Auto |
| `updated_at` | TIMESTAMPTZ | Auto |

### users
Application users. Passwords are bcrypt-hashed, never stored plaintext.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | VARCHAR(50) PK | — |
| `username` | VARCHAR(100) UNIQUE | Login handle |
| `email` | VARCHAR(255) UNIQUE | Optional |
| `full_name` | VARCHAR(255) | — |
| `hashed_password` | VARCHAR(255) | bcrypt hash |
| `role_id` | FK → roles | RESTRICT on delete |
| `is_active` | BOOLEAN | — |
| `is_demo` | BOOLEAN | True for demo accounts |
| `last_login_at` | TIMESTAMPTZ | Updated on login |

### service_levels
SLA configuration reference data.

| Column | Type | Notes |
|--------|------|-------|
| `service_level_id` | VARCHAR(50) PK | STANDARD \| EXPRESS \| SAME_DAY \| PRIORITY |
| `name` | VARCHAR(100) UNIQUE | — |
| `maximum_delivery_hours` | NUMERIC(8,2) | SLA breach threshold |
| `allowed_delay_hours` | NUMERIC(8,2) | Grace period before BREACHED |

### carriers

| Column | Type | Notes |
|--------|------|-------|
| `carrier_id` | VARCHAR(50) PK | — |
| `carrier_name` | VARCHAR(200) UNIQUE | — |
| `carrier_code` | VARCHAR(20) UNIQUE | Short code |
| `base_delay_factor` | NUMERIC(5,3) | Multiplier ≥1.0 applied to transit time |

### routes

| Column | Type | Notes |
|--------|------|-------|
| `route_id` | VARCHAR(50) PK | — |
| `origin_facility_id` | FK → facilities | — |
| `destination_facility_id` | FK → facilities | ≠ origin |
| `distance_km` | NUMERIC(10,2) | > 0 |
| `base_transit_hours` | NUMERIC(8,2) | > 0 |

### facilities

| Column | Type | Notes |
|--------|------|-------|
| `facility_id` | VARCHAR(50) PK | — |
| `facility_type` | VARCHAR(50) | WAREHOUSE \| HUB \| DISTRIBUTION_CENTER \| SORTING_CENTER \| DELIVERY_CENTER |
| `capacity` | INTEGER | > 0 |
| `latitude` / `longitude` | NUMERIC(9,6) | Demo coords labelled as simulated |
| `status` | VARCHAR(50) | ACTIVE \| INACTIVE \| MAINTENANCE |

### facility_queues
Point-in-time queue snapshots. `utilization_pct = queue_length / capacity * 100`.

### weather_events
Discrete disruption windows.

| `weather_type` | `delay_factor` |
|---------------|----------------|
| NORMAL | 1.00 |
| RAIN | 1.15 |
| HEAVY_RAIN | 1.35 |
| STORM | 1.60 |
| FLOOD | 2.00 |
| EXTREME_HEAT | 1.10 |
| FOG | 1.25 |

### shipments
Core operational entity. SLA status recalculated by SLA monitor (Phase 9).

| Column | Type | Notes |
|--------|------|-------|
| `shipment_id` | VARCHAR(30) PK | SHP-YYYY-NNNNNN |
| `status` | VARCHAR(30) | CREATED \| PICKED_UP \| IN_TRANSIT \| AT_FACILITY \| OUT_FOR_DELIVERY \| DELIVERED \| CANCELLED \| EXCEPTION |
| `sla_status` | VARCHAR(20) | ON_TIME \| AT_RISK \| BREACHED |
| `priority` | VARCHAR(20) | LOW \| NORMAL \| HIGH \| CRITICAL |
| `is_demo` | BOOLEAN | Flags synthetic records |

### shipment_legs
Multi-leg breakdown with unique `(shipment_id, leg_sequence)`.

### tracking_events
**Immutable** — never updated or deleted.

| Column | Type | Notes |
|--------|------|-------|
| `event_time` | TIMESTAMPTZ | When event physically occurred |
| `ingestion_time` | TIMESTAMPTZ | When system received it (may lag) |
| `is_duplicate` | BOOLEAN | Flagged by Phase 5 validator |
| `is_late_arrival` | BOOLEAN | `ingestion_time >> event_time` |

### eta_estimates
**Append-only** prediction history.

| Column | Notes |
|--------|-------|
| `feature_cutoff_time` | Only events with `ingestion_time ≤ this` were used (leakage guard) |
| `model_version` | Identifies which engine/model produced this estimate |
| `model_type` | RULE_BASED \| LINEAR \| RANDOM_FOREST \| GRADIENT_BOOSTING \| XGBOOST |

### delay_reasons
Labelled delay reasons derived from outcomes and business rules (not fabricated).

### route_changes
Records diversions from the original planned route, requires `original_route_id ≠ new_route_id`.

### carrier_performance / facility_performance
Period-snapshot aggregates calculated by the ETL pipeline. Fields document their source formula.

### alerts
Generated from DB records and configured rules. `dedup_key` prevents duplicate open alerts.

| `alert_type` values |
|---------------------|
| HIGH_DELAY_RISK \| SLA_AT_RISK \| SLA_BREACH \| FACILITY_CONGESTION \| WEATHER_DISRUPTION \| ROUTE_DEVIATION \| MISSING_SCAN \| LATE_EVENT \| DATA_QUALITY_ERROR |

### notifications / notification_preferences
In-app notification center. `channel = IN_APP` is the only active channel until external providers are configured.

### audit_logs
**Immutable** rows. Never updated or deleted.

### agent_decisions
Records every agentic AI tool execution and recommendation. `tools_used` is a JSON array of `{tool, input, output}` objects.

### human_approvals
Formal approval records. `status` lifecycle: PENDING → APPROVED \| REJECTED \| MORE_INFO_REQUESTED.

### model_versions
ML model registry with metrics. `is_active` marks the currently deployed version.

### prediction_explanations
SHAP-derived explanations. `shap_values_json` stores `[{feature, shap_value, display_impact_pct}]`. Values are derived from the actual explainer — never fabricated.

### data_quality_issues
Labelled anomalies from the validation pipeline. `ground_truth_label` is from the generator — **never used as a model input feature**.

### rag_documents / rag_ingestion_jobs
Knowledge base documents and their ingestion history. Embedding model used: `sentence-transformers/all-MiniLM-L6-v2` (local, no OpenAI embeddings).
