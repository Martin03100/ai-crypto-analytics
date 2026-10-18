"""Signals and coin pages never make a visitor wait for a slow or blocked source."""

from __future__ import annotations

import time

import pytest
import requests

from app.services import coin_page, signal_text, signals

pytestmark = pytest.mark.live_signals


@pytest.fixture(autouse=True)
def fresh_state():
    for cache in (signals._fast, signals._medium, signals._slow, signals._bundle, coin_page._cache):
        cache.clear()
    signals._down_until.clear()
    yield
    signals._down_until.clear()


def _wait_until(check, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return False


def test_an_unreachable_source_is_skipped_for_a_while(monkeypatch):
    calls = []

    def hanging_get(url, **kwargs):
        calls.append(url)
        raise requests.exceptions.ConnectTimeout("no answer")

    monkeypatch.setattr(signals.requests, "get", hanging_get)
    assert signals._get("https://slow.example.com/a", signals._fast) is None
    assert signals._get("https://slow.example.com/b", signals._fast) is None
    assert len(calls) == 1, "the second request must not wait for the same dead host"


def test_an_expired_bundle_is_served_at_once_and_refreshed_in_the_background(monkeypatch):
    old = {"coin": "BTC", "items": [{"tone": "bullish"}], "sources": [], "lines": [], "updated_at": "old"}
    signals._bundle._store["BTC"] = (time.monotonic() - 10_000, old)       # expired long ago
    refreshed = []

    def slow_collect(symbol, timeout):
        time.sleep(0.2)
        fresh = {**old, "updated_at": "new"}
        signals._bundle.set(symbol, fresh)
        refreshed.append(symbol)
        return fresh

    monkeypatch.setattr(signals, "_collect", slow_collect)
    started = time.monotonic()
    assert signals.collect("BTC")["updated_at"] == "old"
    assert time.monotonic() - started < 0.15
    assert _wait_until(lambda: refreshed == ["BTC"])
    assert signals.collect("BTC")["updated_at"] == "new"


def test_warm_refreshes_every_coin(monkeypatch):
    seen = []
    monkeypatch.setattr(signals, "_collect", lambda symbol, timeout: seen.append(symbol) or {"items": []})
    pauses = []
    monkeypatch.setattr(signals.time, "sleep", lambda s: pauses.append(s))
    assert signals.warm(["btc", "eth"]) == 2
    assert pauses == [signals._WARM_PAUSE_SECONDS]      # a breather between coins, none before the first
    assert seen == ["BTC", "ETH"]


def test_an_expired_coin_page_is_served_at_once(client, monkeypatch):
    coin_page._cache._store["ETH"] = (time.monotonic() - 10_000, {"coin": "ETH", "price": 1.0, "outlook": []})
    rebuilt = []
    monkeypatch.setattr(coin_page, "_build", lambda db, coin: rebuilt.append(coin) or {"coin": coin})
    res = client.get("/api/public/coin/ETH")
    assert res.status_code == 200 and res.json()["price"] == 1.0
    assert _wait_until(lambda: rebuilt == ["ETH"])


def test_display_values_are_localized_for_emails():
    assert signal_text.localize_display("+2.8% 1m", "sk") == "+2.8% 1 mes."
    assert signal_text.localize_display("3.7% y/y", "de") == "3.7% ggü. Vorjahr"
    assert signal_text.localize_display("0% long", "cs") == "0 % longů"
    lines = signal_text.headline([{"key": "funding", "display": "+0.0450% / 8h", "tone": "bearish"}], "pl")
    assert lines == ["Funding: +0.0450% / 8 h ▼"]


def test_a_country_blocked_source_is_skipped_for_hours(monkeypatch):
    import requests
    calls = []

    class Blocked:
        status_code = 451

        def raise_for_status(self):
            raise requests.HTTPError("451 Client Error", response=self)

    monkeypatch.setattr(signals.requests, "get", lambda *a, **k: calls.append(1) or Blocked())
    signals._down_until.clear()
    assert signals._get("https://fapi.blocked.example.com/premiumIndex", signals._fast) is None
    assert signals._get("https://fapi.blocked.example.com/premiumIndex?symbol=ETH", signals._fast) is None
    assert len(calls) == 1
    assert signals._down_until["fapi.blocked.example.com"] - time.monotonic() > 3600
    signals._down_until.clear()
