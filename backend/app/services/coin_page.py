"""Public coin pages (SEO): live price, the free model's outlook, market signals and how accurate each AI was."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, QUANT_LABEL
from app.models import ForecastEvaluation
from app.services import insights, market_data, quant_engine, signals
from app.utils.ttl_cache import TTLCache

_cache = TTLCache(ttl_seconds=600)


def _outlook(coin: str, horizon: str) -> Optional[Dict[str, Any]]:
    ok, data, _err = quant_engine.build_quant_forecast(coin, horizon, "en")
    if not ok or not data or not data.get("ceny") or not isinstance(data.get("aktualna_cena"), (int, float)):
        return None
    spot, final = data["aktualna_cena"], data["ceny"][-1]
    band = data.get("pasmo") or {}
    lows, highs = band.get("dolne") or [], band.get("horne") or []
    return {"horizon": horizon, "price": round(final, 8), "change_pct": round((final - spot) / spot * 100, 2),
            "low": round(lows[-1], 8) if lows else None, "high": round(highs[-1], 8) if highs else None}


def _accuracy(db: Session, coin: str) -> list:
    hits = func.sum(case((ForecastEvaluation.direction_correct == True, 1), else_=0))  # noqa: E712
    rows = (db.query(ForecastEvaluation.provider, func.count(), hits)
            .filter(ForecastEvaluation.coin == coin, ForecastEvaluation.is_demo.isnot(True))
            .group_by(ForecastEvaluation.provider).all())
    out = [{"provider": "Statistical model" if p == QUANT_LABEL else p, "forecasts": n,
            "hit_pct": round((h or 0) / n * 100, 1)} for p, n, h in rows if n]
    return sorted(out, key=lambda r: (r["forecasts"] >= 5, r["hit_pct"]), reverse=True)


def build(db: Session, coin: str) -> Optional[Dict[str, Any]]:
    coin = coin.upper()
    if coin not in DEFAULT_COIN_IDS:
        return None
    cached = _cache.get(coin)
    if cached is not None:
        return cached
    coin_id = DEFAULT_COIN_IDS[coin]
    ok, markets, _err = market_data.get_coin_markets([coin_id])
    m = (markets or {}).get(coin_id, {}) if ok else {}
    ok_h, history, _err = market_data.get_market_history(coin_id, 30)
    rsi = insights.daily_rsi(history.get("prices", [])) if ok_h else None
    day, week = _outlook(coin, "24h"), _outlook(coin, "1T")
    bundle = signals.collect(coin)
    items = [{k: v for k, v in s.items() if k != "note"} for s in bundle["items"] if s["tone"] != "neutral"][:8]
    page = {
        "coin": coin, "name": m.get("name") or coin, "price": m.get("current_price"), "market_cap": m.get("market_cap"),
        "rank": m.get("market_cap_rank"), "change_24h": m.get("price_change_percentage_24h_in_currency"),
        "change_7d": m.get("price_change_percentage_7d_in_currency"),
        "change_30d": m.get("price_change_percentage_30d_in_currency"),
        "rsi": rsi, "signal": insights.signal(day["change_pct"] if day else None, rsi),
        "outlook": [o for o in (day, week) if o], "signals": items, "balance": signals.score(bundle["items"]),
        "accuracy": _accuracy(db, coin), "updated_at": bundle.get("updated_at"),
    }
    if page["price"] or page["outlook"]:
        _cache.set(coin, page)
    return page
