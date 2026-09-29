"""Database setup."""

from __future__ import annotations

import logging

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


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    auto_migrate()
