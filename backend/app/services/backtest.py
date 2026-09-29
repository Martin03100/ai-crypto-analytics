"""Walk-forward backtest of the statistical (quant) model on real price history.

For many past dates ("origins") the model sees only the prices known at that moment,
forecasts ahead, and the forecast is compared with what really happened. The same
code path as the live forecast is used (quant_engine.project_path)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import DEFAULT_COIN_IDS
from app.services import market_data, quant_engine
from app.utils.ttl_cache import TTLCache

# horizon -> (history days to download, lookback points, forecast points, step hours, points between origins)
BACKTEST_SETUP: Dict[str, Tuple[int, int, int, float, int]] = {
    "24h": (90, 720, 24, 1.0, 24),   # hourly data: 30-day lookback, a new origin every day
    "1T": (365, 90, 7, 24.0, 7),     # daily data: 90-day lookback, a new origin every week
    "1M": (365, 90, 30, 24.0, 7),    # daily data, overlapping monthly windows
}
_cache = TTLCache(ttl_seconds=6 * 3600)


def _pct_error(predicted: float, actual: float) -> float:
    return abs(predicted - actual) / actual * 100


def run_backtest_on_series(prices: List[List[float]], horizon: str) -> Optional[Dict[str, Any]]:
    """Pure computation, no network: used by the endpoint and directly by tests."""
    if horizon not in BACKTEST_SETUP:
        return None
    _days, lookback, points, step_hours, origin_every = BACKTEST_SETUP[horizon]
    series = quant_engine._clean_series(prices)
    samples: List[Dict[str, Any]] = []
    inside = total_points = direction_hits = direction_total = 0
    model_errors: List[float] = []
    naive_errors: List[float] = []

    for origin in range(lookback, len(series) - points, origin_every):
        window = series[origin - lookback:origin]
        sigma_h = quant_engine.estimate_sigma_per_hour([list(p) for p in window])
        if sigma_h is None:
            continue
        predicted, lows, highs = quant_engine.project_path(window, sigma_h, step_hours, points)
        actual = [price for _ts, price in series[origin:origin + points]]
        spot = window[-1][1]

        for low, high, real in zip(lows, highs, actual):
            total_points += 1
            inside += low <= real <= high
        model_errors.append(_pct_error(predicted[-1], actual[-1]))
        naive_errors.append(_pct_error(spot, actual[-1]))
        if not math.isclose(predicted[-1], spot, rel_tol=1e-4):
            direction_total += 1
            direction_hits += (predicted[-1] > spot) == (actual[-1] > spot)
        samples.append({
            "date": datetime.fromtimestamp(window[-1][0] / 1000, tz=timezone.utc).isoformat(),
            "start": spot, "predicted": predicted[-1], "actual": actual[-1], "low": lows[-1], "high": highs[-1],
        })

    if not samples:
        return None
    mape = sum(model_errors) / len(model_errors)
    naive_mape = sum(naive_errors) / len(naive_errors)
    return {
        "horizon": horizon, "samples": samples, "sample_count": len(samples),
        "mape_pct": round(mape, 2), "naive_mape_pct": round(naive_mape, 2),
        "band_coverage_pct": round(inside / total_points * 100, 1), "band_target_pct": 80.0,
        "direction_accuracy_pct": round(direction_hits / direction_total * 100, 1) if direction_total else None,
        "direction_samples": direction_total,
        "period_start": samples[0]["date"], "period_end": samples[-1]["date"],
    }


def run_backtest(coin: str, horizon: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    coin = (coin or "").upper()
    coin_id = DEFAULT_COIN_IDS.get(coin)
    if not coin_id or horizon not in BACKTEST_SETUP:
        return False, None, "Backtest podporuje základné mince a horizonty 24h, 1T a 1M."
    key = f"{coin}|{horizon}"
    cached = _cache.get(key)
    if cached is not None:
        return True, cached, None
    ok, history, error = market_data.get_market_history(coin_id, BACKTEST_SETUP[horizon][0])
    if not ok or not history.get("prices"):
        return False, None, error or "Historické dáta momentálne nie sú dostupné."
    result = run_backtest_on_series(history["prices"], horizon)
    if result is None:
        return False, None, "Na backtest je málo historických dát."
    result["coin"] = coin
    _cache.set(key, result)
    return True, result, None
