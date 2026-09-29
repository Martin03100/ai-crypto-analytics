"""Walk-forward backtest of the statistical model."""

import pytest

from tests.test_quant import _patch_history, _series
from tests.test_quant_real_data import SERIES as REAL_BTC_DAILY


@pytest.fixture(autouse=True)
def _clear_backtest_cache():
    from app.services import backtest
    backtest._cache._store.clear()
    yield
    backtest._cache._store.clear()


def test_backtest_on_real_btc_history_is_calibrated():
    from app.services.backtest import run_backtest_on_series
    result = run_backtest_on_series(REAL_BTC_DAILY, "1T")
    assert result["sample_count"] > 50
    # The 80 % band should contain the real price roughly 80 % of the time.
    assert 65 <= result["band_coverage_pct"] <= 95
    # A random-walk-like model should be in the same league as "price stays the same".
    assert result["mape_pct"] <= result["naive_mape_pct"] * 1.25
    assert result["samples"][0]["date"] < result["samples"][-1]["date"]


def test_backtest_uses_only_past_data_for_each_origin():
    """A forecast must not see the future: changing prices after an origin must not change it."""
    from app.services.backtest import run_backtest_on_series
    base = run_backtest_on_series(REAL_BTC_DAILY, "1T")["samples"][0]
    tampered = [list(p) for p in REAL_BTC_DAILY]
    cutoff = next(i for i, p in enumerate(tampered) if p[0] / 1000 > __import__("datetime").datetime.fromisoformat(base["date"]).timestamp())
    for p in tampered[cutoff:]:
        p[1] *= 3
    again = run_backtest_on_series(tampered, "1T")["samples"][0]
    assert again["predicted"] == base["predicted"] and again["low"] == base["low"]
    assert again["actual"] != base["actual"]


def test_backtest_rejects_short_history_and_unknown_horizon():
    from app.services.backtest import run_backtest_on_series
    assert run_backtest_on_series(REAL_BTC_DAILY[:50], "1T") is None
    assert run_backtest_on_series(REAL_BTC_DAILY, "1R") is None


def test_backtest_endpoint(registered, monkeypatch):
    client, _u, _p = registered
    _patch_history(monkeypatch, _series(n=400, sigma=0.03))
    res = client.get("/api/forecast/backtest?coin=BTC&horizon=1T")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["coin"] == "BTC" and body["sample_count"] > 10 and body["band_target_pct"] == 80.0


def test_backtest_endpoint_validates_input(registered):
    client, _u, _p = registered
    assert client.get("/api/forecast/backtest?coin=NOPE&horizon=1T").status_code == 400
    assert client.get("/api/forecast/backtest?coin=BTC&horizon=1R").status_code == 400


def test_backtest_endpoint_reports_missing_data(registered, monkeypatch):
    from app.services import market_data
    client, _u, _p = registered
    monkeypatch.setattr(market_data, "get_market_history", lambda *a, **k: (False, {}, "offline"))
    assert client.get("/api/forecast/backtest?coin=ETH&horizon=1M").status_code == 503


def test_backtest_requires_login(client):
    assert client.get("/api/forecast/backtest?coin=BTC&horizon=1T").status_code == 401
