"""Portfolio tracker (Premium): positions with cost basis, live P&L, risk score and a daily value history."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS
from app.models import PortfolioPosition, PortfolioSnapshot, User
from app.services import market_data
from app.services.premium import is_premium

MAX_POSITIONS = 30


def _quotes(coins: List[str]) -> Dict[str, Dict[str, Any]]:
    ok, markets, _err = market_data.get_coin_markets([DEFAULT_COIN_IDS[c] for c in coins if c in DEFAULT_COIN_IDS])
    return {c: (markets or {}).get(DEFAULT_COIN_IDS[c], {}) for c in coins} if ok else {}


def risk_score(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """1 (calm) .. 10 (very risky): value-weighted 30-day swing plus a penalty for concentration."""
    total = sum(r["value"] for r in rows)
    if not total:
        return {"score": None, "level": None}
    swing = sum(r["value"] / total * abs(r.get("change_30d") or 0) for r in rows)
    top_share = max(r["value"] for r in rows) / total
    score = round(min(10.0, max(1.0, swing / 4 + max(0.0, top_share - 0.5) * 6)), 1)
    return {"score": score, "level": "low" if score < 4 else "medium" if score < 7 else "high",
            "top_share_pct": round(top_share * 100, 1)}


def summary(db: Session, user: User) -> Dict[str, Any]:
    positions = db.query(PortfolioPosition).filter(PortfolioPosition.user_id == user.id).order_by(PortfolioPosition.coin).all()
    quotes = _quotes([p.coin for p in positions])
    rows = []
    for p in positions:
        q = quotes.get(p.coin, {})
        price = q.get("current_price") if isinstance(q.get("current_price"), (int, float)) else None
        cost = p.avg_buy_price * p.amount
        value = price * p.amount if price else None          # no quote: unknown, never counted as a loss
        rows.append({"id": p.id, "coin": p.coin, "amount": p.amount, "avg_buy_price": p.avg_buy_price, "price": price,
                     "value": round(value, 2) if value is not None else None, "cost": round(cost, 2),
                     "pnl": round(value - cost, 2) if value is not None else None,
                     "pnl_pct": round((value - cost) / cost * 100, 2) if value is not None and cost else None,
                     "change_24h": q.get("price_change_percentage_24h_in_currency"),
                     "change_30d": q.get("price_change_percentage_30d_in_currency")})
    priced = [r for r in rows if r["value"] is not None]
    total_value = sum(r["value"] for r in priced)
    total_cost = sum(r["cost"] for r in priced)
    for r in rows:
        r["allocation_pct"] = round(r["value"] / total_value * 100, 1) if total_value and r["value"] is not None else None
    history = (db.query(PortfolioSnapshot).filter(PortfolioSnapshot.user_id == user.id)
               .order_by(PortfolioSnapshot.day.desc()).limit(180).all())
    changes = [r["change_24h"] for r in priced if isinstance(r.get("change_24h"), (int, float))]
    return {
        "positions": rows, "max": MAX_POSITIONS,
        "total": {"value": round(total_value, 2), "cost": round(total_cost, 2), "pnl": round(total_value - total_cost, 2),
                  "pnl_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost else None,
                  "change_24h_pct": round(sum(r["value"] * (r["change_24h"] or 0) for r in priced) / total_value, 2)
                  if total_value and changes else None},
        "risk": risk_score(priced), "unpriced": len(rows) - len(priced),
        "dispersion_24h": round(statistics.pstdev(changes), 2) if len(changes) > 1 else None,
        "history": [{"day": s.day, "value": s.value_usd, "cost": s.cost_usd} for s in reversed(history)],
    }


def take_snapshots(db: Session) -> int:
    """Daily job: store today's value for every Premium user with positions."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user_ids = [uid for (uid,) in db.query(PortfolioPosition.user_id).distinct().all()]
    taken = 0
    for uid in user_ids:
        user = db.get(User, uid)
        if user is None or not is_premium(user):
            continue
        data = summary(db, user)
        if not data["total"]["value"] or data["unpriced"]:
            continue                      # incomplete quotes would draw a fake dip in the history
        row = db.query(PortfolioSnapshot).filter(PortfolioSnapshot.user_id == uid, PortfolioSnapshot.day == day).first()
        if row is None:
            db.add(PortfolioSnapshot(user_id=uid, day=day, value_usd=data["total"]["value"], cost_usd=data["total"]["cost"]))
        else:
            row.value_usd, row.cost_usd = data["total"]["value"], data["total"]["cost"]
        taken += 1
    db.commit()
    return taken
