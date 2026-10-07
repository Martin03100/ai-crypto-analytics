"""Personal statistics (Premium) and the full data export (GDPR access / portability)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent, CommunityVote, ForecastEvaluation, ForecastHistory, ForecastSchedule, Notification, PortfolioHistory,
    PortfolioPosition, PortfolioSnapshot, PriceAlert, PriceTip, User,
)


def _group(db: Session, user_id: int, column) -> list[dict]:
    beats = case(((ForecastEvaluation.baseline_accuracy_pct.isnot(None))
                  & (ForecastEvaluation.accuracy_pct > ForecastEvaluation.baseline_accuracy_pct), 1), else_=0)
    rows = (db.query(column, func.count(), func.sum(case((ForecastEvaluation.direction_correct == True, 1), else_=0)),  # noqa: E712
                     func.avg(ForecastEvaluation.accuracy_pct), func.sum(beats))
            .filter(ForecastEvaluation.user_id == user_id, ForecastEvaluation.is_demo.isnot(True))
            .group_by(column).all())
    out = [{"key": key, "evaluated": n, "direction_hit_pct": round((h or 0) / n * 100, 1),
            "avg_accuracy_pct": round(acc or 0.0, 1), "beats_baseline_pct": round((b or 0) / n * 100, 1)}
           for key, n, h, acc, b in rows]
    return sorted(out, key=lambda r: (r["evaluated"], r["direction_hit_pct"]), reverse=True)


def personal_stats(db: Session, user_id: int) -> dict:
    tips = dict(db.query(PriceTip.outcome, func.count()).filter(
        PriceTip.user_id == user_id, PriceTip.outcome.isnot(None), PriceTip.is_demo.isnot(True)).group_by(PriceTip.outcome).all())
    by_provider = _group(db, user_id, ForecastEvaluation.provider)
    total = sum(r["evaluated"] for r in by_provider)
    hits = sum(r["evaluated"] * r["direction_hit_pct"] / 100 for r in by_provider)
    return {
        "total_evaluated": total,
        "direction_hit_pct": round(hits / total * 100, 1) if total else None,
        "by_provider": by_provider,
        "by_coin": _group(db, user_id, ForecastEvaluation.coin),
        "by_horizon": _group(db, user_id, ForecastEvaluation.timeframe),
        "duels": {"wins": tips.get("win", 0), "losses": tips.get("loss", 0), "ties": tips.get("tie", 0)},
    }


def _rows(db: Session, model, user_id: int, fields: tuple[str, ...]) -> list[dict]:
    out = []
    for row in db.query(model).filter(model.user_id == user_id).all():
        item = {}
        for f in fields:
            value = getattr(row, f, None)
            if isinstance(value, str) and f.endswith("_json"):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            item[f.removesuffix("_json")] = value
        out.append(item)
    return out


def export_user_data(db: Session, user: User) -> dict:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {"username": user.username, "email": user.email, "email_verified": user.email_verified,
                    "created_at": user.created_at, "language": user.lang, "nickname": user.nickname,
                    "two_factor": bool(user.totp_enabled), "premium_until": user.premium_until,
                    "weekly_email": bool(user.digest_opt_in), "morning_briefing": bool(user.briefing_opt_in),
                    "referral_code": user.referral_code, "watchlist": user.watchlist_json},
        "connected_ai_providers": [k.provider for k in user.api_keys],
        "forecasts": _rows(db, ForecastHistory, user.id, ("id", "crypto_symbol", "timeframe", "model_used", "created_at", "forecast_json")),
        "forecast_evaluations": _rows(db, ForecastEvaluation, user.id, ("forecast_id", "provider", "coin", "timeframe", "accuracy_pct",
                                                                        "direction_correct", "evaluated_at")),
        "portfolio_analyses": _rows(db, PortfolioHistory, user.id, ("id", "created_at", "model_used", "holdings_json", "analysis_json")),
        "price_tips": _rows(db, PriceTip, user.id, ("forecast_id", "tip_price", "ai_price", "outcome", "created_at")),
        "schedules": _rows(db, ForecastSchedule, user.id, ("coin", "horizon", "provider", "frequency", "hour", "minute", "timezone", "active")),
        "price_alerts": _rows(db, PriceAlert, user.id, ("kind", "coin", "direction", "target_price", "active", "created_at",
                                                        "triggered_at")),
        "portfolio_positions": _rows(db, PortfolioPosition, user.id, ("coin", "amount", "avg_buy_price", "created_at")),
        "portfolio_history": _rows(db, PortfolioSnapshot, user.id, ("day", "value_usd", "cost_usd")),
        "community_votes": _rows(db, CommunityVote, user.id, ("sentiment_vote", "voted_at")),
        "notifications": _rows(db, Notification, user.id, ("kind", "data_json", "created_at", "read_at")),
        "account_activity": _rows(db, AuditEvent, user.id, ("action", "ip", "user_agent", "created_at")),
    }
