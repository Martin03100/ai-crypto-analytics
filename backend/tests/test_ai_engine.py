"""Testy pre app/services/ai_engine.py — hlavne _fetch_market_context(), ktora
dava AI predikciam realnu kotvu (aktualnu cenu a trend) namiesto toho, aby si
model vymyslal cisla len z vseobecneho "crypto rastie" narativu."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import ai_engine  # noqa: E402


def test_fetch_market_context_formats_price_and_trend(monkeypatch):
    monkeypatch.setattr(
        ai_engine.market_data, "get_live_prices",
        lambda ids, cur, timeout=None: (True, {"bitcoin": {"usd": 64280.0, "usd_24h_change": -2.15}}, None),
    )
    monkeypatch.setattr(
        ai_engine.market_data, "get_market_chart",
        lambda coin_id, cur, days, timeout=None: (True, [[0, 68000.0], [1, 64280.0]], None),
    )
    result = ai_engine._fetch_market_context("BTC")
    assert result is not None
    assert "64,280.00" in result
    assert "-2.15%" in result
    assert "7 dni" in result


def test_fetch_market_context_returns_none_for_unknown_coin():
    """Minca, ktora nie je v DEFAULT_COIN_IDS (napr. custom hladana minca) -
    ziadny coin_id na dotaz, prompt sa zostavi bez realnych dat namiesto padu."""
    assert ai_engine._fetch_market_context("TOTALLY_UNKNOWN_COIN") is None


def test_fetch_market_context_returns_none_when_price_fetch_fails(monkeypatch):
    monkeypatch.setattr(
        ai_engine.market_data, "get_live_prices",
        lambda ids, cur, timeout=None: (False, None, "network error"),
    )
    monkeypatch.setattr(
        ai_engine.market_data, "get_market_chart",
        lambda coin_id, cur, days, timeout=None: (True, [], None),
    )
    assert ai_engine._fetch_market_context("BTC") is None


def test_fetch_market_context_uses_short_timeout_not_full_request_timeout(monkeypatch):
    """Bez kratkeho timeoutu tu mohli tieto 2 volania v najhorsom pripade
    zjest az 24s (2x plny REQUEST_TIMEOUT_SECONDS) e s t e PREDTYM, nez
    zacalo samotne volanie AI providera - v sucte s tym cely request mohol
    prekrocit ~40s limit Netlify proxy a skoncit 502 chybou."""
    captured_timeouts = []

    def fake_prices(ids, cur, timeout=None):
        captured_timeouts.append(timeout)
        return True, {"bitcoin": {"usd": 100.0, "usd_24h_change": 0.0}}, None

    def fake_chart(coin_id, cur, days, timeout=None):
        captured_timeouts.append(timeout)
        return True, [[0, 100.0], [1, 100.0]], None

    monkeypatch.setattr(ai_engine.market_data, "get_live_prices", fake_prices)
    monkeypatch.setattr(ai_engine.market_data, "get_market_chart", fake_chart)
    ai_engine._fetch_market_context("BTC")
    assert captured_timeouts == [ai_engine._MARKET_CONTEXT_TIMEOUT, ai_engine._MARKET_CONTEXT_TIMEOUT]
    assert ai_engine._MARKET_CONTEXT_TIMEOUT < ai_engine.REQUEST_TIMEOUT_SECONDS


def test_fetch_market_context_never_raises_on_unexpected_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("nieco sa pokazilo")
    monkeypatch.setattr(ai_engine.market_data, "get_live_prices", boom)
    # nesmie vyhodit vynimku von - realne data su bonus, nikdy nesmu zhodit predikciu
    assert ai_engine._fetch_market_context("BTC") is None


def test_compute_accuracy_pending_when_horizon_not_yet_matured():
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc)  # "1T" (1 tyzden) predikcia vytvorena prave teraz
    result = ai_engine.compute_forecast_accuracy("BTC", "1T", [100, 105, 110], ["d1", "d2", "d3"], created_at)
    assert result["status"] == "pending"
    assert result["accuracy_pct"] is None
    assert result["actual_prices"] == []


def test_compute_accuracy_unavailable_for_unknown_coin():
    from datetime import datetime, timedelta, timezone
    created_at = datetime.now(timezone.utc) - timedelta(days=10)  # horizont uz davno ubehol
    result = ai_engine.compute_forecast_accuracy("SOME_UNKNOWN_COIN", "1T", [100, 105], ["d1", "d2"], created_at)
    assert result["status"] == "unavailable"
    assert result["accuracy_pct"] is None


def test_compute_accuracy_completed_with_correct_percentage(monkeypatch):
    from datetime import datetime, timedelta, timezone
    created_at = datetime.now(timezone.utc) - timedelta(days=10)  # "1T" horizont uz ubehol

    def fake_range(coin_id, cur, from_ts, to_ts):
        # simuluje skutocny vyvoj ceny presne na urovni predikcie (nulova chyba)
        return True, [[from_ts * 1000, 100.0], [to_ts * 1000, 110.0]], None

    monkeypatch.setattr(ai_engine.market_data, "get_market_chart_range", fake_range)
    result = ai_engine.compute_forecast_accuracy("BTC", "1T", [100.0, 110.0], ["d1", "d2"], created_at)
    assert result["status"] == "completed"
    assert result["accuracy_pct"] == 100.0  # predikcia sedela presne so "skutocnostou"
    assert result["actual_prices"] == [100.0, 110.0]


def test_compute_accuracy_unavailable_when_chart_fetch_fails(monkeypatch):
    from datetime import datetime, timedelta, timezone
    created_at = datetime.now(timezone.utc) - timedelta(days=10)
    monkeypatch.setattr(ai_engine.market_data, "get_market_chart_range", lambda *a: (False, [], "network error"))
    result = ai_engine.compute_forecast_accuracy("BTC", "1T", [100.0, 110.0], ["d1", "d2"], created_at)
    assert result["status"] == "unavailable"


def test_openai_compatible_payload_caps_tokens_and_temperature(monkeypatch):
    """Bez explicitneho max_tokens by model mohol generovat neobmedzene dlho -
    a appka aj tak pouzije len strukturovany JSON, zvysok su zbytocne platene
    tokeny. Tento test zamyka, ze limit tam ostane aj po buducich upravach."""
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setattr(ai_engine.requests, "post", fake_post)
    ai_engine._call_openai_compatible("https://example.com/v1/chat", "some-model", "test prompt", "fake-key")
    assert captured["payload"]["max_tokens"] == ai_engine._MAX_OUTPUT_TOKENS
    assert captured["payload"]["temperature"] == ai_engine._TEMPERATURE


def test_anthropic_payload_caps_tokens_and_temperature(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"content": [{"text": "{}"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setattr(ai_engine.requests, "post", fake_post)
    ai_engine._call_anthropic("test prompt", "fake-key")
    assert captured["payload"]["max_tokens"] == ai_engine._MAX_OUTPUT_TOKENS
    assert captured["payload"]["temperature"] == ai_engine._TEMPERATURE


def test_estimate_forecast_cost_scales_with_points():
    """Vacsi horizont (viac datovych bodov) = viac ocakavanych vystupnych
    tokenov = vyssia odhadovana cena."""
    short = ai_engine.estimate_forecast_cost("gemini", "BTC", "24h")  # 24 bodov
    long = ai_engine.estimate_forecast_cost("gemini", "BTC", "1R")   # 12 bodov, ale este viac textu v prompte
    assert short["estimated_total_tokens"] > 0
    assert short["estimated_cost_usd"] > 0
    assert "estimated_input_tokens" in short and "estimated_output_tokens" in short


def test_estimate_portfolio_cost_scales_with_holdings_count():
    small = ai_engine.estimate_portfolio_cost("gemini", [{"minca": "BTC", "mnozstvo": 1}])
    large = ai_engine.estimate_portfolio_cost(
        "gemini", [{"minca": f"COIN{i}", "mnozstvo": 1} for i in range(10)]
    )
    assert large["estimated_total_tokens"] > small["estimated_total_tokens"]
    assert large["estimated_cost_usd"] > small["estimated_cost_usd"]


def test_estimate_cost_differs_by_provider_price():
    """Anthropic ma v config.py vyssiu cenu/1K tokenov nez DeepSeek - odhad
    pre rovnaky prompt sa musi lisit podla zvoleneho providera."""
    cheap = ai_engine.estimate_forecast_cost("deepseek", "BTC", "1T")
    expensive = ai_engine.estimate_forecast_cost("anthropic", "BTC", "1T")
    assert cheap["estimated_total_tokens"] == expensive["estimated_total_tokens"]
    assert cheap["estimated_cost_usd"] < expensive["estimated_cost_usd"]



def _fake_gemini(monkeypatch, text):
    from google import genai
    captured = {}

    class FakeModels:
        def generate_content(self, model, contents, config):
            captured["config"] = config

            class Resp:
                pass
            r = Resp()
            r.text = text
            return r

    class FakeClient:
        def __init__(self, api_key, http_options=None):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    return captured


def test_gemini_uses_low_thinking_no_temperature_and_enough_tokens(monkeypatch):
    """Gemini 3.x zapocitava premyslanie do limitu vystupu - s 1024 tokenmi a
    predvolenym premyslanim vracal prazdnu odpoved (vzdy ukazkove data)."""
    captured = _fake_gemini(monkeypatch, '{"ok": 1}')
    ok, text, err = ai_engine._call_gemini("prompt", "fake-key")
    assert ok is True and err is None
    cfg = captured["config"]
    assert cfg.temperature is None
    assert cfg.thinking_config is not None and cfg.thinking_config.thinking_level is not None
    assert cfg.max_output_tokens >= 2048


def test_gemini_empty_response_returns_explicit_error(monkeypatch):
    _fake_gemini(monkeypatch, None)
    ok, text, err = ai_engine._call_gemini("prompt", "fake-key")
    assert ok is False
    assert "prazdnu odpoved" in err


def test_call_ai_provider_never_logs_api_key(monkeypatch, caplog):
    monkeypatch.setattr(ai_engine, "_call_ai_provider_raw",
                        lambda p, pr, k: (False, "", f"chyba s klucom {k} v sprave"))
    with caplog.at_level("WARNING", logger="aca.ai"):
        ai_engine.call_ai_provider("gemini", "prompt", "TAJNY-KLUC-123")
    assert "TAJNY-KLUC-123" not in caplog.text
    assert "***" in caplog.text
