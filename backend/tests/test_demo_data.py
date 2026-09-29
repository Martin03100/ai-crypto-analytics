"""One-click demo data."""

import json
from datetime import datetime, timezone

from tests.conftest import csrf_headers
from tests.test_quant_real_data import SERIES as REAL_BTC_DAILY


def _patch_real_history(monkeypatch):
    from app.services import market_data
    monkeypatch.setattr(market_data, "get_market_history",
                        lambda coin_id, days=30, *a, **k: (True, {"prices": REAL_BTC_DAILY, "volumes": []}, None))


def test_demo_forecasts_use_only_data_known_at_their_date(monkeypatch):
    from app.services.demo_data import _forecast_at
    from app.services import quant_engine
    series = quant_engine._clean_series(REAL_BTC_DAILY)
    origin = series[200][0]
    data = _forecast_at(series, origin, "BTC", "1T", "en")
    assert data["aktualna_cena"] == series[200][1]
    assert datetime.fromisoformat(data["vytvorene"]).timestamp() * 1000 == origin
    tampered = [(ts, p * (5 if ts > origin else 1)) for ts, p in series]
    assert _forecast_at(tampered, origin, "BTC", "1T", "en")["ceny"] == data["ceny"]


def test_load_demo_data_creates_backdated_quant_forecasts(registered, monkeypatch):
    client, _u, _p = registered
    _patch_real_history(monkeypatch)
    from app.services import demo_data
    fixed_now = datetime(2026, 9, 29, tzinfo=timezone.utc)
    real_create = demo_data.create_demo_data
    monkeypatch.setattr("app.routers.account.create_demo_data",
                        lambda db, uid, lang: real_create(db, uid, lang, now=fixed_now))
    res = client.post("/api/account/demo-data?lang=sk", headers=csrf_headers(client))
    assert res.status_code == 200, res.text
    assert res.json()["created"] == len(demo_data.DEMO_PLAN)
    items = client.get("/api/forecast/history?page_size=100").json()["items"]
    assert len(items) == len(demo_data.DEMO_PLAN)
    assert all(i["model_used"] == "Quant (free model)" and i["forecast_data"]["demo"] for i in items)
    assert "Bezplatný" in items[0]["forecast_data"]["odovodnenie"]
    assert min(i["created_at"] for i in items) < "2026-09-02"


def test_reloading_replaces_demo_data_and_keeps_real_forecasts(registered, monkeypatch):
    from tests.conftest import signed_forecast_payload
    client, _u, _p = registered
    _patch_real_history(monkeypatch)
    client.post("/api/forecast/save", json=signed_forecast_payload(client), headers=csrf_headers(client))
    client.post("/api/account/demo-data", headers=csrf_headers(client))
    first_total = client.get("/api/forecast/history").json()["total"]
    client.post("/api/account/demo-data", headers=csrf_headers(client))
    assert client.get("/api/forecast/history").json()["total"] == first_total
    removed = client.delete("/api/account/demo-data", headers=csrf_headers(client)).json()["removed"]
    assert removed == first_total - 1
    items = client.get("/api/forecast/history").json()["items"]
    assert len(items) == 1 and not items[0]["forecast_data"].get("demo")


def test_demo_data_unavailable_market_returns_503(registered, monkeypatch):
    from app.services import market_data
    client, _u, _p = registered
    monkeypatch.setattr(market_data, "get_market_history", lambda *a, **k: (False, {}, "offline"))
    assert client.post("/api/account/demo-data", headers=csrf_headers(client)).status_code == 503


def test_demo_data_is_logged(registered, monkeypatch):
    client, _u, _p = registered
    _patch_real_history(monkeypatch)
    client.post("/api/account/demo-data", headers=csrf_headers(client))
    events = client.get("/api/account/activity").json()["events"]
    assert events[0]["action"] == "demo_data_loaded"


def _load_demo(client, monkeypatch):
    _patch_real_history(monkeypatch)
    from app.services import demo_data
    real_create = demo_data.create_demo_data
    monkeypatch.setattr("app.routers.account.create_demo_data",
                        lambda db, uid, lang: real_create(db, uid, lang, now=datetime(2026, 9, 29, tzinfo=timezone.utc)))
    assert client.post("/api/account/demo-data", headers=csrf_headers(client)).status_code == 200


def test_demo_forecasts_never_reach_the_shared_leaderboard(registered, monkeypatch):
    """Regression: retroactive demo forecasts must not inflate the global model ranking."""
    from app.routers import forecast as forecast_router
    client, _u, _p = registered
    _load_demo(client, monkeypatch)
    completed = {"status": "completed", "accuracy_pct": 99.0, "baseline_accuracy_pct": 50.0,
                 "direction_correct": True, "actual_prices": [1.0], "predicted_prices": [1.0],
                 "time_labels": [], "matures_at": ""}
    monkeypatch.setattr(forecast_router, "compute_forecast_accuracy", lambda *a, **k: completed)
    board = client.get("/api/forecast/leaderboard").json()
    assert board["providers"] == []
    entry_id = client.get("/api/forecast/history").json()["items"][0]["id"]
    assert client.get(f"/api/forecast/history/{entry_id}/accuracy").json()["status"] == "completed"
    assert client.get("/api/forecast/leaderboard").json()["providers"] == []


def test_demo_forecasts_cannot_be_shared(registered, monkeypatch):
    client, _u, _p = registered
    _load_demo(client, monkeypatch)
    entry_id = client.get("/api/forecast/history").json()["items"][0]["id"]
    assert client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).status_code == 400
