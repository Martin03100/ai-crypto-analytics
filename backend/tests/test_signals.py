"""Market signals: parsing of each public source, fallbacks between exchanges and the bundle the AI receives."""

import time
from datetime import date

import pytest

from app.services import ai_engine, signals

pytestmark = pytest.mark.live_signals

NOW_MS = time.time() * 1000


def fake_get(responses):
    """responses: {url_fragment: payload}; anything else is unavailable (None)."""
    def _get(url, cache, params=None, as_text=False):
        for fragment, payload in responses.items():
            if fragment in url:
                return payload(params) if callable(payload) else payload
        return None
    return _get


@pytest.fixture(autouse=True)
def fresh_caches():
    for cache in (signals._fast, signals._medium, signals._slow, signals._bundle):
        cache.clear()


def test_derivatives_from_binance(monkeypatch):
    monkeypatch.setattr(signals, "_get", fake_get({
        "premiumIndex": {"lastFundingRate": "0.00045"},
        "openInterestHist": [{"sumOpenInterestValue": "1000000000"}] + [{}] * 23 + [{"sumOpenInterestValue": "1100000000"}],
        "globalLongShortAccountRatio": [{"longShortRatio": "2.4"}],
    }))
    items = {s["key"]: s for s in signals.derivatives("BTC")}
    assert items["funding"]["display"] == "+0.0450% / 8h" and items["funding"]["tone"] == "bearish"
    assert items["open_interest"]["value"] == 10.0 and items["open_interest"]["display"] == "$1.10B (+10.0% 24h)"
    assert items["long_short"]["tone"] == "bearish" and items["funding"]["source"] == "binance"


def test_derivatives_fall_back_to_bybit_then_okx(monkeypatch):
    monkeypatch.setattr(signals, "_get", fake_get({
        "bybit.com/v5/market/tickers": {"result": {"list": [{"fundingRate": "-0.0002", "openInterestValue": "5000000"}]}},
        "account-ratio": {"result": {"list": [{"buyRatio": "0.4", "sellRatio": "0.6"}]}},
    }))
    items = {s["key"]: s for s in signals.derivatives("PEPE")}
    assert items["funding"]["source"] == "bybit" and items["funding"]["tone"] == "bullish"
    assert items["long_short"]["value"] == 0.67
    monkeypatch.setattr(signals, "_get", fake_get({"okx.com/api/v5/public/funding-rate": {"data": [{"fundingRate": "0.0001"}]}}))
    assert signals.derivatives("SOL")[0]["source"] == "okx"
    monkeypatch.setattr(signals, "_get", fake_get({}))
    assert signals.derivatives("SOL") == []


def test_liquidations_share_of_longs(monkeypatch):
    details = [{"posSide": "long", "sz": "8", "ts": str(NOW_MS)}, {"posSide": "short", "sz": "2", "ts": str(NOW_MS)},
               {"posSide": "short", "sz": "50", "ts": "1000"}]                      # old: ignored
    monkeypatch.setattr(signals, "_get", fake_get({"liquidation-orders": {"data": [{"details": details}]}}))
    item = signals.liquidations("BTC")[0]
    assert item["value"] == 80.0 and item["tone"] == "bearish"


def test_options_put_call_and_dvol(monkeypatch):
    book = {"result": [{"instrument_name": "BTC-27NOV26-70000-P", "open_interest": 120},
                       {"instrument_name": "BTC-27NOV26-90000-C", "open_interest": 100}]}
    vol = {"result": {"data": [[1, 0, 0, 0, 40.0], [2, 0, 0, 0, 50.0]]}}
    monkeypatch.setattr(signals, "_get", fake_get({"get_book_summary": book, "volatility_index": vol}))
    items = {s["key"]: s for s in signals.options("BTC")}
    assert items["put_call"]["value"] == 1.2 and items["put_call"]["tone"] == "bearish"
    assert items["dvol"]["display"] == "50.0 (+25% 7d)" and items["dvol"]["tone"] == "bearish"
    assert signals.options("DOGE") == []


def test_stablecoins_premium_market_and_network(monkeypatch):
    chart = [{"totalCirculatingUSD": {"peggedUSD": 200e9}}] * 23 + [{"totalCirculatingUSD": {"peggedUSD": 200e9}}] * 7 \
        + [{"totalCirculatingUSD": {"peggedUSD": 202e9}}]
    monkeypatch.setattr(signals, "_get", fake_get({
        "stablecoincharts": chart,
        "coinbase.com": {"price": "100100"}, "market/ticker": {"data": [{"last": "100000"}]},
        "coingecko.com/api/v3/global": {"data": {"market_cap_percentage": {"btc": 58.24},
                                                  "total_market_cap": {"usd": 3.1e12}, "market_cap_change_percentage_24h_usd": -2.5}},
        "fees/recommended": {"fastestFee": 12},
        "hashrate": {"hashrates": [{"avgHashrate": 8e20}, {"avgHashrate": 9e20}]},
    }))
    assert signals.stablecoins()[0]["tone"] == "bullish"
    assert signals.coinbase_premium()[0]["display"] == "+0.100%"
    market = {s["key"]: s for s in signals.global_market()}
    assert market["btc_dominance"]["display"] == "58.2%" and market["total_cap"]["tone"] == "bearish"
    network = {s["key"]: s for s in signals.btc_network()}
    assert network["btc_fees"]["display"] == "12 sat/vB" and network["hashrate"]["display"] == "900 EH/s (+12% 30d)"


def test_macro_from_keyless_fred_csv(monkeypatch):
    def series(params):
        sid = params["id"]
        rows = {"VIXCLS": ["18", "27.5"], "NASDAQCOM": ["100", ".", "100", "100", "100", "100", "97"],
                "DCOILWTICO": [], "FEDFUNDS": ["4.33"], "CPIAUCSL": ["100"] * 12 + ["103"]}.get(sid, [])
        return "observation_date," + sid + "\n" + "\n".join(f"2026-01-{i + 1:02d},{v}" for i, v in enumerate(rows))
    monkeypatch.setattr(signals, "_get", fake_get({"fredgraph.csv": series,
                                                   "simple/price": {"pax-gold": {"usd": 3990.2, "usd_24h_change": 1.234}}}))
    items = {s["key"]: s for s in signals.macro()}
    assert items["vix"]["tone"] == "bearish" and items["vix"]["display"] == "27.5"
    assert items["nasdaq"]["display"] == "-3.0% 1w" and items["nasdaq"]["tone"] == "bearish"
    assert items["inflation"]["display"] == "3.0% y/y" and items["fed_rate"]["display"] == "4.33%"
    assert items["gold"]["display"] == "$3,990 (+1.2% 24h)" and "oil" not in items


def test_events_regulators_and_polymarket(monkeypatch):
    assert signals.events(today=date(2026, 10, 25))[0]["note"].startswith("Scheduled:")
    rss = """<rss><channel>
      <item><title>SEC charges crypto exchange</title><pubDate>{now}</pubDate></item>
      <item><title>SEC names new director</title><pubDate>{now}</pubDate></item>
    </channel></rss>""".format(now=time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()))
    monkeypatch.setattr(signals, "_get", fake_get({
        "sec.gov": rss, "cftc.gov": "<not xml",
        "polymarket": [{"question": "Will Bitcoin hit $150k in 2026?", "outcomes": '["Yes","No"]', "outcomePrices": '["0.23","0.77"]'},
                       {"question": "Will it rain in Paris?", "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]'}],
    }))
    reg = signals.regulation()
    assert [r["display"] for r in reg] == ["SEC charges crypto exchange"] and reg[0]["source"] == "sec"
    poly = signals.prediction_markets("BTC")
    assert len(poly) == 1 and poly[0]["value"] == 23


def test_bundle_survives_failing_and_slow_sources(monkeypatch):
    monkeypatch.setattr(signals, "_get", fake_get({"fees/recommended": {"fastestFee": 3}}))
    monkeypatch.setattr(signals, "macro", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    bundle = signals.collect("ETH")
    assert [s["key"] for s in bundle["items"]][-1] in ("event", "btc_fees")
    assert "mempool" in bundle["sources"] and bundle["lines"]
    assert signals.context_block(bundle).startswith("Market signals")
    assert signals.context_block({"lines": []}) is None


def test_forecast_and_chat_prompts_include_signals(monkeypatch):
    bundle = {"items": [signals.signal("derivatives", "funding", 0.05, "+0.05%", "bearish", "binance", "BTC funding high")],
              "lines": ["BTC funding high"], "sources": ["binance"]}
    monkeypatch.setattr(signals, "collect", lambda *a, **k: bundle)
    assert "BTC funding high" in ai_engine.market_signals_block("BTC", "ETH")
    prompts = []
    monkeypatch.setattr(ai_engine, "call_ai_provider", lambda provider, prompt, key: prompts.append(prompt) or (True, "Fine.", None))
    ai_engine.chat_with_ai("gemini", [{"role": "user", "content": "what about sol today?"}], "key")
    assert "BTC funding high" in prompts[-1]
    assert ai_engine._used_signals("BTC") == [{"group": "derivatives", "key": "funding", "display": "+0.05%",
                                                "tone": "bearish", "source": "binance"}]


def test_signals_endpoint_and_briefing_lines(client, monkeypatch):
    bundle = {"coin": "ETH", "items": [signals.signal("macro", "vix", 28.0, "28.0", "bearish", "fred", "VIX high"),
                                       signals.signal("market", "btc_dominance", 58.0, "58.0%", "neutral", "coingecko", "dom")],
              "sources": ["fred"], "lines": [], "updated_at": "now", "score": {"bullish": 0, "bearish": 1, "neutral": 1}}
    monkeypatch.setattr(signals, "collect", lambda coin: {**bundle, "coin": coin})
    res = client.get("/api/market/signals?coin=eth")
    assert res.status_code == 200 and res.json()["coin"] == "ETH" and len(res.json()["items"]) == 2
    assert client.get("/api/market/signals?coin=FAKE").status_code == 400
    assert signals.headline(bundle["items"], "sk") == ["VIX: 28.0 ▼"]
