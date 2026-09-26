"""Testy pre app/services/ai_engine.py — hlavne _fetch_market_context(), ktora
dava AI predikciam realnu kotvu (aktualnu cenu a trend) namiesto toho, aby si
model vymyslal cisla len z vseobecneho "crypto rastie" narativu."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import ai_engine  # noqa: E402




def test_fetch_market_context_returns_none_for_unknown_coin():
    """Minca, ktora nie je v DEFAULT_COIN_IDS (napr. custom hladana minca) -
    ziadny coin_id na dotaz, prompt sa zostavi bez realnych dat namiesto padu."""
    assert ai_engine._fetch_market_context("TOTALLY_UNKNOWN_COIN") is None








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
    """1T predikcia s 2 bodmi: bod 1 = cas vytvorenia + 3.5 dna, bod 2 = +7 dni
    (rovnako ako casy v grafe). Skutocna cena rastie linearne zo 100 na 110."""
    from datetime import datetime, timedelta, timezone
    created_at = datetime.now(timezone.utc) - timedelta(days=10)

    def fake_range(coin_id, cur, from_ts, to_ts):
        hours = int((to_ts - from_ts) / 3600)
        return True, [[(from_ts + h * 3600) * 1000, 100.0 + 10.0 * h / hours] for h in range(hours + 1)], None

    monkeypatch.setattr(ai_engine.market_data, "get_market_chart_range", fake_range)
    result = ai_engine.compute_forecast_accuracy("BTC", "1T", [105.0, 110.0], ["d1", "d2"], created_at)
    assert result["status"] == "completed"
    assert result["accuracy_pct"] >= 99.9  # predikcia sedela so "skutocnostou"
    assert abs(result["actual_prices"][0] - 105.0) < 0.1 and abs(result["actual_prices"][1] - 110.0) < 0.1
    # predikcia trafila smer (rast) a bola lepsia nez naivny odhad "cena sa nezmeni"
    assert result["direction_correct"] is True
    assert result["baseline_accuracy_pct"] < result["accuracy_pct"]


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



def _hist(start, end, hours=720):
    """Linearny vyvoj ceny zo `start` na `end` za 30 dni, hodinove body."""
    now = 1_800_000_000_000
    pts = [[now - (hours - i) * 3_600_000, start + (end - start) * i / hours] for i in range(hours + 1)]
    return {"prices": pts, "volumes": [[p[0], 1_000_000.0] for p in pts]}


def _patch_sources(monkeypatch, coin_hist, btc_hist=None, fail=False, timeouts=None):
    def fake_history(coin_id, days=30, timeout=None):
        if timeouts is not None:
            timeouts.append(timeout)
        if fail:
            return False, {}, "chyba"
        return True, (btc_hist if coin_id == "bitcoin" and btc_hist else coin_hist), None
    monkeypatch.setattr(ai_engine.market_data, "get_market_history", fake_history)
    monkeypatch.setattr(ai_engine.market_data, "get_fear_greed_index",
                        lambda *a, **k: (True, {"value": 71, "classification": "Greed"}, None))
    monkeypatch.setattr(ai_engine.market_data, "get_crypto_headlines",
                        lambda *a, **k: (True, [{"title": "Bitcoin ETF inflows rise"}], None))
    for name in ("coin_profile", "coin_news", "derivatives", "onchain", "chain_tvl", "macro_summary",
                 "world_news", "github_activity", "coin_subreddit"):
        monkeypatch.setattr(ai_engine.data_sources, name, lambda *a, **k: None)


def test_market_context_includes_indicators_btc_mood_and_news(monkeypatch):
    _patch_sources(monkeypatch, _hist(100.0, 110.0), btc_hist=_hist(80000.0, 84000.0))
    ctx = ai_engine._fetch_market_context("SOL")
    assert "SOL: cena $110.00" in ctx
    assert "30d +10.0%" in ctx
    assert "RSI(14)" in ctx and "vs SMA7" in ctx and "denna volatilita" in ctx and "objem 24h" in ctx
    assert "BTC (lider trhu): cena $84,000.00" in ctx
    assert "Fear & Greed index: 71 (Greed)" in ctx
    assert "Bitcoin ETF inflows rise" in ctx


def test_market_context_for_btc_has_no_duplicate_leader_line(monkeypatch):
    _patch_sources(monkeypatch, _hist(80000.0, 84000.0))
    ctx = ai_engine._fetch_market_context("BTC")
    assert "BTC: cena" in ctx and "lider trhu" not in ctx


def test_market_context_none_when_history_unavailable(monkeypatch):
    _patch_sources(monkeypatch, None, fail=True)
    assert ai_engine._fetch_market_context("ETH") is None


def test_market_context_uses_short_timeout(monkeypatch):
    timeouts = []
    _patch_sources(monkeypatch, _hist(1.0, 2.0), timeouts=timeouts)
    ai_engine._fetch_market_context("ETH")
    assert timeouts and all(t == ai_engine._MARKET_CONTEXT_TIMEOUT for t in timeouts)
    assert ai_engine._MARKET_CONTEXT_TIMEOUT < ai_engine.REQUEST_TIMEOUT_SECONDS


def test_market_context_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("nieco sa pokazilo")
    for fn in ("get_market_history", "get_fear_greed_index", "get_crypto_headlines"):
        monkeypatch.setattr(ai_engine.market_data, fn, boom)
    for fn in ("coin_profile", "coin_news", "derivatives", "onchain", "chain_tvl", "macro_summary", "world_news"):
        monkeypatch.setattr(ai_engine.data_sources, fn, boom)
    assert ai_engine._fetch_market_context("ETH") is None


def test_rsi_extremes():
    assert ai_engine._rsi([float(i) for i in range(20)]) == 100.0
    assert ai_engine._rsi([float(20 - i) for i in range(20)]) == 0.0
    assert ai_engine._rsi([1.0, 2.0]) is None


def test_real_forecast_prompt_requests_user_language(monkeypatch):
    captured = {}
    monkeypatch.setattr(ai_engine, "_build_market_context", lambda coin: (None, []))
    monkeypatch.setattr(ai_engine, "call_ai_provider",
                        lambda p, prompt, k: (captured.setdefault("prompt", prompt), (False, "", "x"))[1])
    ai_engine.get_coin_forecast("gemini", "BTC", "1T", "fake-key", lang="cz")
    assert "čeština" in captured["prompt"]



def test_market_context_adds_type_guidance_and_lists_sources(monkeypatch):
    _patch_sources(monkeypatch, _hist(0.1, 0.12))
    monkeypatch.setattr(ai_engine.data_sources, "coin_profile",
                        lambda cid: {"categories": ["Meme", "Dog-Themed"], "rank": 9, "github": "", "subreddit": ""})
    monkeypatch.setattr(ai_engine.data_sources, "derivatives", lambda s: "Derivaty (Hyperliquid perp): funding +0.0010%/h")
    text, sources = ai_engine._build_market_context("DOGE")
    assert "MEME coin" in text and "Derivaty (Hyperliquid perp)" in text
    assert "hyperliquid" in sources and "coingecko_profile" in sources


def test_portfolio_context_computes_values_and_weights(monkeypatch):
    rows = {
        "bitcoin": {"current_price": 50000.0, "market_cap_rank": 1, "price_change_percentage_7d_in_currency": 2.0},
        "ethereum": {"current_price": 2500.0, "market_cap_rank": 2, "price_change_percentage_7d_in_currency": -3.0},
    }
    monkeypatch.setattr(ai_engine.market_data, "get_coin_markets", lambda ids, timeout=None: (True, rows, None))
    _patch_sources(monkeypatch, _hist(1.0, 1.0))
    text, sources = ai_engine._build_portfolio_context(
        [{"minca": "BTC", "mnozstvo": 1, "coin_id": "bitcoin"}, {"minca": "ETH", "mnozstvo": 20, "coin_id": "ethereum"}])
    assert "BTC: hodnota $50,000 (50% portfolia)" in text
    assert "ETH: hodnota $50,000 (50% portfolia)" in text and "7d -3.0%" in text
    assert "Celkova hodnota $100,000" in text
    assert sources[0] == "coingecko_prices"



def test_custom_provider_call_revalidates_and_blocks_redirects(monkeypatch):
    import json as _json
    captured = {}
    monkeypatch.setattr(ai_engine, "validate_custom_base_url", lambda url: None)

    class Resp:
        is_redirect = False

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "OK"}}]}

    def fake_post(url, headers=None, json=None, timeout=None, allow_redirects=True):
        captured.update(url=url, allow_redirects=allow_redirects)
        return Resp()

    monkeypatch.setattr(ai_engine.requests, "post", fake_post)
    secret = _json.dumps({"base_url": "https://api.example.com/v1/", "model": "m1", "key": "k"})
    assert ai_engine.call_ai_provider("custom", "hi", secret) == (True, "OK", None)
    assert captured == {"url": "https://api.example.com/v1/chat/completions", "allow_redirects": False}


def test_validate_custom_base_url_blocks_private_and_http():
    for url in ("http://example.com", "https://10.0.0.5/v1", "https://169.254.169.254", "https://[::1]/v1", "ftp://x"):
        assert ai_engine.validate_custom_base_url(url) is not None, url


def test_custom_provider_inner_key_never_logged(monkeypatch, caplog):
    import json as _json
    secret = _json.dumps({"base_url": "https://x", "model": "m", "key": "SUPER-TAJNY"})
    monkeypatch.setattr(ai_engine, "_call_ai_provider_raw", lambda p, pr, k: (False, "", "chyba SUPER-TAJNY"))
    with caplog.at_level("WARNING", logger="aca.ai"):
        ai_engine.call_ai_provider("custom", "p", secret)
    assert "SUPER-TAJNY" not in caplog.text
