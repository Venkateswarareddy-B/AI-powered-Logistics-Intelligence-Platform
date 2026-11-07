"""Database connectivity tests (Phase 2).

These verify the SQLAlchemy engine, session factory, and the non-raising
health probe. They require a running PostgreSQL (started via
``docker compose up -d``); otherwise they are skipped.
"""

from __future__ import annotations

from sqlalchemy import text

from backend.core.database import SessionLocal, check_db_connection, engine


def test_select_one(requires_db):
    """The engine can execute a trivial query."""
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_health_check_reports_healthy(requires_db):
    """check_db_connection reports a healthy status with latency."""
    health = check_db_connection()
    assert health["status"] == "healthy"
    assert health["database"]  # non-empty
    assert isinstance(health["latency_ms"], float)
    assert "error" not in health


def test_session_local_works(requires_db):
    """The session factory yields a usable session."""
    db = SessionLocal()
    try:
        assert db.execute(text("SELECT 1")).scalar() == 1
    finally:
        db.close()


def test_health_check_handles_bad_engine(monkeypatch):
    """check_db_connection degrades gracefully when the DB is unreachable."""
    from sqlalchemy.exc import OperationalError

    def _boom(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    # Force the engine's connect() to fail; check_db_connection must catch it.
    monkeypatch.setattr(engine, "connect", _boom)
    health = check_db_connection()
    assert health["status"] == "unhealthy"
    assert "error" in health
