"""Market events calendar and AI -> statistical model fallback."""

from datetime import date

from tests.conftest import csrf_headers
from tests.test_quant import _patch_history, _series


def test_events_come_from_real_calendar_and_are_upcoming_only():
    from app.services.market_data import get_upcoming_market_events
    events = get_upcoming_market_events("en", today=date(2026, 9, 29))
    assert [e["datum"] for e in events] == ["14.10.2026", "28.10.2026", "10.11.2026", "09.12.2026", "10.12.2026"]
    assert events[1]["udalost"].startswith("FOMC")
    assert "CPI" in events[0]["udalost"]


def test_events_include_today_and_are_localized():
    from app.services.market_data import get_upcoming_market_events
    events = get_upcoming_market_events("sk", today=date(2026, 10, 28), limit=1)
    assert events == [{"datum": "28.10.2026", "udalost": "Rozhodnutie FOMC o úrokových sadzbách (Fed)", "typ": "Makro"}]


def test_events_empty_after_calendar_ends():
    from app.services.market_data import get_upcoming_market_events
    assert get_upcoming_market_events("en", today=date(2030, 1, 1)) == []


def test_events_are_not_relative_to_today():
    """Regression: events used to be 'today + N days', so FOMC was always 3 days away."""
    from app.services.market_data import get_upcoming_market_events
    a = get_upcoming_market_events("en", today=date(2026, 9, 29))
    b = get_upcoming_market_events("en", today=date(2026, 9, 30))
    assert a == b


def _fail_ai(monkeypatch, error="Gemini API chyba: 429 RESOURCE_EXHAUSTED"):
    from app.services import ai_engine
    monkeypatch.setattr(ai_engine, "_build_market_context", lambda coin: (None, []))
    monkeypatch.setattr(ai_engine, "call_ai_provider", lambda p, prompt, k: (False, "", error))


def test_ai_failure_falls_back_to_quant_model(monkeypatch):
    from app.services import ai_engine
    _fail_ai(monkeypatch)
    _patch_history(monkeypatch, _series())
    result = ai_engine.get_coin_forecast("gemini", "BTC", "1T", "fake-key", lang="en")
    assert result.success and result.is_mock is False
    assert result.provider_used == "quant"
    assert "429" in result.error_message
    assert len(result.data["ceny"]) == 7


def test_ai_failure_uses_sample_data_only_when_quant_also_fails(monkeypatch):
    from app.services import ai_engine, market_data
    _fail_ai(monkeypatch)
    monkeypatch.setattr(market_data, "get_market_history", lambda *a, **k: (False, {}, "offline"))
    result = ai_engine.get_coin_forecast("gemini", "BTC", "1T", "fake-key", lang="en")
    assert result.success and result.is_mock is True and result.provider_used is None


def test_fallback_forecast_is_signed_and_saved_as_quant_only(registered, monkeypatch):
    from app.routers import forecast as forecast_router
    client, _u, _p = registered
    _fail_ai(monkeypatch)
    _patch_history(monkeypatch, _series())
    monkeypatch.setattr(forecast_router, "get_decrypted_api_key", lambda db, uid, provider: "fake-key")
    body = client.post("/api/forecast", json={"provider": "gemini", "coin": "BTC", "horizon": "1T", "lang": "en"},
                       headers=csrf_headers(client)).json()
    assert body["provider_used"] == "quant" and body["is_mock"] is False and body["data"]["podpis"]

    as_gemini = client.post("/api/forecast/save", json={"provider": "gemini", "coin": "BTC", "horizon": "1T",
                                                        "forecast_data": body["data"], "is_mock": False},
                            headers=csrf_headers(client))
    assert as_gemini.status_code == 400
    as_quant = client.post("/api/forecast/save", json={"provider": "quant", "coin": "BTC", "horizon": "1T",
                                                       "forecast_data": body["data"], "is_mock": False},
                           headers=csrf_headers(client))
    assert as_quant.status_code == 201 and as_quant.json()["model_used"] == "Quant (free model)"
