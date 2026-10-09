"""When a source or an AI fails, users see that it failed — never invented ratings, headlines or values."""

from __future__ import annotations

from app.routers import market as market_router
from app.services import ai_engine, free_digest
from tests.conftest import csrf_headers

HOLDINGS = [{"minca": "BTC", "mnozstvo": 1}, {"minca": "DOGE", "mnozstvo": 100}, {"minca": "XYZ", "mnozstvo": 5}]


def test_sample_portfolio_without_a_key_rates_nothing():
    result = ai_engine.get_portfolio_analysis("gemini", HOLDINGS, None, "en")
    assert result.success and result.is_mock
    assert {r["akcia"] for r in result.data["odporucania"]} == {"HOLD"}
    assert all("not assessed" in r["dovod"] for r in result.data["odporucania"])
    sectors = result.data["sektorova_alokacia"]
    assert sectors["L1/L2"] == sectors["Memes"] == sectors["Other"] == 33.3 and sectors["DeFi"] == 0.0


def test_a_failed_ai_call_is_an_error_not_a_sample(monkeypatch):
    monkeypatch.setattr(ai_engine, "_build_portfolio_context", lambda holdings: (None, []))
    monkeypatch.setattr(ai_engine, "call_ai_provider", lambda *a: (False, "", "Gemini API chyba: 503"))
    result = ai_engine.get_portfolio_analysis("gemini", HOLDINGS, "key", "en")
    assert result.success is False and result.data is None and "503" in result.error_message

    monkeypatch.setattr(ai_engine, "market_signals_block", lambda *a: None)
    news = ai_engine.get_news_sentiment_summary("gemini", ["Bitcoin rises"], "key", "en")
    assert news.success is False and news.data is None
    assert ai_engine.get_news_sentiment_summary("gemini", ["Bitcoin rises"], None, "en").success is False


def test_morning_overview_without_a_key_uses_live_data(monkeypatch):
    monkeypatch.setattr(free_digest.market_data, "get_coin_markets", lambda ids: (True, {
        "bitcoin": {"price_change_percentage_24h_in_currency": 2.345},
        "ethereum": {"price_change_percentage_24h_in_currency": -1.2}}, None))
    monkeypatch.setattr(free_digest.signals, "latest", lambda symbol: {"items": [
        {"key": "funding", "display": "+0.0450% / 8h", "tone": "bearish"}]})
    result = ai_engine.get_daily_digest("gemini", 64, "Greed", [], None, "sk")
    assert result.success and result.is_mock is False and result.provider_used == "free"
    assert "64/100 (chamtivosť)" in result.data["zhrnutie"] and "BTC +2.3 %" in result.data["zhrnutie"]
    assert any("Funding" in point for point in result.data["kluceve_body"])
    assert "UKÁŽKOV" not in str(result.data) and "MOCK" not in str(result.data)
    unknown = free_digest.build(None, None, "en")
    assert "Fear & Greed" not in unknown["zhrnutie"]       # never a made-up 50


def test_unavailable_sources_are_reported_not_faked(client, monkeypatch):
    monkeypatch.setattr(market_router, "get_fear_greed_index", lambda force_refresh=False: (False, None, "down"))
    monkeypatch.setattr(market_router, "get_crypto_headlines", lambda limit=8: (False, [], "down"))
    fg = client.get("/api/market/fear-greed").json()
    assert fg["data"] is None and fg["is_mock"] is False
    news = client.get("/api/market/headlines").json()
    assert news["headlines"] == [] and news["error_message"]


def test_portfolio_endpoint_reports_ai_failure(registered, monkeypatch):
    client, _, _ = registered
    from app.routers import portfolio as portfolio_router
    monkeypatch.setattr(portfolio_router, "get_decrypted_api_key", lambda *a: "key")
    monkeypatch.setattr(ai_engine, "_build_portfolio_context", lambda holdings: (None, []))
    monkeypatch.setattr(ai_engine, "call_ai_provider", lambda *a: (False, "", "Gemini API chyba: quota"))
    res = client.post("/api/portfolio/analyze", json={"provider": "gemini", "holdings": HOLDINGS[:1]},
                      headers=csrf_headers(client))
    assert res.status_code == 200 and res.json()["success"] is False
