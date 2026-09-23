"""
app/database.py
=================
SQLAlchemy engine, session factory a Base trieda. Jedine miesto, kde sa
konfiguruje pripojenie k SQLite databaze.

Auto-migrate: appka nepouziva Alembic (zbytocna zataz pre jednu SQLite
databazu bez viacerych prostredi), ale pri kazdom starte porovna stlpce
kazdej modelovej tabulky s tym, co realne existuje v DB, a chybajuce
stlpce doplni cez `ALTER TABLE ... ADD COLUMN`. Vdaka tomu funguje upgrade
existujucej databazy zo starsej verzie appky bez manualneho zasahu.
Ak by appka niekedy prerastla SQLite/jeden proces, toto je miesto, kde
zamenit za Alembic migracie.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATA_DIR, DATABASE_URL

logger = logging.getLogger("aca.database")

DATA_DIR.mkdir(parents=True, exist_ok=True)

# `check_same_thread=False` je SQLite-specificky connect arg (potrebny, lebo
# FastAPI moze obsluzit request na inom threade ako ten, co DB session
# otvoril). Ak DATABASE_URL smeruje na inu databazu (napr. Postgres cez
# DATABASE_URL env premennu - viz DEPLOYMENT.md), tento arg by DBAPI
# ovladac odmietol, preto sa pridava iba pre SQLite.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# Bezpecny SQL typ + DEFAULT pre ALTER TABLE ADD COLUMN na chybajucich
# stlpcoch existujucej tabulky. SQLite vyzaduje literalny DEFAULT pri
# pridavani NOT NULL stlpca do tabulky, ktora uz moze mat riadky.
_TYPE_DEFAULTS = {
    "INTEGER": "0",
    "BOOLEAN": "0",
    "VARCHAR": "''",
    "TEXT": "''",
    "DATETIME": "NULL",
}


def _column_ddl(column) -> str:
    col_type = column.type.compile(dialect=engine.dialect)
    base_type = col_type.split("(")[0].upper()
    if column.nullable:
        default_sql = "DEFAULT NULL"
    else:
        fallback = "''"
        default_sql = f"DEFAULT {_TYPE_DEFAULTS.get(base_type, fallback)}"
    return f'ADD COLUMN "{column.name}" {col_type} {default_sql}'


def auto_migrate() -> None:
    """Porovna kazdu tabulku v Base.metadata s tym, co existuje v DB, a
    doplni chybajuce stlpce. Nikdy nemaze ani nepremenuvava stlpce - iba
    pridava, takze je bezpecne volat pri kazdom starte appky."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue  # nova tabulka - postara sa o nu create_all()
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                try:
                    ddl = _column_ddl(column)
                    conn.execute(text(f'ALTER TABLE "{table_name}" {ddl}'))
                    logger.info("auto_migrate: pridany stlpec %s.%s", table_name, column.name)
                except Exception as exc:  # noqa: BLE001 - migracia nesmie zhodit start appky
                    logger.warning("auto_migrate: nepodarilo sa pridat %s.%s (%s)", table_name, column.name, exc)


def init_db() -> None:
    """Vytvori chybajuce tabulky a doplni chybajuce stlpce v existujucich.
    Bezpecne na opakovane volanie (idempotentne)."""
    from app import models  # noqa: F401  (registruje modely do Base.metadata)

    Base.metadata.create_all(bind=engine)
    auto_migrate()
