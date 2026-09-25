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
    assert "MOCK DATA" in body["data"]["odovodnenie"]


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
        "provider": "gemini", "coin": "BTC", "horizon": "1T", "is_mock": True,
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
