"""YottaFlex FastAPI application — Phase 10 (full REST API + auth)."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import get_settings
from backend.core.database import check_db_connection, SessionLocal
from backend.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(level=settings.LOG_LEVEL, debug=settings.DEBUG)
log = get_logger("backend.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_health = check_db_connection()
    log.info("application starting", extra={"props": {
        "app": settings.APP_NAME, "env": settings.ENV, "db": db_health["status"]
    }})
    if db_health["status"] == "healthy":
        try:
            from backend.api.auth import seed_demo_user
            db = SessionLocal()
            seed_demo_user(db)
            db.close()
            log.info("demo user seeded")
        except Exception as exc:
            log.warning("demo user seed failed: %s", exc)
    yield
    log.info("application stopping")


app = FastAPI(
    title=f"{settings.APP_NAME} — {settings.APP_TAGLINE}",
    version=settings.APP_VERSION,
    description="YottaFlex AI-Powered Logistics Intelligence Platform REST API",
    lifespan=lifespan,
    docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
from backend.api.health import router as health_router
from backend.api.auth import router as auth_router
from backend.api.shipments import router as shipments_router
from backend.api.analytics import router as analytics_router, alerts_router, notif_router
from backend.api.assistant import router as assistant_router
from backend.api.rag import router as rag_router
from backend.api.agent import router as agent_router
from backend.api.routes import router as routes_router
from backend.api.approval import router as approval_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(shipments_router)
app.include_router(analytics_router)
app.include_router(alerts_router)
app.include_router(notif_router)
app.include_router(assistant_router)
app.include_router(rag_router)
app.include_router(agent_router)
app.include_router(routes_router)
app.include_router(approval_router)


@app.get("/", tags=["meta"])
async def root():
    return {"app": settings.APP_NAME, "tagline": settings.APP_TAGLINE,
            "version": settings.APP_VERSION, "env": settings.ENV, "status": "ok"}
