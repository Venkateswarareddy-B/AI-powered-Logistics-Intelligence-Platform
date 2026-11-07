# CHANGELOG

## v1.0.0 — 2026-11-07

### Added
- Premium SaaS dashboard with dark navy sidebar, gradient KPI cards, donut + bar charts
- 16 agent tools: shipment tracking, delay analysis, SLA stats, high-risk detection, carrier scoring
- RAG website ingestion pipeline with robots.txt compliance and private-network protection
- Enhanced Knowledge Base: website source management, add/sync/delete URLs
- Agent chat UI with typing indicators, copy button, source citations, expandable policy refs
- Explainable AI: SHAP-derived per-prediction explanations shown on shipment detail page
- Human approval workflow with immutable PostgreSQL audit trail
- 398 automated tests across all layers (API, ML, RAG, Agent, Security, E2E)

### Fixed
- bcrypt 5.x incompatibility with passlib 1.7.4 (pinned to 4.3.0)
- CORS_ORIGINS pydantic-settings JSON decode error (CORS_ORIGINS_STR workaround)
- Docker Compose postgres:17 image doubling (switched to POSTGRES_VERSION variable)
- Native PG18 port 5432 conflict (platform runs on port 5434)
- Agent execute_tools FAC-001 hardcoded default replaced with dynamic DB lookup
- ML package conflict on Python 3.14 (tests/ml __init__.py shadowing ml package)

### Architecture
- Backend: FastAPI + SQLAlchemy 2.x + Alembic (32 tables)
- Frontend: React 18 + Vite 5 + Tailwind CSS 3
- Data: Bronze/Silver/Gold ETL, deterministic generator (seed 20261022)
- ML: scikit-learn ETA regression + delay classification + SHAP
- GenAI: Groq provider abstraction (OpenAI never used)
- RAG: ChromaDB + sentence-transformers (local, no cloud embeddings)
