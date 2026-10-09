"""An admin backup can be restored into an empty database."""

from __future__ import annotations

import gzip
import json

import pytest

from app.database import Base, SessionLocal, engine
from app.models import ForecastHistory, User
from app.services import backup
from tests.conftest import csrf_headers, signed_forecast_payload


def test_backup_round_trip(registered):
    client, username, _password = registered
    client.post("/api/forecast/save", json=signed_forecast_payload(client), headers=csrf_headers(client))
    db = SessionLocal()
    try:
        data = json.loads(gzip.decompress(backup.dump(backup.build_backup(db))))    # exactly what the admin downloads
    finally:
        db.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    counts = backup.restore_backup(engine, data)
    assert counts["users"] == 1 and counts["forecast_history"] == 1

    db = SessionLocal()
    try:
        user = db.query(User).one()
        assert user.username == username and user.created_at.year >= 2026
        assert db.query(ForecastHistory).one().user_id == user.id
    finally:
        db.close()
    # The restored account works: the session cookie is still valid and the history is there.
    assert client.get("/api/forecast/history").json()["total"] == 1


def test_restore_refuses_a_database_that_is_in_use(registered):
    db = SessionLocal()
    try:
        data = backup.build_backup(db)
    finally:
        db.close()
    with pytest.raises(ValueError):
        backup.restore_backup(engine, data)
    assert backup.restore_backup(engine, data, force=True)["users"] == 1
    with pytest.raises(ValueError):
        backup.restore_backup(engine, {"format": 99, "tables": {}}, force=True)
