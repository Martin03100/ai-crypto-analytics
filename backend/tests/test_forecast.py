"""Testy pre app/routers/forecast.py — AI predikcia (mock rezim) a historia."""

from tests.conftest import anon_csrf_headers, csrf_headers


def test_generate_forecast_requires_auth(client):
    res = client.post("/api/forecast", json={"provider": "gemini", "coin": "BTC", "horizon": "1T"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 401


def test_generate_forecast_without_api_key_returns_mock_data(registered):
    """Bez pripojeneho API klucu appka NIKDY nevrati chybu - vzdy vygeneruje
    mock predikciu (is_mock: true), aby appka bola pouzitelna aj bez
    vlastneho AI klucu."""
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
    """Ulozi 5 predikcii a overi, ze page_size=2 vrati spravne stranky aj
    spravny celkovy pocet (total), aj ked na aktualnu stranku nesedia
    vsetky zaznamy naraz - predtym pevny .limit(100) by starsie zaznamy
    proste "stratil" bez akehokolvek naznaku, ze existuju dalsie."""
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
    # Najnovsi ulozeny zaznam (COIN4) ma byt prvy (zoradene od najnovsieho).
    assert body["items"][0]["crypto_symbol"] == "COIN4"

    res = client.get("/api/forecast/history?page=3&page_size=2")
    body = res.json()
    assert body["total"] == 5
    assert len(body["items"]) == 1  # posledna, neuplna stranka


def test_forecast_accuracy_requires_auth(client):
    res = client.get("/api/forecast/history/1/accuracy")
    assert res.status_code == 401


def test_forecast_accuracy_404_for_nonexistent_entry(registered):
    client, _username, _password = registered
    res = client.get("/api/forecast/history/999999/accuracy")
    assert res.status_code == 404


def test_forecast_accuracy_pending_for_recent_forecast(registered):
    """Predikcia ulozena prave teraz s horizontom "1T" (1 tyzden) - realne
    data na porovnanie este neexistuju, status musi byt "pending"."""
    client, _username, _password = registered
    payload = {
        "provider": "gemini", "coin": "BTC", "horizon": "1T", "is_mock": False,
        "forecast_data": {"ceny": [100, 105], "casove_body": ["d1", "d2"], "odovodnenie": "test"},
    }
    res = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client))
    entry_id = res.json()["id"]

    res = client.get(f"/api/forecast/history/{entry_id}/accuracy")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pending"
    assert body["accuracy_pct"] is None
    assert body["predicted_prices"] == [100, 105]


def test_forecast_accuracy_cannot_be_read_by_another_user(registered, client):
    """Presnost cudzej ulozenej predikcie sa nikdy nesmie dat nahliadnut cez
    len uhadnute ID zaznamu - rovnaky princip ako pri mazani cudzej analyzy."""
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
    """Bez pripojeneho klucu by realne volanie bolo zadarmo (mock rezim) -
    odhad sa preto vobec nepocita, len sa vrati is_mock=true."""
    client, _username, _password = registered
    res = client.post("/api/forecast/estimate-cost", json={"provider": "gemini", "coin": "BTC", "horizon": "1T"},
                       headers=csrf_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["is_mock"] is True
    assert body["estimated_cost_usd"] == 0.0


def test_forecast_accuracy_not_tracked_for_mock_forecast(registered):
    """Ukazkove (mock) predikcie su z demonstracneho modelu, nie z AI - ich
    "presnost" by bola nezmyselne, zavadzajuce cislo."""
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
    """Limit sa pocita podla sablony routy - prechadzanie roznych ID
    (/history/1/accuracy, /history/2/accuracy...) ho nesmie obist."""
    client, _username, _password = registered
    codes = [client.get(f"/api/forecast/history/{i}/accuracy").status_code for i in range(1, 26)]
    assert 429 in codes



def test_forecast_rejects_invalid_horizon_and_too_long_coin(registered):
    """Bez validacie by Postgres (Neon) pri ulozeni dlhsej hodnoty vratil 500."""
    client, _username, _password = registered
    base = {"provider": "gemini", "is_mock": True,
            "forecast_data": {"ceny": [1], "casove_body": ["d1"], "odovodnenie": "x"}}
    assert client.post("/api/forecast/save", json={**base, "coin": "BTC", "horizon": "5 rokov"},
                       headers=csrf_headers(client)).status_code == 422
    assert client.post("/api/forecast/save", json={**base, "coin": "X" * 40, "horizon": "1T"},
                       headers=csrf_headers(client)).status_code == 422



def _save_real_forecast(client, prices=(100.0, 110.0), is_mock=False):
    payload = {"provider": "gemini", "coin": "BTC", "horizon": "24h", "is_mock": is_mock,
               "forecast_data": {"ceny": list(prices), "casove_body": ["a", "b"], "odovodnenie": "test"}}
    return client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).json()["id"]


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
    assert body["tip_outcome"] == "win" and body["can_tip"] is False  # |108-107| < |110-107|
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
