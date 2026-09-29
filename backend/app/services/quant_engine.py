"""Statistical forecast model."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import DEFAULT_COIN_IDS, TIME_HORIZONS
from app.i18n_content import quant_reasoning, unit_label
from app.services import market_data

Z_80 = 1.2815515655446004
_EWMA_LAMBDA = 0.97
_DRIFT_DAMPING = 0.25
_DRIFT_CAP_SIGMAS = 0.35
_MIN_OBSERVATIONS = 48

_JUMP_VARIANCE_FLOOR = 0.0003

STEP_HOURS: Dict[str, float] = {"24h": 1.0, "1T": 24.0, "1M": 24.0, "1R": 365.0 * 24.0 / 12.0}


def _clean_series(prices: List[List[float]]) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    for item in prices or []:
        try:
            ts, price = float(item[0]), float(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isfinite(ts) and math.isfinite(price) and price > 0:
            out.append((ts, price))
    out.sort(key=lambda p: p[0])
    return out


def estimate_sigma_per_hour(prices: List[List[float]]) -> Optional[float]:
    series = _clean_series(prices)
    if len(series) < _MIN_OBSERVATIONS:
        return None
    normalized: List[float] = []
    for (t0, p0), (t1, p1) in zip(series, series[1:]):
        dt_hours = (t1 - t0) / 3_600_000
        if dt_hours < 0.25:
            continue
        normalized.append(math.log(p1 / p0) / math.sqrt(dt_hours))
    if len(normalized) < _MIN_OBSERVATIONS - 1:
        return None
    sample_var = statistics.pvariance(normalized)
    ewma = statistics.pvariance(normalized[:24]) if len(normalized) >= 24 else sample_var
    for r in normalized:
        ewma = _EWMA_LAMBDA * ewma + (1 - _EWMA_LAMBDA) * r * r
    sigma = math.sqrt(0.5 * ewma + 0.5 * sample_var)
    return sigma if sigma > 0 else None


def _drift_per_hour(series: List[Tuple[float, float]]) -> float:
    now_ts, now_price = series[-1]
    target = now_ts - 168 * 3_600_000
    past_ts, past_price = min(series, key=lambda p: abs(p[0] - target))
    hours = (now_ts - past_ts) / 3_600_000
    if hours < 24:
        return 0.0
    return _DRIFT_DAMPING * math.log(now_price / past_price) / hours


def _fmt(value: float) -> float:
    return float(f"{value:.8g}")


def attach_uncertainty_band(parsed: Dict[str, Any], prices: List[List[float]], horizon: str) -> None:
    sigma_h = estimate_sigma_per_hour(prices)
    step = STEP_HOURS.get(horizon)
    ceny = parsed.get("ceny")
    if sigma_h is None or step is None or not isinstance(ceny, list) or not ceny:
        return
    lows, highs = [], []
    for i, price in enumerate(ceny, start=1):
        sigma_t = math.sqrt((sigma_h ** 2) * (step * i) + _JUMP_VARIANCE_FLOOR)
        spread = Z_80 * sigma_t
        lows.append(_fmt(float(price) * math.exp(-spread)))
        highs.append(_fmt(float(price) * math.exp(spread)))
    parsed["pasmo"] = {"dolne": lows, "horne": highs}
    parsed["denna_volatilita_pct"] = round(sigma_h * math.sqrt(24) * 100, 2)


def build_quant_forecast(coin: str, horizon: str, lang: str = "en") -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    coin = (coin or "").upper()
    coin_id = DEFAULT_COIN_IDS.get(coin)
    horizon_cfg = TIME_HORIZONS.get(horizon)
    if not coin_id or not horizon_cfg or horizon not in STEP_HOURS:
        return False, None, "Bezplatny model podporuje iba zakladne mince (BTC, ETH, SOL, ...)."
    try:
        ok, history, error = market_data.get_market_history(coin_id, 30)
    except Exception as exc:  # noqa: BLE001
        return False, None, f"Trhove data sa nepodarilo nacitat: {exc}"
    if not ok or not history.get("prices"):
        return False, None, error or "Trhove data momentalne nie su dostupne."

    series = _clean_series(history["prices"])
    sigma_h = estimate_sigma_per_hour(history["prices"])
    if sigma_h is None or len(series) < _MIN_OBSERVATIONS:
        return False, None, "Nedostatok historickych dat na odhad volatility."

    spot = series[-1][1]
    drift_h = _drift_per_hour(series)
    points = int(horizon_cfg["points"])
    step = STEP_HOURS[horizon]
    unit = unit_label(str(horizon_cfg["unit"]), lang)

    prices, lows, highs, labels = [], [], [], []
    for i in range(1, points + 1):
        h = step * i
        sigma_t = math.sqrt((sigma_h ** 2) * h + _JUMP_VARIANCE_FLOOR)
        cap = _DRIFT_CAP_SIGMAS * sigma_t
        mu = max(-cap, min(cap, drift_h * h))
        prices.append(_fmt(spot * math.exp(mu)))
        lows.append(_fmt(spot * math.exp(mu - Z_80 * sigma_t)))
        highs.append(_fmt(spot * math.exp(mu + Z_80 * sigma_t)))
        labels.append(f"{unit} {i}")

    sigma_day_pct = sigma_h * math.sqrt(24) * 100
    rel_width = (highs[-1] - lows[-1]) / prices[-1]
    confidence = round(max(15.0, min(92.0, 92.0 - rel_width * 90.0)), 1)
    risk = "Low" if sigma_day_pct < 2.0 else "Medium" if sigma_day_pct < 4.5 else "High"
    change_pct = (prices[-1] / spot - 1) * 100

    data = {
        "ceny": prices, "casove_body": labels,
        "odovodnenie": quant_reasoning(lang, coin, horizon, sigma_day_pct, change_pct, lows[-1], highs[-1], spot),
        "confidence_score": confidence, "risk_level": risk,
        "pasmo": {"dolne": lows, "horne": highs},
        "denna_volatilita_pct": round(sigma_day_pct, 2),
        "zdroje_dat": ["coingecko_market", "quant_model"],
        "vytvorene": datetime.now(timezone.utc).isoformat(),
        "aktualna_cena": _fmt(spot),
    }
    return True, data, None
