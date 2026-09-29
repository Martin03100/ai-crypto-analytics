"""Regression tests for malformed upstream data and concurrent writes."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services import market_data
from tests.conftest import anon_csrf_headers, csrf_headers, signed_forecast_payload


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clear_caches():
    for cache in (market_data._market_chart_cache, market_data._fear_greed_cache, market_data._price_cache,
                  market_data._search_cache):
        cache._store.clear()
    yield


def test_clean_price_points_drops_invalid_pairs():
    raw = [[1, 100], [2, None], [3, "x"], [4, float("nan")], [5, -1], "bad", [6], [7, "8.5"]]
    assert market_data.clean_price_points(raw) == [[1.0, 100.0], [7.0, 8.5]]
    assert market_data.clean_price_points({"prices": []}) == []


@pytest.mark.parametrize("payload", [["not", "a", "dict"], {"prices": [[1, None]]}, {"prices": "oops"}, None])
def test_market_chart_handles_malformed_payload(monkeypatch, payload):
    monkeypatch.setattr(market_data.requests, "get", lambda *a, **k: _Resp(payload))
    ok, prices, error = market_data.get_market_chart("bitcoin", "usd", "7")
    assert ok is False and prices == [] and error


def test_market_chart_range_sanitizes_points(monkeypatch):
    monkeypatch.setattr(market_data.requests, "get",
                        lambda *a, **k: _Resp({"prices": [[1, 10], [2, None], [3, 12]]}))
    ok, prices, _ = market_data.get_market_chart_range("bitcoin", "usd", 0, 10)
    assert ok is True and prices == [[1.0, 10.0], [3.0, 12.0]]


@pytest.mark.parametrize("payload", [{"data": "abc"}, ["x"], {"data": [{"value": "999"}]}, {"data": [{"value": "n/a"}]}])
def test_fear_greed_never_raises(monkeypatch, payload):
    monkeypatch.setattr(market_data.requests, "get", lambda *a, **k: _Resp(payload))
    ok, data, _ = market_data.get_fear_greed_index(force_refresh=True)
    if ok:
        assert 0 <= data["value"] <= 100


@pytest.mark.parametrize("payload", [["x"], {"coins": "x"}, {"coins": [1, None, {"id": "btc", "symbol": "b"}]}])
def test_search_coins_never_raises(monkeypatch, payload):
    monkeypatch.setattr(market_data.requests, "get", lambda *a, **k: _Resp(payload))
    ok, results, _ = market_data.search_coins("bit")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) and r["id"] for r in results)


def test_live_prices_non_dict_body(monkeypatch):
    monkeypatch.setattr(market_data.requests, "get", lambda *a, **k: _Resp(["x"]))
    ok, data, _ = market_data.get_live_prices(["bitcoin"], "usd")
    assert ok is True and data == {}


def test_register_race_returns_400_not_500(client, monkeypatch):
    headers = anon_csrf_headers(client)
    original_commit = Session.commit
    calls = {"n": 0}

    def flaky_commit(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: users.username"))
        return original_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)
    res = client.post("/api/auth/register", json={"username": "racer", "password": "TestPass123",
                                                  "email": "racer@example.com"}, headers=headers)
    assert res.status_code == 400


def test_token_with_non_numeric_subject_is_rejected(client):
    import jwt
    from app.config import JWT_ALGORITHM, JWT_SECRET_KEY
    token = jwt.encode({"sub": "abc", "tv": 0, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                       JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_history_without_days_back_includes_old_forecasts(registered):
    client, _, _ = registered
    from app.database import SessionLocal
    from app.models import ForecastHistory
    res = client.post("/api/forecast/save", json=signed_forecast_payload(client), headers=csrf_headers(client))
    assert res.status_code == 201
    db = SessionLocal()
    try:
        row = db.get(ForecastHistory, res.json()["id"])
        row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=200)
        db.commit()
    finally:
        db.close()
    assert client.get("/api/forecast/history?days_back=30").json()["total"] == 0
    assert client.get("/api/forecast/history").json()["total"] == 1


def test_duplicate_evaluation_commit_is_ignored(registered, monkeypatch):
    client, _, _ = registered
    from app.routers import forecast as forecast_router
    created = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    res = client.post("/api/forecast/save", json=signed_forecast_payload(client, created=created),
                      headers=csrf_headers(client))
    entry_id = res.json()["id"]
    monkeypatch.setattr(forecast_router, "compute_forecast_accuracy", lambda *a, **k: {
        "status": "completed", "accuracy_pct": 90.0, "actual_prices": [101.0, 109.0], "predicted_prices": [100.0, 110.0],
        "time_labels": ["a", "b"], "matures_at": created, "direction_correct": True, "baseline_accuracy_pct": 80.0})
    original_commit = Session.commit

    def racing_commit(self):
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: forecast_evaluations.forecast_id"))

    monkeypatch.setattr(Session, "commit", racing_commit)
    res = client.get(f"/api/forecast/history/{entry_id}/accuracy")
    monkeypatch.setattr(Session, "commit", original_commit)
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


# ---------- lenient AI forecast validation ----------

import json as _json

from app.services.validators import validate_forecast_payload


def _forecast(**over):
    base = {"ceny": [100.0, 101.0, 102.0, 103.0], "casove_body": ["a", "b", "c", "d"],
            "odovodnenie": "test", "confidence_score": 70, "risk_level": "Medium"}
    base.update(over)
    return _json.dumps(base)


def test_forecast_accepts_numeric_strings_and_aliases():
    ok, data, err = validate_forecast_payload(
        _forecast(ceny=["100", "$101.5", "3 102,40", 103], confidence_score="72%", risk_level="vysoké"), 4)
    assert ok, err
    assert data["ceny"] == [100.0, 101.5, 3102.4, 103.0]
    assert data["confidence_score"] == 72.0 and data["risk_level"] == "High"


def test_forecast_resamples_slightly_short_series_and_fixes_labels():
    ok, data, err = validate_forecast_payload(_forecast(ceny=[100.0, 110.0, 120.0], casove_body=["x"]), 5)
    assert ok, err
    assert len(data["ceny"]) == 5 and data["ceny"][0] == 100.0 and data["ceny"][-1] == 120.0
    assert len(data["casove_body"]) == 5


def test_forecast_still_rejects_far_too_few_points():
    ok, _, err = validate_forecast_payload(_forecast(ceny=[100.0, 101.0], casove_body=["a", "b"]), 24)
    assert not ok and "bodov" in err


def test_forecast_tolerates_trailing_commas():
    raw = '{"ceny": [1, 2, 3,], "casove_body": ["a","b","c",], "odovodnenie": "x", "confidence_score": 0.8, "risk_level": "low",}'
    ok, data, err = validate_forecast_payload(raw, 3)
    assert ok, err
    assert data["confidence_score"] == 80.0 and data["risk_level"] == "Low"


def test_gemini_retries_without_thinking_config(monkeypatch):
    import sys
    import types as pytypes
    from app.services import ai_engine

    calls = []

    class _Models:
        def generate_content(self, model, contents, config):
            calls.append(config)
            if config.get("thinking_config") is not None:
                raise RuntimeError("400 INVALID_ARGUMENT: Thinking level is not supported for this model.")
            return pytypes.SimpleNamespace(text='{"ok": 1}')

    class _Client:
        def __init__(self, **kwargs):
            self.models = _Models()

    fake_types = pytypes.SimpleNamespace(
        HttpOptions=lambda **k: k, ThinkingConfig=lambda **k: k, GenerateContentConfig=lambda **k: k)
    genai_mod = pytypes.ModuleType("google.genai")
    genai_mod.Client = _Client
    genai_mod.types = fake_types
    google_mod = pytypes.ModuleType("google")
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    ok, text, err = ai_engine._call_gemini("prompt", "key")
    assert ok, err
    assert len(calls) == 2 and "thinking_config" not in calls[1]
