"""Forecast API tests."""

from tests.conftest import anon_csrf_headers, csrf_headers, signed_forecast_payload


def test_generate_forecast_requires_auth(client):
    res = client.post("/api/forecast", json={"provider": "gemini", "coin": "BTC", "horizon": "1T"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 401


def test_generate_forecast_without_api_key_returns_mock_data(registered):
    client, _username, _password = registered
    res = client.post("/api/forecast", json={"provider": "gemini", "coin": "BTC", "horizon": "1T", "lang": "en"},
                       headers=csrf_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["is_mock"] is True
    assert "ceny" in body["data"] and "casove_body" in body["data"]
    assert "SAMPLE DATA" in body["data"]["odovodnenie"]


def test_save_and_read_forecast_history(registered):
    client, _username, _password = registered
    payload = {
        "provider": "gemini", "coin": "BTC", "horizon": "1T", "is_mock": True,
        "forecast_data": {"ceny": [1, 2, 3], "casove_body": ["d1", "d2", "d3"], "odovodnenie": "test"},
    }
    res = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))
    assert res.status_code == 201
    entry_id = res.json()["id"]

    res = client.get("/api/forecast/history")
    assert res.status_code == 200
    history = res.json()
    assert history["total"] == 1
    assert len(history["items"]) == 1
    assert history["items"][0]["id"] == entry_id


def test_delete_nonexistent_forecast_returns_404(registered):
    client, _username, _password = registered
    res = client.delete("/api/forecast/history/999999", headers=csrf_headers(client))
    assert res.status_code == 404


def test_delete_own_forecast_succeeds(registered):
    client, _username, _password = registered
    payload = {
        "provider": "gemini", "coin": "ETH", "horizon": "1M", "is_mock": True,
        "forecast_data": {"ceny": [1], "casove_body": ["d1"], "odovodnenie": "test"},
    }
    res = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))
    entry_id = res.json()["id"]

    res = client.delete(f"/api/forecast/history/{entry_id}", headers=csrf_headers(client))
    assert res.status_code == 200

    res = client.get("/api/forecast/history")
    body = res.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_forecast_history_pagination(registered):
    client, _username, _password = registered
    for i in range(5):
        payload = {
            "provider": "gemini", "coin": f"COIN{i}", "horizon": "1T", "is_mock": True,
            "forecast_data": {"ceny": [1], "casove_body": ["d1"], "odovodnenie": "test"},
        }
        client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))

    res = client.get("/api/forecast/history?page=1&page_size=2")
    body = res.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["items"][0]["crypto_symbol"] == "COIN4"

    res = client.get("/api/forecast/history?page=3&page_size=2")
    body = res.json()
    assert body["total"] == 5
    assert len(body["items"]) == 1


def test_forecast_accuracy_requires_auth(client):
    res = client.get("/api/forecast/history/1/accuracy")
    assert res.status_code == 401


def test_forecast_accuracy_404_for_nonexistent_entry(registered):
    client, _username, _password = registered
    res = client.get("/api/forecast/history/999999/accuracy")
    assert res.status_code == 404


def test_forecast_accuracy_pending_for_recent_forecast(registered):
    client, _username, _password = registered
    payload = signed_forecast_payload(client, prices=(100, 105), horizon="1T")
    res = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))
    assert res.status_code == 201, res.text
    entry_id = res.json()["id"]

    res = client.get(f"/api/forecast/history/{entry_id}/accuracy")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pending"
    assert body["accuracy_pct"] is None
    assert body["predicted_prices"] == [100, 105]


def test_forecast_accuracy_cannot_be_read_by_another_user(registered, client):
    owner_client, _username, _password = registered
    payload = {
        "provider": "gemini", "coin": "BTC", "horizon": "1T", "is_mock": True,
        "forecast_data": {"ceny": [100], "casove_body": ["d1"], "odovodnenie": "test"},
    }
    res = owner_client.post("/api/forecast/save", json=payload, headers=csrf_headers(owner_client))
    entry_id = res.json()["id"]

    other_reg = client.post("/api/auth/register", json={
        "username": "inyuzivatel", "password": "heslo12345", "email": "iny@example.com",
    }, headers=anon_csrf_headers(client))
    assert other_reg.status_code == 201

    res = client.get(f"/api/forecast/history/{entry_id}/accuracy")
    assert res.status_code == 404


def test_estimate_forecast_cost_without_api_key_returns_mock(registered):
    client, _username, _password = registered
    res = client.post("/api/forecast/estimate-cost", json={"provider": "gemini", "coin": "BTC", "horizon": "1T"},
                       headers=csrf_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["is_mock"] is True
    assert body["estimated_cost_usd"] == 0.0


def test_forecast_accuracy_not_tracked_for_mock_forecast(registered):
    client, _username, _password = registered
    payload = {
        "provider": "gemini", "coin": "BTC", "horizon": "24h", "is_mock": True,
        "forecast_data": {"ceny": [100, 105], "casove_body": ["d1", "d2"], "odovodnenie": "test"},
    }
    entry_id = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).json()["id"]
    body = client.get(f"/api/forecast/history/{entry_id}/accuracy").json()
    assert body["status"] == "mock"
    assert body["accuracy_pct"] is None


def test_news_sentiment_rejects_too_many_titles(registered):
    client, _username, _password = registered
    res = client.post("/api/market/news-sentiment",
                       json={"provider": "gemini", "titles": [f"titulok {i}" for i in range(21)]},
                       headers=csrf_headers(client))
    assert res.status_code == 422



def test_rate_limit_cannot_be_bypassed_by_changing_path_id(registered):
    client, _username, _password = registered
    codes = [client.get(f"/api/forecast/history/{i}/accuracy").status_code for i in range(1, 26)]
    assert 429 in codes



def test_forecast_rejects_invalid_horizon_and_too_long_coin(registered):
    client, _username, _password = registered
    base = {"provider": "gemini", "is_mock": True,
            "forecast_data": {"ceny": [1], "casove_body": ["d1"], "odovodnenie": "x"}}
    assert client.post("/api/forecast/save", json={**base, "coin": "BTC", "horizon": "5 rokov"},
                       headers=csrf_headers(client)).status_code == 422
    assert client.post("/api/forecast/save", json={**base, "coin": "X" * 40, "horizon": "1T"},
                       headers=csrf_headers(client)).status_code == 422



def _save_real_forecast(client, prices=(100.0, 110.0), is_mock=False):
    if is_mock:
        payload = {"provider": "gemini", "coin": "BTC", "horizon": "24h", "is_mock": True,
                   "forecast_data": {"ceny": list(prices), "casove_body": ["a", "b"], "odovodnenie": "test"}}
    else:
        payload = signed_forecast_payload(client, prices=prices, horizon="24h")
    res = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_tip_challenge_and_leaderboard(registered, monkeypatch):
    from app.routers import forecast as forecast_router
    client, _u, _p = registered
    entry_id = _save_real_forecast(client)
    assert client.get(f"/api/forecast/history/{entry_id}/accuracy").json()["can_tip"] is True
    assert client.post(f"/api/forecast/history/{entry_id}/tip", json={"price": 108}, headers=csrf_headers(client)).status_code == 200
    assert client.post(f"/api/forecast/history/{entry_id}/tip", json={"price": 109}, headers=csrf_headers(client)).status_code == 400
    monkeypatch.setattr(forecast_router, "compute_forecast_accuracy", lambda *a, **k: {
        "status": "completed", "accuracy_pct": 97.0, "predicted_prices": [100.0, 110.0], "actual_prices": [101.0, 107.0],
        "time_labels": ["a", "b"], "matures_at": "x", "baseline_accuracy_pct": 95.0, "direction_correct": True})
    body = client.get(f"/api/forecast/history/{entry_id}/accuracy").json()
    assert body["tip_outcome"] == "win" and body["can_tip"] is False
    board = client.get("/api/forecast/leaderboard").json()
    assert board["providers"][0]["evaluated"] == 1 and board["providers"][0]["direction_hit_pct"] == 100.0
    assert board["challenge"]["you"]["wins"] == 1


def test_tip_rejected_for_mock_forecast(registered):
    client, _u, _p = registered
    entry_id = _save_real_forecast(client, is_mock=True)
    assert client.post(f"/api/forecast/history/{entry_id}/tip", json={"price": 108}, headers=csrf_headers(client)).status_code == 400



def test_bulk_delete_only_removes_own_forecasts(registered, client):
    owner, _u, _p = registered
    ids = [_save_real_forecast(owner) for _ in range(3)]
    res = owner.post("/api/forecast/history/bulk-delete", json={"ids": ids[:2] + [999999]}, headers=csrf_headers(owner))
    assert res.status_code == 200 and res.json()["deleted"] == 2
    assert owner.get("/api/forecast/history").json()["total"] == 1
    assert owner.post("/api/forecast/history/bulk-delete", json={"ids": []}, headers=csrf_headers(owner)).status_code == 422


def test_save_rejects_unsigned_real_forecast(registered):
    client, _u, _p = registered
    payload = signed_forecast_payload(client)
    payload["forecast_data"].pop("podpis")
    res = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))
    assert res.status_code == 400


def test_save_rejects_tampered_prices_or_coin(registered):
    client, _u, _p = registered
    payload = signed_forecast_payload(client, prices=(100, 110), coin="BTC")
    tampered = {**payload, "forecast_data": {**payload["forecast_data"], "ceny": [100.0, 999.0]}}
    assert client.post("/api/forecast/save", json=tampered, headers=csrf_headers(client)).status_code == 400
    other_coin = {**payload, "coin": "ETH"}
    assert client.post("/api/forecast/save", json=other_coin, headers=csrf_headers(client)).status_code == 400
    assert client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).status_code == 201


def test_signature_cannot_be_reused_by_another_user(registered, client):
    owner, _u, _p = registered
    payload = signed_forecast_payload(owner)
    owner.cookies.clear()
    res = owner.post("/api/auth/register", json={"username": "druhy_user", "password": "heslo12345", "email": "d@example.com"})
    assert res.status_code == 201
    res = owner.post("/api/forecast/save", json=payload, headers=csrf_headers(owner))
    assert res.status_code == 400


def test_save_rejects_unknown_provider(registered):
    client, _u, _p = registered
    payload = signed_forecast_payload(client, provider="gemini")
    payload["provider"] = "TotallyFakeAI"
    assert client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).status_code == 400


def test_accuracy_survives_corrupted_prices(registered, monkeypatch):
    from app.services import ai_engine
    client, _u, _p = registered
    payload = signed_forecast_payload(client, prices=(1, 2), horizon="24h")
    entry_id = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).json()["id"]
    from app.database import SessionLocal
    from app.models import ForecastHistory
    import json as _json
    from datetime import datetime, timedelta, timezone
    db = SessionLocal()
    try:
        row = db.get(ForecastHistory, entry_id)
        data = _json.loads(row.forecast_json)
        data["ceny"] = ["x", "y"]
        row.forecast_json = _json.dumps(data)
        row.created_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(ai_engine.market_data, "get_market_chart_range", lambda *a, **k: (True, [[0, 100.0], [10**13, 101.0]], None))
    res = client.get(f"/api/forecast/history/{entry_id}/accuracy")
    assert res.status_code == 200
    assert res.json()["status"] == "unavailable"


def test_leaderboard_flags_low_sample_and_ranks_reliable_first(registered):
    from app.database import SessionLocal
    from app.models import ForecastEvaluation
    client, _u, _p = registered
    db = SessionLocal()
    try:
        for i in range(6):
            db.add(ForecastEvaluation(forecast_id=i + 1, user_id=1, provider="A", coin="BTC", timeframe="1T",
                                      accuracy_pct=90.0, baseline_accuracy_pct=95.0, direction_correct=i % 2 == 0,
                                      actual_final_price=1.0))
        db.add(ForecastEvaluation(forecast_id=100, user_id=1, provider="B", coin="BTC", timeframe="1T",
                                  accuracy_pct=99.0, baseline_accuracy_pct=95.0, direction_correct=True,
                                  actual_final_price=1.0))
        db.commit()
    finally:
        db.close()
    board = client.get("/api/forecast/leaderboard").json()
    names = [p["provider"] for p in board["providers"]]
    assert names == ["A", "B"], "a provider with enough samples must rank above one with a single forecast"
    assert board["providers"][0]["low_sample"] is False and board["providers"][1]["low_sample"] is True
