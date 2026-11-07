# YottaFlex — Deployment Guide

> **Status:** Deployment preparation only. No actual deployment has been done.
> All commands below are ready to use when you're ready to deploy.

---

## 1. Local Development (Docker Compose)

The entire application runs locally via Docker:

```bash
# Start all services (PostgreSQL + Backend + Frontend + ChromaDB)
docker compose up --build -d

# Check status
docker compose ps

# View logs
docker compose logs -f backend

# Stop (keeps data)
docker compose down

# Reset everything (deletes all data)
docker compose down -v
```

### Local URLs
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5434 |
| ChromaDB | localhost:8001 |

### Without Docker (native)

```bash
# Terminal 1 — Start PostgreSQL
docker compose up -d postgres

# Terminal 2 — Run migrations + generate data + start backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m data_engineering.generator --shipments 100 --reset
.\.venv\Scripts\python.exe -m data_engineering.pipelines
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000

# Terminal 3 — Start frontend
cd frontend && npm run dev
```

---

## 2. Backend Deployment (Render)

### Prerequisites
- Render account (https://render.com)
- PostgreSQL instance (Render PostgreSQL or external)

### Steps

1. **Create a new Web Service on Render**
   - Connect your GitHub repository
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/api/health`

2. **Set Environment Variables** (in Render dashboard):
   ```
   ENV=production
   DEBUG=false
   APP_NAME=YottaFlex
   APP_TAGLINE=AI-Powered Logistics Intelligence Platform
   POSTGRES_HOST=<your-render-pg-host>
   POSTGRES_PORT=5432
   POSTGRES_USER=<your-pg-user>
   POSTGRES_PASSWORD=<your-pg-password>
   POSTGRES_DB=<your-pg-db>
   JWT_SECRET=<generate-strong-secret>
   CORS_ORIGINS_STR=https://your-app.vercel.app
   GROQ_API_KEY=<your-groq-key>
   GROQ_ENABLED=true
   RAG_ENABLED=false
   ```

3. **Run migrations** (after first deploy):
   ```bash
   # In Render shell:
   python -m alembic upgrade head
   python -m data_engineering.generator --shipments 100 --reset
   python -m data_engineering.pipelines
   ```

4. **`render.yaml`** is already configured in the repo root.

### Notes
- Render's free tier has 512MB RAM — sufficient for the backend
- ChromaDB data is ephemeral on Render free tier; use managed vector DB for production
- Sentence-transformers model downloads on first startup (~90MB)

---

## 3. Frontend Deployment (Vercel)

### Prerequisites
- Vercel account (https://vercel.com)
- Backend deployed and accessible via URL

### Steps

1. **Import the project on Vercel**
   - Framework: Vite
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`

2. **Set Environment Variables** (in Vercel dashboard):
   ```
   VITE_API_URL=https://your-backend.onrender.com
   ```

3. **`vercel.json`** is already configured with SPA rewrites.

4. The frontend proxies `/api/*` to the backend in development (via vite.config.js).
   In production, it uses `VITE_API_URL` for all API calls.

### Notes
- Vercel automatically handles SPA routing via the rewrites in `vercel.json`
- The frontend communicates with the Render backend via `VITE_API_URL`
- No secrets are exposed to the frontend (only the API URL)

---

## 4. Database Setup

### Local (Docker Compose)
- PostgreSQL 16 on port 5434
- Credentials: `logistics` / `logistics` / `logistics_ai`
- Data persisted in `yottaflex_pgdata` volume

### Production (Hosted PostgreSQL)
Use any managed PostgreSQL provider:
- Render PostgreSQL
- Supabase
- Neon
- AWS RDS

Set these environment variables:
```
POSTGRES_HOST=<host>
POSTGRES_PORT=<port>
POSTGRES_USER=<user>
POSTGRES_PASSWORD=<password>
POSTGRES_DB=<database>
```

Run migrations after connecting:
```bash
python -m alembic upgrade head
```

---

## 5. Deployment Verification Checklist

After deploying, verify each item:

- [ ] Frontend URL loads (Vercel)
- [ ] Backend URL loads (Render)
- [ ] `/api/health` returns `{"status": "healthy"}`
- [ ] `/api/health/database` returns `{"status": "healthy"}`
- [ ] Login works with demo credentials
- [ ] Dashboard loads data from API
- [ ] Shipment list pagination works
- [ ] Shipment detail page shows tracking events
- [ ] ETA prediction button works
- [ ] Carrier analytics page loads
- [ ] Facility analytics page loads
- [ ] Delay alerts page loads
- [ ] System Health page shows all 4 checks
- [ ] GenAI assistant responds (if GROQ_API_KEY set)
- [ ] RAG search returns results (if documents ingested)
- [ ] Agent runs tool execution
- [ ] Route comparison shows alternatives
- [ ] Approval workflow creates and decides
- [ ] Audit history shows logged actions

---

## 6. Environment Variables Reference

| Variable | Required | Default | Where to Set |
|----------|----------|---------|--------------|
| `APP_NAME` | No | YottaFlex | Any |
| `APP_TAGLINE` | No | AI-Powered Logistics Intelligence Platform | Any |
| `ENV` | Yes | local | Render: production |
| `DEBUG` | No | false | Render: false |
| `POSTGRES_*` | Yes | localhost:5434 | Render: hosted PG |
| `JWT_SECRET` | Yes | (placeholder) | Render: generate strong value |
| `GROQ_API_KEY` | For GenAI | (empty) | Render dashboard |
| `GROQ_ENABLED` | For GenAI | false | Render: true |
| `RAG_ENABLED` | For RAG | false | Render: true |
| `CORS_ORIGINS_STR` | Yes | localhost URLs | Render: Vercel URL |
| `VITE_API_URL` | Frontend | (proxy) | Vercel: Render URL |
