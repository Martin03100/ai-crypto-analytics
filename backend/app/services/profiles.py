"""Public tipster profiles, accuracy over time and the weekly "AI vs reality" summary."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import QUANT_LABEL
from app.models import Challenge, ChallengeEntry, ForecastEvaluation, ForecastHistory, PriceTip, User
from app.services.premium import ambassador_badge, invited_signups
from app.utils.ttl_cache import TTLCache

_cache = TTLCache(ttl_seconds=600)
TIMELINE_WEEKS = 12
RECENT = 15


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


def _provider(name: str) -> str:
    return "quant" if name == QUANT_LABEL else name


# ---------- tipster profile ----------

def tipster(db: Session, nickname: str) -> Optional[Dict[str, Any]]:
    user = (db.query(User).filter(func.lower(User.nickname) == nickname.lower(), User.disabled.isnot(True)).first())
    if user is None:
        return None
    rows = (db.query(PriceTip, ForecastHistory.crypto_symbol, ForecastHistory.timeframe, ForecastEvaluation.actual_final_price)
            .join(ForecastHistory, ForecastHistory.id == PriceTip.forecast_id)
            .outerjoin(ForecastEvaluation, ForecastEvaluation.forecast_id == PriceTip.forecast_id)
            .filter(PriceTip.user_id == user.id, PriceTip.is_demo.isnot(True), PriceTip.outcome.isnot(None))
            .order_by(PriceTip.created_at.desc()).all())
    counts = {"win": 0, "loss": 0, "tie": 0}
    for tip, *_ in rows:
        counts[tip.outcome] = counts.get(tip.outcome, 0) + 1
    streak = 0
    for tip, *_ in rows:
        if tip.outcome != "win":
            break
        streak += 1
    total = sum(counts.values())
    rounds = (db.query(ChallengeEntry, Challenge).join(Challenge, Challenge.week == ChallengeEntry.week)
              .filter(ChallengeEntry.user_id == user.id, Challenge.end_price.isnot(None))
              .order_by(Challenge.week.desc()).limit(10).all())
    return {
        "nickname": user.nickname, "member_since": _iso(user.created_at),
        "badge": ambassador_badge(invited_signups(db, user.id)),
        "duels": {"total": total, **counts, "win_pct": round(counts["win"] / total * 100) if total else None,
                  "streak": streak},
        "recent": [{"coin": coin, "horizon": tf, "tip": tip.tip_price, "ai": tip.ai_price, "actual": actual,
                    "outcome": tip.outcome, "at": _iso(tip.created_at)} for tip, coin, tf, actual in rows[:RECENT]],
        "challenge": {
            "wins": sum(1 for _e, c in rounds if c.winner_user_id == user.id),
            "rounds": [{"week": c.week, "coin": c.coin, "guess": e.price, "end": c.end_price,
                        "error_pct": round(abs(e.price - c.end_price) / c.end_price * 100, 2),
                        "won": c.winner_user_id == user.id} for e, c in rounds],
        },
    }


# ---------- accuracy over time ----------

def week_key(dt: datetime) -> str:
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def timeline(db: Session, now: Optional[datetime] = None, weeks: int = TIMELINE_WEEKS) -> Dict[str, Any]:
    use_cache = now is None and weeks == TIMELINE_WEEKS
    if use_cache and _cache.get("timeline") is not None:
        return _cache.get("timeline")
    now = now or _now()
    start = (now - timedelta(weeks=weeks - 1))
    start = (start - timedelta(days=start.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    keys = [week_key(start + timedelta(weeks=i)) for i in range(weeks)]
    rows = (db.query(ForecastEvaluation.provider, ForecastEvaluation.evaluated_at, ForecastEvaluation.direction_correct,
                     ForecastEvaluation.accuracy_pct)
            .filter(ForecastEvaluation.evaluated_at >= start, ForecastEvaluation.is_demo.isnot(True)).all())
    acc: Dict[str, Dict[str, List]] = defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0]))
    for provider, at, hit, accuracy in rows:
        cell = acc[_provider(provider)][week_key(at)]
        cell[0] += 1
        cell[1] += bool(hit)
        cell[2] += accuracy or 0.0
    providers = []
    for provider, by_week in sorted(acc.items(), key=lambda kv: -sum(c[0] for c in kv[1].values())):
        points = []
        for key in keys:
            n, hits, total_acc = by_week.get(key, (0, 0, 0.0))
            points.append({"week": key, "n": n, "hit_pct": round(hits / n * 100, 1) if n else None,
                           "accuracy_pct": round(total_acc / n, 1) if n else None})
        providers.append({"provider": provider, "n": sum(p["n"] for p in points), "points": points})
    out = {"weeks": keys, "providers": providers, "generated_at": _iso(now)}
    if use_cache:
        _cache.set("timeline", out)
    return out


# ---------- weekly summary ----------

def weekly_summary(db: Session, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or _now()
    since = now - timedelta(days=7)
    rows = (db.query(ForecastEvaluation).filter(ForecastEvaluation.evaluated_at >= since,
                                                 ForecastEvaluation.is_demo.isnot(True)).all())
    by: Dict[str, List[ForecastEvaluation]] = defaultdict(list)
    for r in rows:
        by[_provider(r.provider)].append(r)
    providers = sorted(({"provider": p, "n": len(items),
                         "hit_pct": round(sum(bool(i.direction_correct) for i in items) / len(items) * 100, 1),
                         "accuracy_pct": round(sum(i.accuracy_pct for i in items) / len(items), 1)}
                        for p, items in by.items()), key=lambda r: (r["n"] >= 3, r["hit_pct"], r["n"]), reverse=True)
    best = max(rows, key=lambda r: r.accuracy_pct, default=None)
    tips = dict(db.query(PriceTip.outcome, func.count()).filter(PriceTip.created_at >= since, PriceTip.outcome.isnot(None),
                                                               PriceTip.is_demo.isnot(True))
                .group_by(PriceTip.outcome).all())
    last = (db.query(Challenge).filter(Challenge.end_price.isnot(None)).order_by(Challenge.week.desc()).first())
    winner = db.get(User, last.winner_user_id) if last and last.winner_user_id else None
    total = len(rows)
    return {
        "from": _iso(since), "to": _iso(now), "forecasts": total,
        "hit_pct": round(sum(bool(r.direction_correct) for r in rows) / total * 100, 1) if total else None,
        "providers": providers,
        "best": {"provider": _provider(best.provider), "coin": best.coin, "horizon": best.timeframe,
                 "accuracy_pct": round(best.accuracy_pct, 1)} if best else None,
        "humans_vs_ai": {"wins": tips.get("win", 0), "losses": tips.get("loss", 0), "ties": tips.get("tie", 0)},
        "challenge": {"week": last.week, "coin": last.coin, "end": last.end_price,
                      "winner": winner.nickname if winner and winner.nickname else None} if last else None,
    }
