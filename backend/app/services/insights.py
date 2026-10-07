"""Premium analytics: smart model choice, AI consensus, strategy simulator and the market scanner."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, HORIZON_HOURS, QUANT_LABEL
from app.models import ForecastEvaluation, ForecastHistory
from app.services import backtest, market_data, quant_engine
from app.utils.ttl_cache import TTLCache

PRIOR = 10            # pseudo-forecasts at 50 %: small samples cannot top the ranking by luck
MIN_SAMPLE = 5
FREE_SCANNER_COINS = ("BTC", "ETH", "SOL", "BNB", "XRP")
_scanner_cache = TTLCache(ttl_seconds=15 * 60)


# ---------- smart model ----------

def _rank_rows(rows) -> List[Dict[str, Any]]:
    ranked = []
    for provider, n, hits, acc in rows:
        score = ((hits or 0) + PRIOR / 2) / (n + PRIOR)
        ranked.append({"provider": provider, "evaluated": n, "direction_hit_pct": round((hits or 0) / n * 100, 1),
                       "avg_accuracy_pct": round(acc or 0.0, 1), "score": round(score * 100, 1)})
    return sorted(ranked, key=lambda r: (r["score"], r["evaluated"]), reverse=True)


def model_ranking(db: Session, coin: str, horizon: str) -> Dict[str, Any]:
    """Best provider for this coin and horizon; falls back to the horizon, then to all data when samples are thin."""
    hit = func.sum(case((ForecastEvaluation.direction_correct == True, 1), else_=0))  # noqa: E712
    base = db.query(ForecastEvaluation.provider, func.count(), hit, func.avg(ForecastEvaluation.accuracy_pct)).filter(
        ForecastEvaluation.is_demo.isnot(True))
    scopes = [("coin_horizon", base.filter(ForecastEvaluation.coin == coin, ForecastEvaluation.timeframe == horizon)),
              ("horizon", base.filter(ForecastEvaluation.timeframe == horizon)), ("all", base)]
    for scope, query in scopes:
        ranked = _rank_rows(query.group_by(ForecastEvaluation.provider).all())
        if sum(r["evaluated"] for r in ranked) >= MIN_SAMPLE:
            return {"scope": scope, "ranking": ranked, "best": ranked[0]["provider"] if ranked else None}
    return {"scope": "none", "ranking": [], "best": QUANT_LABEL}


def model_weights(db: Session, coin: str, horizon: str) -> Dict[str, float]:
    return {r["provider"]: r["score"] / 100 for r in model_ranking(db, coin, horizon)["ranking"]}


# ---------- consensus ----------

def consensus(forecasts: List[Dict[str, Any]], weights: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """forecasts: [{model, start, final}] -> weighted verdict, agreement and target range."""
    rows = [f for f in forecasts if isinstance(f.get("start"), (int, float)) and isinstance(f.get("final"), (int, float))
            and f["start"] > 0 and f["final"] > 0]
    if not rows:
        return None
    up = down = 0.0
    changes = []
    for f in rows:
        w = weights.get(f["model"], 0.5)
        change = (f["final"] - f["start"]) / f["start"] * 100
        changes.append(change)
        if change >= 0:
            up += w
        else:
            down += w
    total = up + down
    direction = "up" if up >= down else "down"
    agreement = round(max(up, down) / total * 100) if total else 0
    return {
        "direction": direction, "agreement_pct": agreement, "models": len(rows),
        "median_change_pct": round(statistics.median(changes), 2),
        "min_change_pct": round(min(changes), 2), "max_change_pct": round(max(changes), 2),
        "strength": "strong" if agreement >= 80 and len(rows) >= 3 else "moderate" if agreement >= 60 else "split",
    }


# ---------- strategy simulator ----------

def _simulate(trades: List[Dict[str, float]], allow_short: bool, fee_pct: float) -> Optional[Dict[str, Any]]:
    """trades: chronological, non-overlapping [{date, start, predicted, actual}]."""
    if not trades:
        return None
    equity = hodl = 1.0
    peak, max_dd, wins, taken = 1.0, 0.0, 0, 0
    curve = [{"date": trades[0]["date"], "strategy": 100.0, "hodl": 100.0}]
    for t in trades:
        ret = t["actual"] / t["start"] - 1
        hodl *= 1 + ret
        side = 1 if t["predicted"] > t["start"] else (-1 if allow_short else 0)
        if side:
            taken += 1
            trade_ret = side * ret - 2 * fee_pct / 100
            wins += trade_ret > 0
            equity *= 1 + trade_ret
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        curve.append({"date": t["date"], "strategy": round(equity * 100, 2), "hodl": round(hodl * 100, 2)})
    return {
        "trades": taken, "periods": len(trades), "win_rate_pct": round(wins / taken * 100, 1) if taken else None,
        "strategy_return_pct": round((equity - 1) * 100, 2), "hodl_return_pct": round((hodl - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2), "curve": curve,
    }


def _non_overlapping(trades: List[Dict[str, Any]], hours: float) -> List[Dict[str, Any]]:
    out, next_free = [], -math.inf
    for t in sorted(trades, key=lambda x: x["ts"]):
        if t["ts"] >= next_free:
            out.append(t)
            next_free = t["ts"] + hours * 3600
    return out


def quant_trades(coin: str, horizon: str) -> Optional[List[Dict[str, Any]]]:
    ok, result, _err = backtest.run_backtest(coin, horizon)
    if not ok or not result:
        return None
    trades = [{"date": s["date"], "ts": datetime.fromisoformat(s["date"]).timestamp(), "start": s["start"],
               "predicted": s["predicted"], "actual": s["actual"]} for s in result["samples"]]
    return _non_overlapping(trades, HORIZON_HOURS[horizon])


def ai_trades(db: Session, provider: str, coin: str, horizon: str) -> List[Dict[str, Any]]:
    rows = (db.query(ForecastEvaluation, ForecastHistory).join(ForecastHistory, ForecastHistory.id == ForecastEvaluation.forecast_id)
            .filter(ForecastEvaluation.provider == provider, ForecastEvaluation.coin == coin,
                    ForecastEvaluation.timeframe == horizon, ForecastEvaluation.is_demo.isnot(True)).all())
    trades = []
    for ev, fh in rows:
        try:
            data = json.loads(fh.forecast_json)
        except json.JSONDecodeError:
            continue
        prices, start = data.get("ceny"), data.get("aktualna_cena")
        if not isinstance(start, (int, float)) or start <= 0 or not isinstance(prices, list) or not prices:
            continue
        if not isinstance(prices[-1], (int, float)):
            continue
        trades.append({"date": fh.created_at.isoformat(), "ts": fh.created_at.timestamp(), "start": float(start),
                       "predicted": float(prices[-1]), "actual": ev.actual_final_price})
    return _non_overlapping(trades, HORIZON_HOURS.get(horizon, 24))


def simulate(db: Session, coin: str, horizon: str, model: str, allow_short: bool, fee_pct: float) -> Optional[Dict[str, Any]]:
    trades = quant_trades(coin, horizon) if model == QUANT_LABEL else ai_trades(db, model, coin, horizon)
    result = _simulate(trades or [], allow_short, fee_pct)
    if result:
        result.update({"coin": coin, "horizon": horizon, "model": model, "allow_short": allow_short, "fee_pct": fee_pct})
    return result


# ---------- market scanner ----------

def daily_rsi(prices: List[List[float]], period: int = 14) -> Optional[float]:
    closes: Dict[int, float] = {}
    for ts, price in prices or []:
        closes[int(ts // 86_400_000)] = price
    series = [closes[d] for d in sorted(closes)]
    if len(series) < period + 1:
        return None
    deltas = [series[i] - series[i - 1] for i in range(len(series) - period, len(series))]
    gains = sum(d for d in deltas if d > 0) / period
    losses = sum(-d for d in deltas if d < 0) / period
    return 100.0 if losses == 0 else round(100 - 100 / (1 + gains / losses), 1)


def signal(expected_pct: Optional[float], rsi: Optional[float]) -> str:
    if rsi is not None and rsi >= 75:
        return "overbought"
    if rsi is not None and rsi <= 25:
        return "oversold"
    if expected_pct is not None and expected_pct >= 0.5:
        return "bullish"
    if expected_pct is not None and expected_pct <= -0.5:
        return "bearish"
    return "neutral"


def _scan_coin(coin: str, market: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "coin": coin, "price": market.get("current_price"), "market_cap": market.get("market_cap"),
        "change_24h": market.get("price_change_percentage_24h_in_currency"),
        "change_7d": market.get("price_change_percentage_7d_in_currency"),
        "change_30d": market.get("price_change_percentage_30d_in_currency"),
        "expected_24h_pct": None, "range_pct": None, "rsi": None,
    }
    ok, history, _err = market_data.get_market_history(DEFAULT_COIN_IDS[coin], 30)
    if ok:
        row["rsi"] = daily_rsi(history.get("prices", []))
    ok, data, _err = quant_engine.build_quant_forecast(coin, "24h", "en")
    if ok and data and isinstance(data.get("aktualna_cena"), (int, float)) and data.get("ceny"):
        spot = data["aktualna_cena"]
        band = data.get("pasmo") or {}
        row["expected_24h_pct"] = round((data["ceny"][-1] - spot) / spot * 100, 2)
        if band.get("dolne") and band.get("horne"):
            row["range_pct"] = round((band["horne"][-1] - band["dolne"][-1]) / spot * 100, 2)
        row["price"] = row["price"] or spot
    row["signal"] = signal(row["expected_24h_pct"], row["rsi"])
    return row


def scan_market() -> List[Dict[str, Any]]:
    cached = _scanner_cache.get("all")
    if cached is not None:
        return cached
    _ok, markets, _err = market_data.get_coin_markets(list(DEFAULT_COIN_IDS.values()))
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda c: _scan_coin(c, (markets or {}).get(DEFAULT_COIN_IDS[c], {})), DEFAULT_COIN_IDS))
    rows = [r for r in rows if r["price"]]
    rows.sort(key=lambda r: abs(r["expected_24h_pct"] or 0), reverse=True)
    if rows:
        _scanner_cache.set("all", rows)
    return rows
