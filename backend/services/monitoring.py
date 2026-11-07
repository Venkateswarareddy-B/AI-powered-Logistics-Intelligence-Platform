"""System monitoring service (Phase 23).

Aggregates health status across all subsystems:
  - Backend (always healthy if this runs)
  - Database (PostgreSQL connectivity)
  - ML models (trained model availability)
  - LLM (Groq connectivity)
  - RAG (ChromaDB + embedding model)
  - Last successful ingestion (ETL pipeline run)
  - Last successful prediction (ETA estimate timestamp)
  - Recent errors (from audit logs / data quality issues)

Never exposes sensitive information in health responses.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import check_db_connection, SessionLocal

settings = get_settings()
log = logging.getLogger("backend.services.monitoring")


def get_database_status() -> dict:
    """Check PostgreSQL connectivity."""
    return check_db_connection()


def get_ml_status() -> dict:
    """Check ML model availability."""
    import glob
    eta_dir = os.path.join(settings.ML_MODELS_DIR, "eta")
    delay_dir = os.path.join(settings.ML_MODELS_DIR, "delay")
    eta_models = glob.glob(os.path.join(eta_dir, "*.joblib"))
    delay_models = glob.glob(os.path.join(delay_dir, "*.joblib"))
    return {
        "status": "available" if eta_models and delay_models else "partial" if eta_models or delay_models else "no_models_trained",
        "eta_models": len(eta_models),
        "delay_models": len(delay_models),
        "models_dir": settings.ML_MODELS_DIR,
    }


def get_llm_status() -> dict:
    """Check LLM / Groq connectivity."""
    if not settings.GROQ_ENABLED or not settings.GROQ_API_KEY:
        return {
            "status": "not_configured",
            "message": "GenAI requires a Groq API key. See deployment docs for setup instructions.",
        }
    return {
        "status": "configured",
        "model": settings.GROQ_MODEL,
        "base_url": settings.GROQ_BASE_URL,
    }


def get_rag_status(db: Session) -> dict:
    """Check RAG / ChromaDB availability."""
    try:
        from rag.vectorstore.chroma_client import get_collection, count_chunks
        coll = get_collection()
        if coll is None:
            return {"status": "unavailable", "message": "ChromaDB not initialized"}
        chunk_count = count_chunks()

        # Check embedding model
        from rag.embeddings.embedder import get_embedder
        embedder = get_embedder()
        embedding_ok = embedder is not None

        # Check documents in DB
        doc_count = db.execute(text(
            "SELECT COUNT(*) FROM rag_documents WHERE is_active = TRUE"
        )).scalar()
        active_docs = db.execute(text(
            "SELECT COUNT(*) FROM rag_documents WHERE processing_status = 'ACTIVE'"
        )).scalar()

        return {
            "status": "available" if chunk_count > 0 and embedding_ok else "initialized_empty" if embedding_ok else "no_embeddings",
            "chromadb_connected": coll is not None,
            "embedding_model": settings.RAG_EMBEDDING_MODEL if embedding_ok else None,
            "vector_chunks": chunk_count,
            "total_documents": int(doc_count),
            "active_documents": int(active_docs),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)[:200]}


def get_last_successful_ingestion(db: Session) -> dict:
    """Get the most recent ETL pipeline run timestamp."""
    try:
        row = db.execute(text("""
            SELECT MAX(silver_processed_at) AS last_ingestion
            FROM silver_tracking_events
        """)).scalar()
        if row:
            return {
                "status": "available",
                "last_ingestion": str(row),
                "hours_ago": round((datetime.now(timezone.utc) - row).total_seconds() / 3600, 1)
                    if isinstance(row, datetime) else None,
            }
        return {"status": "never_run", "last_ingestion": None}
    except Exception as exc:
        return {"status": "error", "message": str(exc)[:200]}


def get_last_successful_prediction(db: Session) -> dict:
    """Get the most recent ETA prediction timestamp."""
    try:
        row = db.execute(text("""
            SELECT MAX(prediction_time) AS last_prediction,
                   MAX(created_at) AS last_created
            FROM eta_estimates
        """)).mappings().fetchone()
        if row and row["last_prediction"]:
            return {
                "status": "available",
                "last_prediction": str(row["last_prediction"]),
                "hours_ago": round((datetime.now(timezone.utc) - row["last_prediction"]).total_seconds() / 3600, 1)
                    if isinstance(row["last_prediction"], datetime) else None,
            }
        return {"status": "never_run", "last_prediction": None}
    except Exception as exc:
        return {"status": "error", "message": str(exc)[:200]}


def get_recent_errors(db: Session, limit: int = 10) -> list[dict]:
    """Get recent errors from audit logs and data quality issues."""
    errors = []

    # Recent audit log entries with error-like actions
    try:
        rows = db.execute(text("""
            SELECT audit_id, action, entity_type, entity_id,
                   reason, timestamp
            FROM audit_logs
            WHERE action LIKE '%ERROR%' OR action LIKE '%FAIL%' OR action LIKE '%BREACH%'
            ORDER BY timestamp DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().fetchall()
        for r in rows:
            errors.append({
                "source": "audit_log",
                "id": r["audit_id"],
                "action": r["action"],
                "entity": f"{r['entity_type']}:{r['entity_id']}",
                "detail": str(r["reason"])[:200] if r["reason"] else None,
                "timestamp": str(r["timestamp"]),
            })
    except Exception:
        pass

    # Recent high-severity data quality issues
    try:
        rows = db.execute(text("""
            SELECT issue_id, issue_type, entity_type, entity_id,
                   severity, description, detected_at
            FROM data_quality_issues
            WHERE severity IN ('HIGH', 'CRITICAL') AND is_resolved = FALSE
            ORDER BY detected_at DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().fetchall()
        for r in rows:
            errors.append({
                "source": "data_quality",
                "id": r["issue_id"],
                "issue_type": r["issue_type"],
                "entity": f"{r['entity_type']}:{r['entity_id']}",
                "severity": r["severity"],
                "detail": str(r["description"])[:200],
                "timestamp": str(r["detected_at"]),
            })
    except Exception:
        pass

    return errors[:limit]


def get_system_health(db: Session) -> dict:
    """Get comprehensive system health status across all subsystems.

    Never exposes secrets, passwords, or connection strings.
    """
    db_status = get_database_status()
    ml_status = get_ml_status()
    llm_status = get_llm_status()
    rag_status = get_rag_status(db)
    ingestion = get_last_successful_ingestion(db)
    prediction = get_last_successful_prediction(db)
    recent_errors = get_recent_errors(db)

    # Overall status: healthy if DB is healthy
    overall = "healthy"
    if db_status["status"] != "healthy":
        overall = "degraded"
    elif ml_status["status"] == "no_models_trained":
        overall = "degraded"

    return {
        "overall_status": overall,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "backend": {
                "status": "healthy",
                "uptime_note": "Backend is responding",
            },
            "database": db_status,
            "ml": ml_status,
            "llm": llm_status,
            "rag": rag_status,
        },
        "operational": {
            "last_successful_ingestion": ingestion,
            "last_successful_prediction": prediction,
            "recent_errors": recent_errors,
            "error_count": len(recent_errors),
        },
        "configuration": {
            "groq_enabled": settings.GROQ_ENABLED,
            "rag_enabled": settings.RAG_ENABLED,
            "debug": settings.DEBUG,
        },
    }
