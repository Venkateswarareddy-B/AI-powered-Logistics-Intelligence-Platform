"""PostgreSQL connectivity layer (SQLAlchemy 2.x, sync engine).

Phase 2 establishes connection management only: engine, session factory, a
FastAPI dependency, and a non-raising health probe. The ORM models, schema,
and Alembic migrations land in Phase 3.

Design notes:
- ``create_engine`` is **lazy**: it does not connect until the first request,
  so importing this module never requires a running database. This lets the
  backend start even when PostgreSQL is temporarily down.
- Connection pooling is configured from ``settings`` (pool_pre_ping keeps
  connections alive and drops stale ones).
- ``check_db_connection`` catches all SQLAlchemy errors and returns a status
  dict instead of raising, so health probes degrade gracefully.
"""

from __future__ import annotations

import time
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger("backend.core.database")
settings = get_settings()

# Lazy engine: no connection is opened at import time.
engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,                       # drop stale connections
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session and closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """Run ``SELECT 1`` and return a health dictionary.

    Never raises. On failure it returns ``status == "unhealthy"`` with the
    error message (connection errors do not expose the password).
    """
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": "healthy",
            "database": settings.POSTGRES_DB,
            "host": settings.POSTGRES_HOST,
            "latency_ms": latency_ms,
        }
    except SQLAlchemyError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.error(
            "database health check failed",
            extra={"props": {"error": str(exc), "latency_ms": latency_ms}},
        )
        return {
            "status": "unhealthy",
            "database": settings.POSTGRES_DB,
            "host": settings.POSTGRES_HOST,
            "latency_ms": latency_ms,
            "error": str(exc),
        }


def dispose_engine() -> None:
    """Dispose of the connection pool (used in tests/teardown)."""
    engine.dispose()
