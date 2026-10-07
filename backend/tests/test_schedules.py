"""Scheduled forecasts and the dashboard watchlist."""

from __future__ import annotations

from datetime import datetime

from app.services import schedules
from app.services.premium import FREE_SCHEDULES
from tests.conftest import csrf_headers


def _create(client, **overrides):
    body = {"provider": "quant", "coin": "BTC", "horizon": "1T", "frequency": "daily", "hour": 8, "minute": 0,
            "timezone": "Europe/Bratislava", "lang": "sk"}
    body.update(overrides)
    return client.post("/api/schedules", json=body, headers=csrf_headers(client))


def test_next_run_daily_and_weekly_in_utc():
    wed_9 = datetime(2026, 10, 7, 9, 30)   # a Wednesday, naive UTC
    nxt = schedules.compute_next_run
    assert nxt("daily", None, 8, 0, "UTC", wed_9) == datetime(2026, 10, 8, 8)
    assert nxt("daily", None, 10, 0, "UTC", wed_9) == datetime(2026, 10, 7, 10)
    assert nxt("weekly", 0, 8, 0, "UTC", wed_9) == datetime(2026, 10, 12, 8)     # next Monday
    assert nxt("weekly", 2, 10, 0, "UTC", wed_9) == datetime(2026, 10, 7, 10)    # later today
    assert nxt("weekly", 2, 9, 0, "UTC", wed_9) == datetime(2026, 10, 14, 9)     # passed: next week


def test_next_run_keeps_local_time_across_dst_and_half_hour_zones():
    nxt = schedules.compute_next_run
    friday = datetime(2026, 10, 23, 12)   # Bratislava switches from CEST (+2) to CET (+1) on 25 Oct
    assert nxt("weekly", 4, 8, 0, "Europe/Bratislava", friday) == datetime(2026, 10, 30, 7)   # 08:00 CET
    assert nxt("weekly", 0, 8, 0, "Europe/Bratislava", friday) == datetime(2026, 10, 26, 7)   # Monday after the switch
    assert nxt("daily", None, 8, 0, "Asia/Kolkata", datetime(2026, 10, 7, 0)) == datetime(2026, 10, 7, 2, 30)
    assert nxt("daily", None, 8, 15, "Asia/Kathmandu", datetime(2026, 10, 7, 0)) == datetime(2026, 10, 7, 2, 30)


def test_crud_and_ownership(registered, client):
    c, _u, _p = registered
    res = _create(c)
    assert res.status_code == 201, res.text
    sid = res.json()["id"]
    assert res.json()["next_run_at"].endswith("+00:00")
    listed = c.get("/api/schedules").json()
    assert [s["id"] for s in listed["items"]] == [sid] and listed["max"] == FREE_SCHEDULES
    assert c.patch(f"/api/schedules/{sid}", json={"active": False}, headers=csrf_headers(c)).json()["active"] is False
    # another user can neither see nor change it
    c.cookies.clear()
    c.post("/api/auth/register", json={"username": "other1", "password": "TestPass123", "email": "o@example.com"})
    assert c.get("/api/schedules").json()["items"] == []
    assert c.delete(f"/api/schedules/{sid}", headers=csrf_headers(c)).status_code == 404


def test_validation_and_limit(registered):
    c, _u, _p = registered
    assert _create(c, provider="nope").status_code == 400
    assert _create(c, coin="FAKECOIN").status_code == 400
    assert _create(c, frequency="weekly").status_code == 422          # weekday missing
    assert _create(c, horizon="1R").status_code == 422
    assert _create(c, hour=24).status_code == 422
    assert _create(c, timezone="Mars/Olympus").status_code == 422
    for _ in range(FREE_SCHEDULES):
        assert _create(c).status_code == 201
    assert _create(c).status_code == 400


def _make_due(sid):
    from app.database import SessionLocal
    from app.models import ForecastSchedule
    db = SessionLocal()
    try:
        db.get(ForecastSchedule, sid).next_run_at = datetime(2020, 1, 1)
        db.commit()
    finally:
        db.close()


def test_due_schedule_saves_a_forecast_once(registered, monkeypatch):
    from app.services import ai_engine
    c, _u, _p = registered
    sid = _create(c).json()["id"]
    _make_due(sid)
    data = {"ceny": [1.0, 2.0], "casove_body": ["a", "b"], "odovodnenie": "x", "vytvorene": "2026-10-01T00:00:00+00:00"}
    calls = []
    monkeypatch.setattr(ai_engine, "get_coin_forecast",
                        lambda *a: calls.append(a) or ai_engine.AIEngineResult(True, dict(data), False))
    assert schedules.run_due_schedules() == 1
    assert schedules.run_due_schedules() == 0          # already claimed and moved to the next run
    assert calls == [("quant", "BTC", "1T", None, "sk")]
    row = c.get("/api/schedules").json()["items"][0]
    assert row["last_status"] == "ok" and row["last_forecast_id"]
    assert row["next_run_at"] > "2026"
    history = c.get("/api/forecast/history").json()["items"]
    assert history[0]["id"] == row["last_forecast_id"] and history[0]["model_used"] == "Quant (free model)"


def test_ai_schedule_without_key_reports_error_and_paused_schedule_is_skipped(registered, monkeypatch):
    from app.services import ai_engine
    c, _u, _p = registered
    sid = _create(c, provider="gemini").json()["id"]
    paused = _create(c).json()["id"]
    c.patch(f"/api/schedules/{paused}", json={"active": False}, headers=csrf_headers(c))
    _make_due(sid)
    _make_due(paused)
    monkeypatch.setattr(ai_engine, "get_coin_forecast", lambda *a: (_ for _ in ()).throw(AssertionError("no call")))
    assert schedules.run_due_schedules() == 1
    rows = {s["id"]: s for s in c.get("/api/schedules").json()["items"]}
    assert rows[sid]["last_status"] == "error" and rows[sid]["last_error"] == "missing_key"
    assert rows[paused]["last_status"] is None


def test_schedules_are_removed_with_the_account(registered):
    from app.database import SessionLocal
    from app.models import ForecastSchedule
    c, _u, password = registered
    _create(c)
    assert c.post("/api/account/delete", json={"password": password}, headers=csrf_headers(c)).status_code == 200
    db = SessionLocal()
    try:
        assert db.query(ForecastSchedule).count() == 0
    finally:
        db.close()


def test_watchlist_defaults_and_update(registered):
    c, _u, _p = registered
    assert c.get("/api/account/watchlist").json()["coins"] == ["BTC", "ETH", "SOL"]
    res = c.put("/api/account/watchlist", json={"coins": ["eth", "ETH", "LINK"]}, headers=csrf_headers(c))
    assert res.status_code == 200 and res.json()["coins"] == ["ETH", "LINK"]
    assert c.get("/api/account/watchlist").json()["coins"] == ["ETH", "LINK"]
    assert c.put("/api/account/watchlist", json={"coins": ["FAKECOIN"]}, headers=csrf_headers(c)).status_code == 400
    assert c.put("/api/account/watchlist", json={"coins": ["BTC"] * 13}, headers=csrf_headers(c)).status_code == 422


def test_a_schedule_is_claimed_by_only_one_poller(registered):
    """Two workers polling at the same moment: exactly one wins each due schedule."""
    from datetime import datetime as dt
    c, _u, _p = registered
    ids = [_create(c, coin=coin).json()["id"] for coin in ("BTC", "ETH")]
    for sid in ids:
        _make_due(sid)
    now = dt(2026, 10, 7, 12)
    first = schedules.claim_due_schedules(now)
    second = schedules.claim_due_schedules(now)
    assert sorted(first) == sorted(ids) and second == []
