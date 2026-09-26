"""Testy pre app/services/data_sources.py - kazdy zdroj musi spravne
spracovat data a pri akomkolvek zlyhani vratit None (nikdy vynimku)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import data_sources  # noqa: E402


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise data_sources.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def _clear_caches():
    for cache in (data_sources._fast_cache, data_sources._med_cache, data_sources._slow_cache):
        cache._store.clear()
    yield


def test_coin_type_classification():
    assert data_sources.coin_type(["Meme", "Layer 1 (L1)"]) == "meme"
    assert data_sources.coin_type(["Decentralized Finance (DeFi)"]) == "defi"
    assert data_sources.coin_type(["Smart Contract Platform"]) == "l1"
    assert data_sources.coin_type([]) == "other"


def test_derivatives_parses_hyperliquid(monkeypatch):
    payload = [{"universe": [{"name": "BTC"}, {"name": "SOL"}]},
               [{"funding": "0.00001", "openInterest": "10", "markPx": "80000"},
                {"funding": "-0.00002", "openInterest": "1000000", "markPx": "150"}]]
    monkeypatch.setattr(data_sources.requests, "post", lambda *a, **k: _Resp(payload))
    line = data_sources.derivatives("SOL")
    assert "funding -0.0020%/h" in line and "shorty platia longom" in line and "$150M" in line
    assert data_sources.derivatives("UNKNOWN") is None


def test_macro_requires_key(monkeypatch):
    monkeypatch.setattr(data_sources, "FRED_API_KEY", "")
    assert data_sources.macro_summary() is None


def test_macro_summary_with_key(monkeypatch):
    monkeypatch.setattr(data_sources, "FRED_API_KEY", "fred-test-key")
    series = {"FEDFUNDS": [4.33, 4.33], "CPIAUCSL": [312.0] + [300.0] * 13, "DTWEXBGS": [120.0] + [118.0] * 29,
              "SP500": [5500.0] + [5000.0] * 9, "DGS10": [4.1]}

    def fake_get(url, params=None, headers=None, timeout=None):
        return _Resp({"observations": [{"value": str(v)} for v in series[params["series_id"]]]})
    monkeypatch.setattr(data_sources.requests, "get", fake_get)
    line = data_sources.macro_summary()
    assert "sadzba Fedu 4.33%" in line and "inflacia CPI +4.0% r/r" in line and "S&P 500 +10.0%" in line


def test_onchain_whales_summary(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        if url.endswith("/stats"):
            return _Resp({"data": {"transactions_24h": 500000, "mempool_transactions": 9000}})
        return _Resp({"data": [{"time": "2026-01-01 00:00:00", "output_total_usd": 3_000_000},
                               {"time": "2026-01-01 01:00:00", "output_total_usd": 12_000_000}]})
    monkeypatch.setattr(data_sources.requests, "get", fake_get)
    line = data_sources.onchain("bitcoin")
    assert "500,000 transakcii za 24h" in line and "spolu $15M" in line and "najvacsi $12M" in line
    assert data_sources.onchain("solana") is None


def test_chain_tvl_uses_gecko_id(monkeypatch):
    history = [{"tvl": 100.0}] * 30 + [{"tvl": 110.0}] * 2

    def fake_get(url, params=None, headers=None, timeout=None):
        if url.endswith("/v2/chains"):
            return _Resp([{"name": "Solana", "gecko_id": "solana", "tvl": 9_000_000_000}])
        return _Resp(history)
    monkeypatch.setattr(data_sources.requests, "get", fake_get)
    line = data_sources.chain_tvl("solana")
    assert "DeFi TVL siete Solana: $9.00B" in line and "30d +10.0%" in line


def test_failed_source_returns_none_and_never_logs_keys(monkeypatch, caplog):
    monkeypatch.setattr(data_sources, "FRED_API_KEY", "TAJNY-FRED-KLUC")

    def fake_get(*a, **k):
        raise data_sources.requests.exceptions.ConnectionError("chyba pre ...&api_key=TAJNY-FRED-KLUC")
    monkeypatch.setattr(data_sources.requests, "get", fake_get)
    with caplog.at_level("INFO", logger="aca.sources"):
        assert data_sources.macro_summary() is None
    assert "TAJNY-FRED-KLUC" not in caplog.text


def test_github_and_reddit_url_parsing(monkeypatch):
    monkeypatch.setattr(data_sources.requests, "get", lambda *a, **k: _Resp([{}] * 42))
    assert "42 commitov" in data_sources.github_activity("https://github.com/solana-labs/solana")
    assert data_sources.github_activity("https://evil.example.com/x/y") is None
    assert data_sources.coin_subreddit("https://example.com/r/x") is None
