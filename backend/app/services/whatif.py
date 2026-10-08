""""What if" calculator: follow the free model's daily signal vs. simply holding the coin.

Every day of the chosen period the model sees only the prices known that day (same code path as the
live forecast). When it expects a rise beyond a small band it holds the coin for the next day,
otherwise it stays in cash. Each switch costs a trading fee. Past results never guarantee anything."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import DEFAULT_COIN_IDS
from app.services import market_data, quant_engine
from app.utils.ttl_cache import TTLCache

PERIODS = (7, 30, 90)
LOOKBACK_DAYS = 60
SIGNAL_BAND_PCT = 0.2
FEE_PCT = 0.1
_cache = TTLCache(ttl_seconds=3 * 3600)


def _max_drawdown(curve: List[float]) -> float:
    peak, worst = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return round(worst * 100, 2)


def daily_signal(window: List[Tuple[float, float]]) -> str:
    sigma_h = quant_engine.estimate_sigma_per_hour([list(p) for p in window])
    if sigma_h is None:
        return "flat"
    predicted, _lows, _highs = quant_engine.project_path(window, sigma_h, 24.0, 1)
    change = (predicted[-1] / window[-1][1] - 1) * 100
    return "up" if change > SIGNAL_BAND_PCT else "down" if change < -SIGNAL_BAND_PCT else "flat"


def simulate(prices: List[List[float]], days: int, amount: float) -> Optional[Dict[str, Any]]:
    """Pure computation on daily [timestamp_ms, price] points; used by the endpoint and by tests."""
    series = quant_engine._clean_series(prices)
    if len(series) < LOOKBACK_DAYS + days + 1:
        return None
    start = len(series) - days - 1
    strategy, hold = amount, amount
    in_market = False
    trades = exposure = 0
    curve = [{"date": _date(series[start][0]), "strategy": round(strategy, 2), "hold": round(hold, 2)}]
    for i in range(start, len(series) - 1):
        signal = daily_signal(series[i - LOOKBACK_DAYS + 1:i + 1])
        want = signal == "up"
        if want != in_market:
            strategy *= 1 - FEE_PCT / 100
            trades += 1
            in_market = want
        move = series[i + 1][1] / series[i][1]
        if in_market:
            strategy *= move
            exposure += 1
        hold *= move
        curve.append({"date": _date(series[i + 1][0]), "strategy": round(strategy, 2), "hold": round(hold, 2)})
    today = daily_signal(series[-LOOKBACK_DAYS:])
    return {
        "days": days, "amount": amount, "fee_pct": FEE_PCT, "signal_today": today,
        "strategy": {"final": round(strategy, 2), "return_pct": round((strategy / amount - 1) * 100, 2),
                     "max_drawdown_pct": _max_drawdown([p["strategy"] for p in curve]), "trades": trades,
                     "exposure_pct": round(exposure / days * 100)},
        "hold": {"final": round(hold, 2), "return_pct": round((hold / amount - 1) * 100, 2),
                 "max_drawdown_pct": _max_drawdown([p["hold"] for p in curve])},
        "curve": curve,
    }


def _date(ts_ms: float) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()


def _daily(points: List[List[float]]) -> List[List[float]]:
    """One price per UTC day (the last one), whatever the source resolution."""
    by_day: Dict[str, List[float]] = {}
    for ts, price in quant_engine._clean_series(points):
        by_day[_date(ts)] = [ts, price]
    return [by_day[d] for d in sorted(by_day)]


def run(coin: str, days: int, amount: float) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    coin = coin.upper()
    coin_id = DEFAULT_COIN_IDS.get(coin)
    if coin_id is None or days not in PERIODS:
        return False, None, "Nepodporovaná minca alebo obdobie."
    key = f"{coin}:{days}"
    prices = _cache.get(key)
    if prices is None:
        ok, raw, err = market_data.get_market_chart(coin_id, "usd", str(days + LOOKBACK_DAYS + 5))
        if not ok or not raw:
            return False, None, err or "Historické ceny sa teraz nepodarilo načítať."
        prices = _daily(raw)
        _cache.set(key, prices)
    result = simulate(prices, days, amount)
    if result is None:
        return False, None, "Na výpočet je zatiaľ málo historických dát."
    return True, {"coin": coin, **result}, None
