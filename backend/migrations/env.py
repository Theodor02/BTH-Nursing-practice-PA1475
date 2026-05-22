"""Alembic environment.

Reads the database URL from the same env vars the Flask app uses so
``alembic upgrade head`` can be run from the entrypoint script before
Gunicorn starts, with no Flask app instance required.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import metadata from the application models so autogenerate sees them.
from logic.database.init.init_db import db
import logic.database.init.class_db  # noqa: F401 — registers all model tables on db.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata


def _build_database_url() -> str:
    explicit = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    return (
        f"postgresql://{os.getenv('POSTGRES_USER', 'qtrain')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'qtrain')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'qtrain')}"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_build_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option("sqlalchemy.url", _build_database_url())
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
