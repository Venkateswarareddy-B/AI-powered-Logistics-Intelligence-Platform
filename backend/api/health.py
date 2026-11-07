"""Health endpoints."""
from __future__ import annotations
from fastapi import APIRouter
from backend.core.database import check_db_connection
from backend.core.config import get_settings

router = APIRouter(prefix="/api/health", tags=["health"])
settings = get_settings()


@router.get("")
def health():
    return {"status": "healthy", "app": settings.APP_NAME, "env": settings.ENV,
            "groq_configured": settings.GROQ_ENABLED, "rag_configured": settings.RAG_ENABLED}


@router.get("/database")
def health_database():
    return check_db_connection()


@router.get("/ml")
def health_ml():
    import os
    model_dir = settings.ML_MODELS_DIR
    has_models = os.path.isdir(model_dir) and bool(os.listdir(model_dir))
    return {"status": "available" if has_models else "no_models_trained",
            "models_dir": model_dir, "models_present": has_models}


@router.get("/llm")
def health_llm():
    if not settings.GROQ_ENABLED or not settings.GROQ_API_KEY:
        return {"status": "not_configured",
                "message": "Set GROQ_API_KEY and GROQ_ENABLED=true to enable GenAI"}
    return {"status": "configured", "model": settings.GROQ_MODEL}


@router.get("/rag")
def health_rag():
    """RAG / ChromaDB availability check."""
    from backend.services.monitoring import get_rag_status
    from backend.core.database import SessionLocal
    db = SessionLocal()
    try:
        return get_rag_status(db)
    finally:
        db.close()


@router.get("/full")
def health_full():
    """Comprehensive system health — all subsystems, operational metrics, recent errors.

    Never exposes secrets. This is the endpoint the System Health page uses.
    """
    from backend.services.monitoring import get_system_health
    from backend.core.database import SessionLocal
    db = SessionLocal()
    try:
        return get_system_health(db)
    finally:
        db.close()
