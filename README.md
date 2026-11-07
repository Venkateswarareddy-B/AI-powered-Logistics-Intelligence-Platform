# YottaFlex — AI-Powered Logistics Intelligence Platform

> **Status: All 24 phases complete · 398 tests pass · Running locally**

---

## 🚀 Quick Start — Run Locally RIGHT NOW

Follow these steps from a clean checkout. All servers are verified working.

### Step 1 — Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Python | 3.12+ | `python --version` |
| Node.js | 18+ | `node --version` |
| Docker Desktop | Any recent | `docker --version` |
| Git | Any | `git --version` |

---

### Step 2 — Clone / Open the project

```powershell
# If cloning fresh:
git clone <your-repo-url>
cd "AI-Powered Logistics Intelligence Platform"
```

---

### Step 3 — Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

---

### Step 4 — Environment configuration

```powershell
Copy-Item .env.example .env
# .env already has correct defaults — no changes needed for local dev
```

**Key `.env` settings (defaults work out of the box):**
```
POSTGRES_PORT=5434        # avoids conflict with native PostgreSQL
POSTGRES_USER=logistics
POSTGRES_PASSWORD=logistics
POSTGRES_DB=logistics_ai
GROQ_API_KEY=             # optional — fill for AI Assistant
GROQ_ENABLED=false        # set to true after adding key
```

---

### Step 5 — Start PostgreSQL (Docker)

```powershell
docker compose up -d
docker compose ps          # should show: healthy
```

PostgreSQL runs on **port 5434** to avoid conflicts with any native PostgreSQL installation.

---

### Step 6 — Database migrations

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Expected output: `Running upgrade ... -> ..., rag_web_sources`

---

### Step 7 — Generate demo data

```powershell
.\.venv\Scripts\python.exe -m data_engineering.generator --shipments 100 --events 500 --facilities 10 --disruptions 20 --seed 20261022 --reset
```

This creates 100 shipments, 504 events, 10 facilities, 23 routes, 840 queue snapshots, and 10 labelled anomalies.

---

### Step 8 — Run ETL pipeline

```powershell
.\.venv\Scripts\python.exe -m data_engineering.pipelines
```

Processes Bronze → Silver → Gold tables including ML feature rows.

---

### Step 9 — Train ML models

```powershell
.\.venv\Scripts\python.exe -m ml.training.train_eta
.\.venv\Scripts\python.exe -m ml.training.train_delay
```

---

### Step 10 — Start the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
```

Or with auto-reload for development:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

---

### Step 11 — Start the frontend

Open a **new terminal window**:

```powershell
cd frontend
npm install
npm run dev
```

---

## 🌐 Localhost Links

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend Dashboard** | **http://localhost:5173** | Full React dashboard |
| **Backend API** | http://localhost:8000 | FastAPI backend |
| **API Documentation** | http://localhost:8000/docs | Interactive Swagger UI |
| **API ReDoc** | http://localhost:8000/redoc | Alternative API docs |
| **Health Check** | http://localhost:8000/api/health | Liveness probe |
| **DB Health** | http://localhost:8000/api/health/database | Database connectivity |
| **Full System Health** | http://localhost:8000/api/health/full | All subsystems |
| **PostgreSQL** | localhost:5434 | Direct DB connection |

---

## 🔐 Demo Login Credentials

> **DEMO ONLY — Never use in production**

```
URL:      http://localhost:5173
Username: demo_admin
Password: Demo@YottaFlex2026
Role:     ADMIN
```

Open http://localhost:5173 in your browser and login with the credentials above.

---

## 🤖 Enable AI Assistant (Optional)

The AI Assistant requires a free Groq API key:

1. Go to **https://console.groq.com/keys**
2. Create a free API key
3. Edit your `.env` file:
   ```
   GROQ_API_KEY=gsk_your_key_here
   GROQ_ENABLED=true
   ```
4. Restart the backend (Ctrl+C then re-run Step 10)

Without the key, all other features work normally — the assistant shows a configuration message.

---

## 🐳 Docker Compose (Full Stack)

Start all services including backend and frontend:

```powershell
docker compose up --build -d
```

| Service | Port |
|---------|------|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| PostgreSQL | localhost:5434 |
| ChromaDB | localhost:8001 |

Stop everything:
```powershell
docker compose down
```

Reset all data:
```powershell
docker compose down -v
```

---

## 📋 All Available Commands

### Data Management
```powershell
# Generate demo data (small — development)
.\.venv\Scripts\python.exe -m data_engineering.generator --shipments 100 --reset

# Generate larger dataset
.\.venv\Scripts\python.exe -m data_engineering.generator --shipments 1000 --events 5000 --facilities 20

# Dry run (no DB writes)
.\.venv\Scripts\python.exe -m data_engineering.generator --shipments 100 --dry-run

# Run validation pipeline
.\.venv\Scripts\python.exe -m data_engineering.validation

# Run ETL pipeline
.\.venv\Scripts\python.exe -m data_engineering.pipelines

# Run only Silver or Gold stage
.\.venv\Scripts\python.exe -m data_engineering.pipelines --stage silver
.\.venv\Scripts\python.exe -m data_engineering.pipelines --stage gold
```

### Machine Learning
```powershell
# Train ETA regression model
.\.venv\Scripts\python.exe -m ml.training.train_eta

# Train delay classification model
.\.venv\Scripts\python.exe -m ml.training.train_delay
```

### Database
```powershell
# Apply all migrations
.\.venv\Scripts\python.exe -m alembic upgrade head

# Rollback one migration
.\.venv\Scripts\python.exe -m alembic downgrade -1

# View migration history
.\.venv\Scripts\python.exe -m alembic history

# Generate a new migration
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "description"
```

### Testing
```powershell
# Run all tests
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Run specific test suite
.\.venv\Scripts\python.exe -m pytest tests/api/ -v
.\.venv\Scripts\python.exe -m pytest tests/integration/ -v
.\.venv\Scripts\python.exe -m pytest tests/unit/ -v
.\.venv\Scripts\python.exe -m pytest tests/ml/ -v

# Run with coverage
.\.venv\Scripts\python.exe -m pytest tests/ --tb=short -q
```

### Backend
```powershell
# Production-style start
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Development with auto-reload
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000

# Verify setup
.\.venv\Scripts\python.exe -m scripts.verify_setup
```

### Frontend
```powershell
cd frontend
npm install          # install dependencies
npm run dev          # development server (port 5173)
npm run build        # production build
npm run preview      # preview production build
```

---

## 📱 Application Pages

All 17 pages are fully functional (no placeholders):

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | KPI cards, charts, recent shipments |
| Shipments | `/shipments` | Filterable, paginated shipment list |
| Shipment Detail | `/shipments/:id` | Tracking, ETA history, delay risk, SHAP explanation |
| ETA Prediction | `/eta` | Batch ETA prediction for active shipments |
| Delay Alerts | `/alerts` | SLA-breached and at-risk shipments |
| Carriers | `/carriers` | Carrier list + performance KPIs |
| Facilities | `/facilities` | Facility utilization trends |
| Route Optimization | `/routes` | What-if route comparison |
| AI Assistant | `/ai-assistant` | Groq-powered chat (requires API key) |
| Knowledge Base | `/knowledge` | Policy docs + website source management |
| Agent | `/agent` | Tool-calling AI with transparent execution |
| Reports | `/reports` | Charts, carrier table, delay report |
| Notifications | `/notifications` | In-app notification center |
| Audit History | `/audit` | Immutable audit log |
| System Health | `/system` | Backend/DB/ML/LLM/RAG status |
| User Management | `/users` | Roles and business actors |
| Settings | `/settings` | Feature status and quick actions |

---

## 🏗️ Architecture

```
Frontend (React + Vite + Tailwind)
         ↓ HTTP (port 5173 → proxy → 8000)
Backend (FastAPI + Uvicorn, port 8000)
         ↓
PostgreSQL (Docker, port 5434)  ← source of truth
ML Models (scikit-learn + SHAP)
ChromaDB  (RAG vector store)
Groq LLM  (optional, for AI features)
```

### Bronze → Silver → Gold ETL
```
Raw Data (generator) → Bronze (audit stamp) → Silver (clean + flag) → Gold (ML features)
```

### AI Agent Flow
```
User question → Tool selection → Execute tools (live DB) → Recommendation → Persist audit
```

---

## 🧪 Test Results

```
398 passed, 1 skipped (Groq live test — skipped without API key)
```

Test coverage:
- Database connectivity (4 tests)
- Schema integrity — 27 tables, PKs, FKs, constraints (60 tests)
- Data generator — reproducibility, anomalies, checksums (45 tests)
- Validation pipeline — 11 validators, leakage prevention (37 tests)
- ETL pipeline — Bronze/Silver/Gold, lineage (39 tests)
- SQL analytics — 12 queries (18 tests)
- ETA engine — rule-based predictions (11 tests)
- SLA monitor — status transitions, dedup (12 tests)
- Explainability — SHAP explanations (7 tests)
- Alerts — generation, dedup, lifecycle (10 tests)
- GenAI — provider abstraction, context retrieval (9 tests)
- RAG — ingestion, search, citations (13 tests)
- Agent — tools, selection, execution, transparency (19 tests)
- Route comparison (10 tests)
- Human approval + audit (14 tests)
- ML models — ETA + Delay (15 tests)
- Security — JWT, SQL injection, CORS (18 tests)
- End-to-end workflows (15 tests)
- Monitoring — health checks (17 tests)

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 5434 in use | Change `POSTGRES_HOST_PORT=5435` in `.env` |
| Docker not starting | Open Docker Desktop app, wait for daemon |
| `bcrypt` error | Already fixed — `bcrypt==4.3.0` in requirements.txt |
| CORS error | Check `CORS_ORIGINS_STR` in `.env` includes `http://localhost:5173` |
| No ML model found | Run `python -m ml.training.train_eta` and `train_delay` |
| GenAI not working | Set `GROQ_API_KEY` + `GROQ_ENABLED=true` in `.env`, restart backend |
| Frontend blank | Run `npm install` in `frontend/` directory |
| Import `ml.eta` fails | `.venv` must be activated; `tests/conftest.py` sets up sys.path |

---

## 🔐 Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `YottaFlex` | Application branding |
| `ENV` | `local` | Runtime profile: local/demo/production |
| `DEBUG` | `false` | Human-readable logs when true |
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5434` | Database port (5434 avoids native PG conflicts) |
| `POSTGRES_USER` | `logistics` | Database user |
| `POSTGRES_PASSWORD` | `logistics` | Database password |
| `POSTGRES_DB` | `logistics_ai` | Database name |
| `JWT_SECRET` | placeholder | Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `GROQ_API_KEY` | empty | Groq key from https://console.groq.com/keys |
| `GROQ_ENABLED` | `false` | Enable GenAI after setting key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `RAG_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage path |
| `RANDOM_SEED` | `20261022` | Reproducibility seed |
| `DEMO_USERNAME` | `demo_admin` | Demo login username |
| `DEMO_PASSWORD` | `Demo@YottaFlex2026` | Demo login password |

---

## 🚢 Deployment (Render + Vercel)

See `docs/deployment.md` for full instructions. Quick summary:

**Backend → Render:**
- Build: `pip install -r requirements.txt`
- Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Health: `/api/health`
- Set all env vars in Render dashboard

**Frontend → Vercel:**
- Root: `frontend/`
- Build: `npm run build` | Output: `dist`
- Set `VITE_API_URL` to your Render backend URL

**`render.yaml`** and **`frontend/vercel.json`** are pre-configured.

---

## 📁 Project Structure

```
AI-Powered Logistics Intelligence Platform/
├── backend/              # FastAPI app
│   ├── api/             # Endpoints (auth, shipments, analytics, alerts, rag, agent...)
│   ├── core/            # Config, database, logging, security
│   ├── models/          # SQLAlchemy ORM (32 tables)
│   └── services/        # Business logic (ETA, SLA, alerts, ML, RAG...)
├── data_engineering/
│   ├── generator/       # Deterministic synthetic data (seed=20261022)
│   ├── validation/      # 11 validators (PK/FK, enums, dates, lifecycle, leakage)
│   ├── transformation/  # Silver + Gold ETL jobs
│   ├── ingestion/       # Bronze layer
│   └── pipelines/       # ETL orchestrator
├── ml/
│   ├── training/        # train_eta.py, train_delay.py
│   ├── eta/             # ETA inference
│   └── delay/           # Delay inference
├── genai/
│   ├── llm/             # Groq provider abstraction
│   ├── assistant/       # Chat service
│   └── prompts/         # System prompts
├── rag/
│   ├── documents/       # Sample policies
│   ├── ingestion/       # pipeline.py + web_scraper.py
│   ├── embeddings/      # Sentence Transformers
│   ├── retrieval/       # Search + citations
│   └── vectorstore/     # ChromaDB client
├── agents/
│   ├── tools/           # 16 logistics tools
│   └── agent.py         # Tool-calling orchestrator
├── database/
│   ├── migrations/      # Alembic versions
│   └── queries/         # Advanced SQL analytics
├── frontend/            # React + Vite + Tailwind
│   └── src/
│       ├── pages/       # 17 fully functional pages
│       ├── components/  # Shared UI components
│       ├── services/    # API client (axios)
│       └── context/     # Auth context
├── tests/               # 398 tests
│   ├── api/
│   ├── data/
│   ├── integration/
│   ├── ml/
│   └── unit/
├── docs/                # Architecture, LLD, API, ML, RAG, deployment docs
├── scripts/             # verify_setup.py
├── .env.example         # Safe placeholder config
├── .env                 # Your local config (not committed)
├── .gitignore
├── alembic.ini
├── docker-compose.yml   # PostgreSQL + ChromaDB + backend + frontend
├── requirements.txt     # Pinned Python dependencies
├── requirements-dev.txt # Test dependencies
└── render.yaml          # Render deployment blueprint
```

---

## 🎯 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | FastAPI + Uvicorn | 0.162 / 0.54 |
| ORM | SQLAlchemy + Alembic | 2.1 / 1.20 |
| Database | PostgreSQL | 16 (Docker) |
| DB Driver | psycopg3 | 3.3.8 |
| Auth | PyJWT + passlib/bcrypt | 2.15 / 4.3 |
| ML | scikit-learn + joblib | 1.9 / 1.6 |
| Explainability | SHAP | 0.54 |
| GenAI | Groq + Llama | 1.7 |
| RAG Vectors | ChromaDB | 1.5.9 |
| RAG Embeddings | Sentence Transformers | 6.2 (local, no OpenAI) |
| Data Eng | Pandas + NumPy + Faker | 3.1 / 2.5 / 40 |
| Frontend | React + Vite | 18.3 / 5.4 |
| Styling | Tailwind CSS | 3.4 |
| Charts | Recharts | 2.x |
| Icons | Lucide React | 0.460 |
| Routing | React Router | 6.27 |
| HTTP Client | Axios | 1.7 |
| Testing | Pytest | 9.2 |
| Container | Docker Compose | v5 |
