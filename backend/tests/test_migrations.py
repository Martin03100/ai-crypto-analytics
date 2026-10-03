"""Alembic migrations: fresh install, pre-Alembic database and model/migration drift."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import database


def _use_engine(tmp_path, monkeypatch, name="db.sqlite"):
    engine = sa.create_engine(f"sqlite:///{tmp_path}/{name}")
    monkeypatch.setattr(database, "engine", engine)
    return engine


def _head() -> str:
    return ScriptDirectory.from_config(database._alembic_config()).get_current_head()


def _current(engine) -> str:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def test_fresh_database_is_created_by_migrations(tmp_path, monkeypatch):
    engine = _use_engine(tmp_path, monkeypatch)
    database.init_db()
    assert _current(engine) == _head()
    assert {"users", "forecast_history", "audit_events"} <= set(sa.inspect(engine).get_table_names())


def test_migrations_match_the_models(tmp_path, monkeypatch):
    """Fails when a model changes without a migration: run `alembic revision --autogenerate -m "..."`."""
    engine = _use_engine(tmp_path, monkeypatch)
    database.init_db()
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), database.Base.metadata)
    assert diff == []


def test_pre_alembic_database_is_stamped_and_upgraded(tmp_path, monkeypatch):
    engine = _use_engine(tmp_path, monkeypatch)
    command.upgrade(database._alembic_config(), "0001")
    with engine.begin() as conn:  # what an install from before Alembic looks like
        conn.execute(sa.text("DROP TABLE alembic_version"))
        conn.execute(sa.text("INSERT INTO users (username, password_hash, created_at, token_version, "
                             "failed_login_attempts) VALUES ('old', 'h', '2026-01-01', 0, 0)"))
    database.init_db()
    assert _current(engine) == _head()
    inspector = sa.inspect(engine)
    assert {"eval_attempts", "eval_last_try_at"} <= {c["name"] for c in inspector.get_columns("forecast_history")}
    assert "totp_last_step" in {c["name"] for c in inspector.get_columns("users")}
    assert "ix_forecast_history_user_id" in {i["name"] for i in inspector.get_indexes("forecast_history")}
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), database.Base.metadata) == []
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT username FROM users")).scalar_one() == "old"


def test_pre_alembic_database_already_completed_by_auto_migrate(tmp_path, monkeypatch):
    """A database already matching the models is only stamped; restarting is a no-op."""
    engine = _use_engine(tmp_path, monkeypatch)
    database.Base.metadata.create_all(bind=engine)
    database.init_db()
    database.init_db()  # idempotent on restart
    assert _current(engine) == _head()


def test_downgrade_and_upgrade_roundtrip(tmp_path, monkeypatch):
    engine = _use_engine(tmp_path, monkeypatch)
    cfg = database._alembic_config()
    database.init_db()
    command.downgrade(cfg, "base")
    assert set(sa.inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(cfg, "head")
    assert _current(engine) == _head()


def test_legacy_database_is_not_stamped_when_a_column_could_not_be_added(tmp_path, monkeypatch):
    import pytest
    engine = _use_engine(tmp_path, monkeypatch)
    command.upgrade(database._alembic_config(), "0001")
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE alembic_version"))
    monkeypatch.setattr(database, "auto_migrate", lambda: None)     # every ALTER "failed"
    with pytest.raises(RuntimeError, match="chybaju stlpce"):
        database.init_db()
    assert "alembic_version" not in sa.inspect(engine).get_table_names()
