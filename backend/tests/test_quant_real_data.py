"""Statistical model backtest on real BTC prices."""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

import pytest

from app.services import quant_engine as q

FIXTURES = Path(__file__).parent / "fixtures"


def _load_real_btc_series():
    series = []
    for year in (2024, 2025, 2026):
        data = json.loads((FIXTURES / f"btc{year}.json").read_text(encoding="utf-8"))
        for date_str, price in data.items():
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            series.append([int(dt.timestamp() * 1000), float(price)])
    series.sort(key=lambda p: p[0])
    return series


SERIES = _load_real_btc_series()
LOOKBACK_DAYS = 90


def _coverage(monkeypatch, horizon_key: str, horizon_days: int, step_days: int) -> tuple[int, int]:
    from app.services import market_data

    hits = total = 0
    for i in range(LOOKBACK_DAYS, len(SERIES) - horizon_days, step_days):
        hist = SERIES[i - LOOKBACK_DAYS:i]
        monkeypatch.setattr(market_data, "get_market_history", lambda *a, hist=hist, **k: (True, {"prices": hist, "volumes": []}, None))
        ok, data, _err = q.build_quant_forecast("BTC", horizon_key, "en")
        if not ok:
            continue
        low, high = data["pasmo"]["dolne"][-1], data["pasmo"]["horne"][-1]
        actual = SERIES[i + horizon_days][1]
        total += 1
        if low <= actual <= high:
            hits += 1
    return hits, total


@pytest.mark.parametrize(
    ("horizon_key", "horizon_days", "step_days"),
    [("24h", 1, 1), ("1T", 7, 2), ("1M", 30, 2)],
)
def test_uncertainty_band_is_reasonably_calibrated_on_real_btc_history(monkeypatch, horizon_key, horizon_days, step_days):
    hits, total = _coverage(monkeypatch, horizon_key, horizon_days, step_days)
    assert total > 100, "too few usable samples - check the fixtures"
    coverage_pct = hits / total * 100
    assert 65.0 <= coverage_pct <= 95.0, f"{horizon_key}: coverage {coverage_pct:.1f}% outside the expected range (n={total})"


def test_band_widens_with_horizon_on_real_data(monkeypatch):
    from app.services import market_data

    hist = SERIES[-LOOKBACK_DAYS - 40:-40]
    monkeypatch.setattr(market_data, "get_market_history", lambda *a, **k: (True, {"prices": hist, "volumes": []}, None))
    widths = {}
    for key in ("24h", "1T", "1M"):
        ok, data, _ = q.build_quant_forecast("BTC", key, "en")
        assert ok
        lo, hi, price = data["pasmo"]["dolne"][-1], data["pasmo"]["horne"][-1], data["ceny"][-1]
        widths[key] = (hi - lo) / price
    assert widths["24h"] < widths["1T"] < widths["1M"], widths


def test_short_horizon_jump_variance_floor_meaningfully_improves_calibration(monkeypatch):
    def coverage_without_floor(step_days=1):
        hits = total = 0
        for i in range(LOOKBACK_DAYS, len(SERIES) - 1, step_days):
            hist = SERIES[i - LOOKBACK_DAYS:i]
            sigma_h = q.estimate_sigma_per_hour(hist)
            if sigma_h is None:
                continue
            clean = q._clean_series(hist)
            drift_h = q._drift_per_hour(clean)
            spot = clean[-1][1]
            h = 24.0
            sigma_t = sigma_h * math.sqrt(h)
            cap = q._DRIFT_CAP_SIGMAS * sigma_t
            mu = max(-cap, min(cap, drift_h * h))
            low = spot * math.exp(mu - q.Z_80 * sigma_t)
            high = spot * math.exp(mu + q.Z_80 * sigma_t)
            actual = SERIES[i + 1][1]
            total += 1
            if low <= actual <= high:
                hits += 1
        return hits / total * 100

    without_floor_pct = coverage_without_floor()
    hits, total = _coverage(monkeypatch, "24h", 1, 1)
    with_floor_pct = hits / total * 100
    assert without_floor_pct < 75.0, f"expected under-calibration without the jump term, measured {without_floor_pct:.1f}%"
    assert with_floor_pct > without_floor_pct + 5.0, (
        f"_JUMP_VARIANCE_FLOOR should clearly improve coverage: without={without_floor_pct:.1f}% with={with_floor_pct:.1f}%"
    )
