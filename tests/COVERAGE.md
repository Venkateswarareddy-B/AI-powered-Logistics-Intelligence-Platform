# Test Suite — YottaFlex

## Coverage: 398 tests (0 failures, 1 skipped)

## Test Files by Layer
tests/integration/test_database.py    (4)  — DB connectivity + SELECT 1
tests/integration/test_schema.py      (60) — 37 tables, PKs, FKs, constraints
tests/integration/test_end_to_end.py  (15) — Full workflow chains
tests/integration/test_security.py    (18) — JWT, SQL injection, CORS
tests/integration/test_monitoring.py  (17) — Health checks, no secrets exposed

tests/data/test_generator.py    (45) — Reproducibility, checksums, anomalies
tests/data/test_validation.py   (37) — 11 validators, leakage contracts
tests/data/test_etl.py          (39) — Bronze/Silver/Gold, lineage, idempotency
tests/data/test_analytics.py    (18) — 12 SQL queries, CTE/window functions

tests/api/test_api.py           (25) — All endpoints, auth, pagination, 404s

tests/unit/test_eta_engine.py   (11) — Rule-based ETA, leakage prevention
tests/unit/test_sla_monitor.py  (12) — SLA transitions, dedup alerts
tests/unit/test_explainability.py (7) — SHAP explanations, factor sorting
tests/unit/test_alerts.py       (10) — Alert generation, dedup, lifecycle
tests/unit/test_genai.py         (9) — Provider abstraction, no OpenAI
tests/unit/test_rag.py          (13) — Ingestion, search, citations
tests/unit/test_agent.py        (19) — Tool registry, selection, execution
tests/unit/test_route_service.py (10) — Route comparison, cost formula
tests/unit/test_approval.py     (14) — Approval workflow, audit immutability
tests/ml/test_eta_model.py       (8) — Artifact, DB registry, leakage check
tests/ml/test_delay_model.py     (7) — Artifact, metrics, binary labels

## Run Commands
python -m pytest tests/ -q             # all tests
python -m pytest tests/api/ -v        # API only
python -m pytest tests/unit/ -v       # unit tests
