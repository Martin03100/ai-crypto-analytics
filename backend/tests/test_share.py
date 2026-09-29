"""Public share links for saved forecasts."""

from tests.conftest import anon_csrf_headers, csrf_headers, signed_forecast_payload


def _save(client, **kwargs):
    res = client.post("/api/forecast/save", json=signed_forecast_payload(client, **kwargs), headers=csrf_headers(client))
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_share_creates_stable_token_and_public_view_hides_signature(registered):
    client, _u, _p = registered
    entry_id = _save(client)
    token = client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).json()["share_token"]
    again = client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).json()["share_token"]
    assert token == again and len(token) >= 30

    client.cookies.clear()  # the public view must work without login
    res = client.get(f"/api/public/forecasts/{token}")
    assert res.status_code == 200
    body = res.json()
    assert body["coin"] == "BTC" and body["horizon"] == "1T" and body["forecast_data"]["ceny"] == [100.0, 110.0]
    assert "podpis" not in body["forecast_data"]
    assert "user" not in str(body).lower() and "testuser1" not in str(body)


def test_history_lists_share_token(registered):
    client, _u, _p = registered
    entry_id = _save(client)
    token = client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).json()["share_token"]
    items = client.get("/api/forecast/history").json()["items"]
    assert items[0]["share_token"] == token


def test_revoked_link_stops_working(registered):
    client, _u, _p = registered
    entry_id = _save(client)
    token = client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).json()["share_token"]
    assert client.delete(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).status_code == 200
    assert client.get(f"/api/public/forecasts/{token}").status_code == 404


def test_deleted_forecast_link_stops_working(registered):
    client, _u, _p = registered
    entry_id = _save(client)
    token = client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).json()["share_token"]
    client.delete(f"/api/forecast/history/{entry_id}", headers=csrf_headers(client))
    assert client.get(f"/api/public/forecasts/{token}").status_code == 404


def test_mock_forecast_cannot_be_shared(registered):
    client, _u, _p = registered
    payload = {"provider": "gemini", "coin": "BTC", "horizon": "1T", "is_mock": True,
               "forecast_data": {"ceny": [1, 2], "casove_body": ["a", "b"], "odovodnenie": "x"}}
    entry_id = client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).json()["id"]
    assert client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).status_code == 400


def test_cannot_share_someone_elses_forecast(registered):
    client, _u, _p = registered
    entry_id = _save(client)
    client.post("/api/auth/logout", headers=csrf_headers(client))
    client.cookies.clear()
    client.post("/api/auth/register", json={"username": "intruder", "password": "IntruderPass1", "email": "i@example.com"},
                headers=anon_csrf_headers(client))
    assert client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).status_code == 404


def test_invalid_tokens_are_rejected(client):
    assert client.get("/api/public/forecasts/short").status_code == 422
    assert client.get("/api/public/forecasts/" + "x" * 40).status_code == 404
    assert client.get("/api/public/forecasts/%27%20OR%201=1%20--%20aaaaaaaaaaaa").status_code == 422


def test_sharing_is_logged(registered):
    client, _u, _p = registered
    entry_id = _save(client)
    client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client))
    client.delete(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client))
    actions = [e["action"] for e in client.get("/api/account/activity").json()["events"]]
    assert actions[:2] == ["share_revoked", "share_created"]
