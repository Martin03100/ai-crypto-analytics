"""Database backup (admin download) and restore (command line: python -m app.services.backup restore FILE)."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import date, datetime, timezone
from typing import Any, Dict

from sqlalchemy import Date, DateTime, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database import Base

FORMAT = 1


def build_backup(db: Session) -> Dict[str, Any]:
    """Every table as plain JSON-ready rows. Secrets stay as stored (hashed or encrypted)."""
    from app import models  # noqa: F401 - registers every table

    data: Dict[str, Any] = {"created_at": datetime.now(timezone.utc).isoformat(), "format": FORMAT, "tables": {}}
    for table in Base.metadata.sorted_tables:
        rows = db.execute(table.select()).mappings().all()
        data["tables"][table.name] = [dict(r) for r in rows]
    return data


def dump(data: Dict[str, Any]) -> bytes:
    return gzip.compress(json.dumps(data, default=str, ensure_ascii=False).encode("utf-8"))


def _value(column, value):
    if value is None:
        return None
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date) and isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def restore_backup(engine: Engine, data: Dict[str, Any], force: bool = False) -> Dict[str, int]:
    """Load a backup into a database with the current schema (run the migrations first).

    Refuses to touch a database that already holds users unless `force` is set; with `force` every table is emptied
    before loading. Returns the number of rows restored per table."""
    from app import models  # noqa: F401

    if data.get("format") != FORMAT or not isinstance(data.get("tables"), dict):
        raise ValueError("Unknown backup format.")
    tables = Base.metadata.sorted_tables
    restored: Dict[str, int] = {}
    with engine.begin() as conn:
        users = Base.metadata.tables["users"]
        if conn.execute(select(func.count()).select_from(users)).scalar() and not force:
            raise ValueError("The database is not empty; pass --force to replace its contents.")
        for table in reversed(tables):           # children first, so foreign keys never block the delete
            conn.execute(table.delete())
        for table in tables:                     # parents first
            rows = data["tables"].get(table.name) or []
            columns = {c.name: c for c in table.columns}
            clean = [{k: _value(columns[k], v) for k, v in row.items() if k in columns} for row in rows]
            if clean:
                conn.execute(table.insert(), clean)
            restored[table.name] = len(clean)
        if engine.dialect.name == "postgresql":  # continue ids after the restored rows
            for table in tables:
                pk = [c for c in table.primary_key.columns if c.autoincrement is not False and c.type.python_type is int]
                if len(pk) == 1:
                    conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0].name}'), "
                                      f"COALESCE((SELECT MAX({pk[0].name}) FROM {table.name}), 1))"))
    return restored


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Restore an AI Crypto Analytics backup (.json.gz from the admin panel).")
    sub = parser.add_subparsers(dest="command", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("file")
    restore.add_argument("--force", action="store_true", help="replace the contents of a database that is not empty")
    args = parser.parse_args(argv)

    from app.database import engine, init_db

    init_db()                                    # schema at the latest migration first
    with gzip.open(args.file, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    counts = restore_backup(engine, data, force=args.force)
    print(f"Restored {sum(counts.values())} rows in {len(counts)} tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
