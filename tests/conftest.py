"""Shared pytest fixtures.

``requires_db`` skips integration tests when PostgreSQL is unavailable, so
the suite stays runnable on a machine that has not started the database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.core.database import engine


@pytest.fixture(scope="session")
def requires_db():
    """Skip the test if PostgreSQL is not reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:  # pragma: no cover - skip path
        pytest.skip(f"PostgreSQL unavailable: {exc}")

# Ensure project root is first on sys.path so ml package resolves correctly
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
