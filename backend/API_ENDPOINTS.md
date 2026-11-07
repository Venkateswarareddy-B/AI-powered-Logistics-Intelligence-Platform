# Backend API Endpoints

## Auth
POST /api/auth/token          Login (form-encoded)
GET  /api/auth/me             Current user info

## Shipments
GET  /api/shipments           List with filters (status, sla_status, carrier_id, page)
GET  /api/shipments/{id}      Shipment detail with carrier/route/facility info
GET  /api/shipments/{id}/tracking    Immutable tracking event history
GET  /api/shipments/{id}/eta         ETA prediction history (append-only)
GET  /api/shipments/{id}/delay-risk  Latest delay probability
GET  /api/shipments/{id}/explanation SHAP-derived explanation

## Analytics
GET  /api/analytics/summary    Dashboard KPIs (total, delivered, SLA, on-time %)
POST /api/eta/predict          Run ETA prediction for a shipment
GET  /api/delays               SLA-breached and at-risk shipments
GET  /api/carriers             Carrier list
GET  /api/carriers/{id}/performance  Carrier KPIs
GET  /api/facilities           Facility list
GET  /api/facilities/{id}/queue      Queue snapshots

## Alerts & Notifications
GET  /api/alerts                   Alert list (filter by status, severity)
POST /api/alerts/{id}/acknowledge  Acknowledge an alert
POST /api/alerts/{id}/resolve      Resolve an alert
GET  /api/notifications            User notifications
GET  /api/notifications/stats      Unread/read counts
POST /api/notifications/{id}/read  Mark read
POST /api/notifications/read-all   Mark all read

## AI & RAG
POST /api/assistant/chat        GenAI chat (Groq required)
GET  /api/rag/documents         Knowledge base documents
POST /api/rag/documents         Create and ingest new document
POST /api/rag/documents/seed-samples   Seed 8 sample policies
POST /api/rag/documents/{id}/reingest  Re-index document
POST /api/rag/documents/{id}/deactivate Archive document
POST /api/rag/search            Semantic knowledge search
GET  /api/rag/web-sources       Website source list
POST /api/rag/web-sources       Add website URL for indexing
POST /api/rag/web-sources/{id}/ingest  Crawl and index website
DELETE /api/rag/web-sources/{id}       Remove website source

## Agent
POST /api/agent/run            Run tool-calling logistics agent

## Routes & Approvals
POST /api/routes/compare       What-if route comparison
GET  /api/approvals            List approval requests
POST /api/approvals            Create approval request
POST /api/approvals/{id}/decide  APPROVED|REJECTED|MORE_INFO_REQUESTED
GET  /api/audit                Immutable audit history

## Health
GET  /api/health               Liveness
GET  /api/health/database      PostgreSQL connectivity
GET  /api/health/ml            Trained model availability
GET  /api/health/llm           Groq configuration status
GET  /api/health/rag           ChromaDB + embedding status
GET  /api/health/full          All subsystems + operational metrics
