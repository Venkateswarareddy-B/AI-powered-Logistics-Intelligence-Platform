"""Alembic environment configuration for YottaFlex.

This file is loaded by every alembic command. It:
  1. Reads the database URL from Settings (env vars / .env file).
  2. Imports every ORM model so Base.metadata is fully populated.
  3. Runs migrations in online mode (connects to the real DB).

Never import credentials directly — always use get_settings().
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the project root is on sys.path so backend.* imports work
# regardless of where alembic is invoked from.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load all ORM models — MUST happen before Base.metadata is used below.
import backend.models  # noqa: F401 — registers all 27 tables
from backend.models.base import Base
from backend.core.config import get_settings

# --------------------------------------------------------------------------
# Alembic config object (reads alembic.ini)
config = context.config

# Inject the database URL from our Settings so alembic.ini doesn't need it.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData that autogenerate compares against
target_metadata = Base.metadata


# --------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Generate SQL without a live connection (used for SQL script output)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
