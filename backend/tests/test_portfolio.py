"""Testy pre app/routers/portfolio.py — AI analyza portfolia (mock rezim) a historia."""

from tests.conftest import anon_csrf_headers, csrf_headers


def test_analyze_portfolio_requires_auth(client):
    res = client.post("/api/portfolio/analyze", json={"provider": "gemini", "holdings": []},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 401


def test_analyze_portfolio_without_api_key_returns_mock_data(registered):
    client, _username, _password = registered
    payload = {"provider": "gemini", "holdings": [{"minca": "BTC", "mnozstvo": 0.5}], "lang": "en"}
    res = client.post("/api/portfolio/analyze", json=payload, headers=csrf_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["is_mock"] is True
    assert "odporucania" in body["data"]


def test_analyze_portfolio_empty_holdings_reports_failure(registered):
    """Prazdne portfolio nie je HTTP chyba (422) - je to platny request s
    business-logickou odpovedou success:false, aby frontend vedel zobrazit
    zrozumitelnu spravu namiesto generickej validacnej chyby."""
    client, _username, _password = registered
    res = client.post("/api/portfolio/analyze", json={"provider": "gemini", "holdings": []},
                       headers=csrf_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False


def test_reject_negative_amount(registered):
    client, _username, _password = registered
    payload = {"provider": "gemini", "holdings": [{"minca": "BTC", "mnozstvo": -5}]}
    res = client.post("/api/portfolio/analyze", json=payload, headers=csrf_headers(client))
    assert res.status_code == 422


def test_save_and_read_portfolio_history(registered):
    client, _username, _password = registered
    payload = {
        "provider": "gemini", "holdings": [{"minca": "BTC", "mnozstvo": 1}],
        "analysis_data": {"odporucania": [], "odborna_analyza": "test"}, "is_mock": True,
    }
    res = client.post("/api/portfolio/save", json=payload, headers=csrf_headers(client))
    assert res.status_code == 201
    entry_id = res.json()["id"]

    res = client.get("/api/portfolio/history")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == entry_id


def test_delete_nonexistent_portfolio_analysis_returns_404(registered):
    client, _username, _password = registered
    res = client.delete("/api/portfolio/history/999999", headers=csrf_headers(client))
    assert res.status_code == 404
