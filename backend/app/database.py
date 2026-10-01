"""Database setup."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATA_DIR, DATABASE_URL

logger = logging.getLogger("aca.database")

DATA_DIR.mkdir(parents=True, exist_ok=True)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


_TYPE_DEFAULTS = {
    "INTEGER": "0",
    "BIGINT": "0",
    "SMALLINT": "0",
    "FLOAT": "0",
    "REAL": "0",
    "DOUBLE PRECISION": "0",
    "NUMERIC": "0",
    "VARCHAR": "''",
    "TEXT": "''",
    "DATETIME": "NULL",
}


def _column_ddl(column) -> str:
    col_type = column.type.compile(dialect=engine.dialect)
    base_type = col_type.split("(")[0].upper()
    if column.nullable:
        default_sql = "DEFAULT NULL"
    elif base_type == "BOOLEAN":
        default_sql = "DEFAULT false" if engine.dialect.name == "postgresql" else "DEFAULT 0"
    else:
        default_sql = f"DEFAULT {_TYPE_DEFAULTS.get(base_type, chr(39) * 2)}"
    return f'ADD COLUMN "{column.name}" {col_type} {default_sql}'


def auto_migrate() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            try:
                ddl = _column_ddl(column)
                with engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{table_name}" {ddl}'))
                logger.info("auto_migrate: pridany stlpec %s.%s", table_name, column.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("auto_migrate: nepodarilo sa pridat %s.%s (%s)", table_name, column.name, exc)


_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.attributes["configure_logging"] = False
    return cfg


def _create_missing_indexes() -> None:
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        existing = {i["name"] for i in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name not in existing:
                index.create(bind=engine)
                logger.info("init_db: pridany index %s", index.name)


def init_db() -> None:
    """Bring the database schema to the latest Alembic revision.

    A database created before Alembic was introduced (create_all + auto_migrate, no alembic_version table) is
    completed to the current models once (tables, columns, indexes) and stamped as the latest revision.
    """
    from alembic import command

    from app import models  # noqa: F401

    cfg = _alembic_config()
    existing = set(inspect(engine).get_table_names())
    if "alembic_version" not in existing and existing & set(Base.metadata.tables):
        logger.info("init_db: databaza bez Alembic verzie - doplnam schemu a oznacujem ju ako aktualnu")
        Base.metadata.create_all(bind=engine)
        auto_migrate()
        _create_missing_indexes()
        command.stamp(cfg, "head")
        return
    command.upgrade(cfg, "head")
