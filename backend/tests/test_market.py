"""Testy pre app/routers/market.py — verejne endpointy a community hlasovanie.

Fear&Greed/headlines/chart/coins-search volaju externe API (CoinGecko a
pod.) — v testovacom prostredi nemusia byt tieto domeny dostupne. Vsetky
tieto endpointy su navrhnute tak, aby PRI ZLYHANI externeho volania vratili
200 s `is_mock: true` namiesto chyby, takze testy overuju len tento
kontrakt (200 + ocakavany tvar odpovede), nie konkretny obsah dat."""

from tests.conftest import anon_csrf_headers, csrf_headers


def test_fear_greed_is_public_and_never_fails(client):
    res = client.get("/api/market/fear-greed")
    assert res.status_code == 200
    assert "data" in res.json()


def test_events_is_public(client):
    res = client.get("/api/market/events?lang=en")
    assert res.status_code == 200
    events = res.json()["events"]
    assert len(events) > 0
    assert "datum" in events[0] and "udalost" in events[0]


def test_prices_with_no_ids_returns_empty_without_network_call(client):
    res = client.get("/api/market/prices?ids=&vs_currency=usd")
    assert res.status_code == 200
    assert res.json()["prices"] == {}


def test_vote_requires_auth(client):
    res = client.post("/api/market/vote", json={"sentiment_vote": "Bullish"}, headers=anon_csrf_headers(client))
    assert res.status_code == 401


def test_vote_invalid_value_reports_failure(registered):
    client, _username, _password = registered
    res = client.post("/api/market/vote", json={"sentiment_vote": "ToTheMoon"}, headers=csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["success"] is False


def test_vote_and_percentages_reflect_latest_vote_only(registered):
    client, _username, _password = registered
    res = client.post("/api/market/vote", json={"sentiment_vote": "Bullish"}, headers=csrf_headers(client))
    assert res.status_code == 200

    res = client.get("/api/market/vote/mine")
    assert res.json()["sentiment_vote"] == "Bullish"

    # Pouzivatel si to rozmysli - novy hlas ma nahradit ten stary v percentages.
    client.post("/api/market/vote", json={"sentiment_vote": "Bearish"}, headers=csrf_headers(client))
    res = client.get("/api/market/vote/percentages")
    body = res.json()
    assert body["total_votes"] == 1
    assert body["Bearish"] == 100.0
    assert body["Bullish"] == 0.0
