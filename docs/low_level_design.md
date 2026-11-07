# YottaFlex — Low-Level Design

## Module Designs

### 1. Authentication & Authorization
- **Responsibility**: JWT login, role-based access, demo user seeding.
- **Input**: username + password → JWT token.
- **Output**: `{"access_token": "...", "token_type": "bearer", "role": "ADMIN"}`.
- **Dependencies**: `users`, `roles` tables, bcrypt, PyJWT.
- **Business rules**: 5 roles (ADMIN, PLANNER, ANALYST, OPERATOR, MANAGER). ADMIN bypasses role checks.
- **Security**: Passwords hashed with bcrypt. JWT signed with `JWT_SECRET`. 401 on invalid/expired token.

### 2. Shipment Management
- **Responsibility**: CRUD shipment listing with filtering, pagination, and detail views.
- **Input**: Query params (status, sla_status, carrier_id, page, page_size).
- **Output**: `{total, page, page_size, items: [...]}`.
- **Dependencies**: `shipments`, `carriers`, `routes`, `facilities`, `service_levels` tables.
- **Business rules**: Page ≥ 1, page_size 1-200. Filters apply WHERE clauses via parameterized SQL.

### 3. Tracking Event Ingestion
- **Responsibility**: Store immutable tracking events. Separate event_time from ingestion_time.
- **Input**: Event rows (shipment_id, event_type, event_time, ingestion_time, facility_id).
- **Output**: Persisted rows in `tracking_events`.
- **Business rules**: Never update/delete. `is_duplicate` and `is_late_arrival` flags set by validator.

### 4. Data Validation
- **Responsibility**: Detect PK duplicates, FK violations, enum violations, date inconsistencies, lifecycle issues, duplicate events, delayed scans, future events, ETA cutoff violations.
- **Input**: Live database state.
- **Output**: `ValidationResult` list → `DataQualityIssue` rows (failures only).
- **Business rules**: 11 validators across 5 groups. Anomalies labelled, never deleted.

### 5. ETL Processing
- **Responsibility**: Bronze (raw copy) → Silver (clean, flag) → Gold (aggregate, ML features).
- **Input**: Source tables (shipments, tracking_events, facility_queues, weather_events).
- **Output**: bronze_*, silver_*, gold_shipment_features tables + carrier/facility performance.
- **Business rules**: `is_usable_for_ml` flag. `ground_truth_label` excluded from Gold. Idempotent (ON CONFLICT).

### 6. ETA Prediction
- **Responsibility**: Rule-based and ML-based ETA calculation.
- **Input**: shipment_id + prediction_time.
- **Output**: New `eta_estimates` row (append-only).
- **Business rules**: `feature_cutoff_time = prediction_time` (no leakage). Components: base + carrier + weather + queue delays.
- **ML**: Trained models loaded from Joblib artifacts. Falls back to rule-based if no model.

### 7. Delay Classification
- **Responsibility**: Binary classification (0=on_time, 1=delayed).
- **Input**: shipment_id.
- **Output**: `delay_probability` (0-1) + `delay_label` (0/1).
- **ML**: Logistic Regression, Random Forest, Gradient Boosting. Best by F1.

### 8. Explainable AI
- **Responsibility**: SHAP-based per-prediction explanation.
- **Input**: shipment_id + prediction_type (ETA/DELAY).
- **Output**: `PredictionExplanation` row with `shap_values_json`.
- **Business rules**: Values from actual SHAP method. Rule-based fallback if SHAP unavailable. Format: "+28 percentage points".

### 9. SLA Monitoring
- **Responsibility**: Evaluate and update SLA status for all shipments.
- **Input**: Live shipment + ETA data.
- **Output**: `shipments.sla_status` update + `audit_logs` transition + `alerts`.
- **Business rules**: ON_TIME / AT_RISK / BREACHED. Dedup alerts via `dedup_key`.

### 10. Alert Generation
- **Responsibility**: Generate alerts from DB records and configured rules.
- **Input**: Current DB state (shipments, facilities, weather, DQ issues).
- **Output**: `alerts` rows + `notifications` for active users.
- **Business rules**: 9 alert types. Dedup prevents duplicate OPEN alerts. Acknowledge/resolve lifecycle.

### 11. RAG Document Ingestion
- **Responsibility**: Load → Chunk → Embed → Store in ChromaDB.
- **Input**: document_id + content (text/PDF/DOCX).
- **Output**: ChromaDB chunks + `rag_ingestion_jobs` record + `rag_documents` status update.
- **Business rules**: Chunk size 800, overlap 120. Embedding: all-MiniLM-L6-v2 (local, never OpenAI).

### 12. RAG Retrieval
- **Responsibility**: Search ChromaDB → enrich with DB metadata → format citations.
- **Input**: query string + n_results.
- **Output**: Citations with document_name, version, chunk_index, source_excerpt.
- **Business rules**: Never invent citations. Return "No supporting policy information" if empty.

### 13. GenAI Assistant
- **Responsibility**: Answer operational questions using live DB data + Groq LLM.
- **Input**: Natural language question.
- **Output**: Grounded response + data_sources list.
- **Business rules**: Retrieve live DB context first. LLM must not fabricate. Config message if no API key.

### 14. Agent Tool Execution
- **Responsibility**: Select and call tools based on keywords → build recommendation.
- **Input**: Natural language request.
- **Output**: Transparent tool summary + recommendation + `AgentDecision` row.
- **Business rules**: 11 tools. Never guesses. Persists decision with `PENDING_REVIEW`.

### 15. Route Comparison
- **Responsibility**: What-if analysis between current and alternative routes.
- **Input**: shipment_id + optional alternative_route_id.
- **Output**: ETA, delay probability, cost, time saved, risk reduction comparison.
- **Business rules**: Cost = distance_km × ₹8 (simulation rule). "NOT verified carrier quotations".

### 16. Human Approval
- **Responsibility**: Create approval requests → process decisions → log to audit.
- **Input**: approval_id + decision (APPROVED/REJECTED/MORE_INFO_REQUESTED).
- **Output**: Updated `human_approvals` + `audit_logs` + linked `agent_decisions` update.
- **Business rules**: Can't decide twice. All decisions logged immutably.

### 17. Audit Logging
- **Responsibility**: Record important operations immutably.
- **Input**: user_id, action, entity_type, entity_id, decision, reason.
- **Output**: `audit_logs` row (never updated/deleted).
- **Business rules**: Table has no `updated_at` column (immutable by design).
