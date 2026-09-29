"""One-click demo data: real statistical-model forecasts made retroactively.

Each demo forecast is what the quant model would have produced on a past date using only the
prices known on that date (same code as the live model). Older ones have already matured, so
their accuracy is evaluated against real prices - the history, accuracy badges and leaderboard
have something honest to show during a presentation."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, QUANT_LABEL, TIME_HORIZONS
from app.i18n_content import quant_reasoning, unit_label
from app.models import ForecastEvaluation, ForecastHistory, PriceTip
from app.services import market_data, quant_engine

DEMO_FLAG = "demo"
# (coin, horizon, days ago). 1T forecasts from 7+ days ago are already evaluated; the rest are pending.
DEMO_PLAN: List[Tuple[str, str, int]] = [
    ("BTC", "1T", 28), ("BTC", "1T", 21), ("BTC", "1T", 14), ("BTC", "1T", 8),
    ("ETH", "1T", 28), ("ETH", "1T", 14), ("ETH", "1T", 8),
    ("SOL", "1T", 21), ("SOL", "1T", 8),
    ("BTC", "1M", 12), ("ETH", "1T", 3),
]
_LOOKBACK_DAYS = 90
_DAY_MS = 86_400_000


def _forecast_at(series: List[Tuple[float, float]], origin_ts: float, coin: str, horizon: str,
                 lang: str) -> Optional[dict]:
    window = [p for p in series if p[0] <= origin_ts][-_LOOKBACK_DAYS:]
    if len(window) < _LOOKBACK_DAYS // 2:
        return None
    sigma_h = quant_engine.estimate_sigma_per_hour([list(p) for p in window])
    if sigma_h is None:
        return None
    points = int(TIME_HORIZONS[horizon]["points"])
    prices, lows, highs = quant_engine.project_path(window, sigma_h, 24.0, points)
    spot = window[-1][1]
    created = datetime.fromtimestamp(window[-1][0] / 1000, tz=timezone.utc)
    sigma_day_pct = sigma_h * math.sqrt(24) * 100
    unit = unit_label(str(TIME_HORIZONS[horizon]["unit"]), lang)
    return {
        "ceny": prices, "casove_body": [f"{unit} {i}" for i in range(1, points + 1)],
        "odovodnenie": quant_reasoning(lang, coin, horizon, sigma_day_pct, (prices[-1] / spot - 1) * 100,
                                       lows[-1], highs[-1], spot),
        "pasmo": {"dolne": lows, "horne": highs}, "denna_volatilita_pct": round(sigma_day_pct, 2),
        "confidence_score": round(max(15.0, min(92.0, 92.0 - (highs[-1] - lows[-1]) / prices[-1] * 90.0)), 1),
        "risk_level": "Low" if sigma_day_pct < 2.0 else "Medium" if sigma_day_pct < 4.5 else "High",
        "zdroje_dat": ["coingecko_market", "quant_model"], "aktualna_cena": spot,
        "vytvorene": created.isoformat(), DEMO_FLAG: True,
    }


def _is_demo(row: ForecastHistory) -> bool:
    try:
        return bool(json.loads(row.forecast_json).get(DEMO_FLAG))
    except (json.JSONDecodeError, AttributeError):
        return False


def remove_demo_data(db: Session, user_id: int) -> int:
    rows = [r for r in db.query(ForecastHistory).filter(ForecastHistory.user_id == user_id).all() if _is_demo(r)]
    ids = [r.id for r in rows]
    if ids:
        db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(PriceTip).filter(PriceTip.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(ForecastHistory).filter(ForecastHistory.id.in_(ids)).delete(synchronize_session=False)
    return len(ids)


def create_demo_data(db: Session, user_id: int, lang: str = "en",
                     now: Optional[datetime] = None) -> Tuple[int, List[str]]:
    """Replace the user's demo forecasts. Returns (created count, coins whose data was unavailable)."""
    now = now or datetime.now(timezone.utc)
    remove_demo_data(db, user_id)
    series_by_coin, missing = {}, []
    for coin in sorted({c for c, _h, _d in DEMO_PLAN}):
        ok, history, _err = market_data.get_market_history(DEFAULT_COIN_IDS[coin], 365)
        series = quant_engine._clean_series(history.get("prices", [])) if ok else []
        if series:
            series_by_coin[coin] = series
        else:
            missing.append(coin)

    created = 0
    for coin, horizon, days_ago in DEMO_PLAN:
        series = series_by_coin.get(coin)
        if not series:
            continue
        data = _forecast_at(series, now.timestamp() * 1000 - days_ago * _DAY_MS, coin, horizon, lang)
        if data is None:
            continue
        created_at = datetime.fromisoformat(data["vytvorene"]).replace(tzinfo=None)
        db.add(ForecastHistory(user_id=user_id, crypto_symbol=coin, timeframe=horizon, model_used=QUANT_LABEL,
                               forecast_json=json.dumps(data, ensure_ascii=False), created_at=created_at))
        created += 1
    return created, missing
