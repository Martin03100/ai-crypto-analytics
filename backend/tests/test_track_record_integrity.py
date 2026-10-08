"""The public track record cannot be steered: no late or repeated saves, deleted forecasts still count."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import ForecastEvaluation, ForecastHistory
from app.routers import forecast as forecast_router
from app.services.quant_engine import direction_confidence
from app.services.stats import wilson_interval
from tests.conftest import csrf_headers, signed_forecast_payload


def _save(client, **kwargs):
    return client.post("/api/forecast/save", json=signed_forecast_payload(client, **kwargs), headers=csrf_headers(client))


def _completed(prices=(101.0, 109.0), correct=True):
    return {"status": "completed", "accuracy_pct": 92.0, "baseline_accuracy_pct": 90.0, "direction_correct": correct,
            "actual_prices": list(prices), "predicted_prices": [100.0, 110.0], "time_labels": ["a", "b"],
            "matures_at": "", "start_price": 100.0}


def _score_all(monkeypatch, correct=True):
    monkeypatch.setattr(forecast_router, "compute_forecast_accuracy", lambda *a, **k: _completed(correct=correct))
    db = SessionLocal()
    try:
        forecast_router._evaluate_pending(db, limit=10)
    finally:
        db.close()


def _age(entry_id: int, days: int = 10) -> None:
    db = SessionLocal()
    try:
        row = db.get(ForecastHistory, entry_id)
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        db.commit()
    finally:
        db.close()


def _public_total(client) -> int:
    return client.get("/api/public/track-record").json()["totals"]["evaluated"]


def test_the_same_generated_forecast_can_be_saved_only_once(registered):
    client, _, _ = registered
    payload = signed_forecast_payload(client)
    assert client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).status_code == 201
    again = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))
    assert again.status_code == 409
    assert "už je uložená" in again.json()["detail"]
    assert client.get("/api/forecast/history").json()["total"] == 1


@pytest.mark.strict_save_window
def test_a_forecast_must_be_saved_within_15_minutes(registered):
    client, _, _ = registered
    old = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
    res = _save(client, created=old)
    assert res.status_code == 400
    assert "staršia ako 15 minút" in res.json()["detail"]
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    assert _save(client, created=future).status_code == 400
    fresh = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert _save(client, created=fresh).status_code == 201


def test_deleting_an_unscored_forecast_hides_it_but_it_is_still_scored(registered, monkeypatch):
    client, _, _ = registered
    entry_id = _save(client).json()["id"]
    _age(entry_id)
    assert client.delete(f"/api/forecast/history/{entry_id}", headers=csrf_headers(client)).status_code == 200
    assert client.get("/api/forecast/history").json()["total"] == 0
    assert client.get(f"/api/forecast/history/{entry_id}/accuracy").status_code == 404
    assert "BTC" not in client.get("/api/account/export/forecasts.csv").text

    _score_all(monkeypatch, correct=False)
    db = SessionLocal()
    try:
        assert db.get(ForecastHistory, entry_id) is None            # removed once scored
        ev = db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == entry_id).one()
        assert ev.direction_correct is False and ev.start_price == 100.0
    finally:
        db.close()
    assert _public_total(client) == 1
    # Being deleted, the result did not notify the user.
    items = client.get("/api/account/notifications").json()["items"]
    assert not any(n["kind"] == "forecast_evaluated" for n in items)


def test_deleting_a_scored_forecast_keeps_its_public_result(registered, monkeypatch):
    client, _, _ = registered
    entry_id = _save(client).json()["id"]
    _age(entry_id)
    _score_all(monkeypatch)
    assert _public_total(client) == 1
    res = client.post("/api/forecast/history/bulk-delete", json={"ids": [entry_id]}, headers=csrf_headers(client))
    assert res.json()["deleted"] == 1
    assert client.get("/api/forecast/history").json()["total"] == 0
    assert _public_total(client) == 1
    from app.routers import public
    public._insights_cache.clear()
    try:
        insights = client.get("/api/public/accuracy-insights").json()
    finally:
        public._insights_cache.clear()       # cached for 10 minutes; other tests build their own data
    assert insights["regimes"], "the evaluation keeps its own start price for the market-regime view"


def test_sample_forecasts_are_deleted_outright(registered):
    client, _, _ = registered
    payload = {"provider": "gemini", "coin": "BTC", "horizon": "1T", "is_mock": True,
               "forecast_data": {"ceny": [1.0, 2.0], "casove_body": ["a", "b"], "odovodnenie": "x"}}
    entry_id = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).json()["id"]
    client.delete(f"/api/forecast/history/{entry_id}", headers=csrf_headers(client))
    db = SessionLocal()
    try:
        assert db.get(ForecastHistory, entry_id) is None
    finally:
        db.close()


def test_deleting_the_account_keeps_scored_results_anonymously(registered, monkeypatch):
    client, _, password = registered
    entry_id = _save(client).json()["id"]
    _age(entry_id)
    _score_all(monkeypatch)
    res = client.post("/api/account/delete", json={"password": password}, headers=csrf_headers(client))
    assert res.status_code == 200
    db = SessionLocal()
    try:
        ev = db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == entry_id).one()
        assert ev.user_id == 0
    finally:
        db.close()
    assert _public_total(client) == 1


def test_tip_window_is_short_for_short_horizons(registered):
    assert forecast_router.tip_window("4h") == timedelta(minutes=24)
    assert forecast_router.tip_window("24h") == timedelta(hours=2)
    assert forecast_router.tip_window("1T") == timedelta(hours=2)
    client, _, _ = registered
    entry_id = _save(client, horizon="4h").json()["id"]
    db = SessionLocal()
    try:
        row = db.get(ForecastHistory, entry_id)
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
        db.commit()
    finally:
        db.close()
    res = client.post(f"/api/forecast/history/{entry_id}/tip", json={"price": 105.0}, headers=csrf_headers(client))
    assert res.status_code == 400
    assert "uplynul" in res.json()["detail"]


def test_hit_rates_come_with_a_confidence_interval(registered, monkeypatch):
    client, _, _ = registered
    for _ in range(3):
        _age(_save(client).json()["id"])
    _score_all(monkeypatch)
    data = client.get("/api/public/track-record").json()
    assert data["reliable_sample"] == 30
    assert data["totals"]["direction_ci"] == list(wilson_interval(3, 3))
    provider = data["providers"][0]
    assert provider["reliable"] is False
    assert provider["avg_error_pct"] == 8.0
    assert provider["direction_ci"][0] < provider["direction_hit_pct"] <= provider["direction_ci"][1]
    assert data["recent"][0]["error_pct"] == 8.0


def test_wilson_interval_is_wide_for_few_forecasts():
    low, high = wilson_interval(3, 5)
    assert 20 < low < 25 and 85 < high < 90
    assert wilson_interval(0, 0) is None


def test_quant_confidence_is_a_direction_probability():
    assert direction_confidence(100.0, 100.0, 0.01, 24) == 50.0
    small = direction_confidence(100.0, 100.5, 0.01, 24)
    assert 50 < small < 60
    assert direction_confidence(100.0, 99.5, 0.01, 24) == small     # same distance down, same confidence
