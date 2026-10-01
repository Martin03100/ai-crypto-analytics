"""Alembic environment: reuses the application's engine and models."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401  (registers all tables on Base.metadata)
from app.database import Base, engine

config = context.config
# Skip logging setup when called from the app (init_db), so it does not override the app's logging.
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_render_as_batch = engine.dialect.name == "sqlite"  # SQLite cannot ALTER most things in place


def run_migrations_offline() -> None:
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=_render_as_batch, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with engine.connect() as conn:
        _run(conn)


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=_render_as_batch)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
