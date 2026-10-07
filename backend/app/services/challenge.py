"""Weekly "Beat the AI" challenge: one coin per week, guesses close on Thursday, the closest guess wins on Monday."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS
from app.models import Challenge, ChallengeEntry, User
from app.services import market_data, quant_engine
from app.services.notifications import notify

logger = logging.getLogger("aca.challenge")

ENTRY_WINDOW = timedelta(days=3)                 # Monday 00:00 → Thursday 00:00 UTC
ROTATION = ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "LINK", "AVAX", "SUI", "TON", "DOT")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def week_start(now: datetime) -> datetime:
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def week_id(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def coin_for(week: str) -> str:
    year, num = week.split("-W")
    return ROTATION[(int(year) * 53 + int(num)) % len(ROTATION)]


def _price(coin: str) -> Optional[float]:
    ok, prices, _err = market_data.get_live_prices([DEFAULT_COIN_IDS[coin]])
    value = (prices or {}).get(DEFAULT_COIN_IDS[coin], {}).get("usd") if ok else None
    return float(value) if isinstance(value, (int, float)) and value > 0 else None


def current(db: Session, now: Optional[datetime] = None) -> Optional[Challenge]:
    """This week's round, created on first use (needs a live price)."""
    now = now or utcnow()
    week = week_id(now)
    row = db.get(Challenge, week)
    if row is not None:
        return row
    coin = coin_for(week)
    start = _price(coin)
    if start is None:
        return None
    ok, data, _err = quant_engine.build_quant_forecast(coin, "1T", "en")
    ai = data["ceny"][-1] if ok and data and data.get("ceny") else None
    row = Challenge(week=week, coin=coin, start_price=start, ai_price=ai)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:                     # created by a parallel request
        db.rollback()
        row = db.get(Challenge, week)
    return row


def deadline(row: Challenge) -> datetime:
    year, num = row.week.split("-W")
    monday = datetime.fromisocalendar(int(year), int(num), 1)
    return monday + ENTRY_WINDOW


def enter(db: Session, user: User, price: float, now: Optional[datetime] = None) -> ChallengeEntry:
    now = now or utcnow()
    row = current(db, now)
    if row is None:
        raise ValueError("Výzvu sa teraz nepodarilo načítať. Skús to neskôr.")
    if now >= deadline(row):
        raise ValueError("Tipy na tento týždeň sú už uzavreté.")
    if not row.start_price * 0.2 <= price <= row.start_price * 5:
        raise ValueError("Tip je mimo rozumného rozsahu.")
    entry = ChallengeEntry(week=row.week, user_id=user.id, price=price, week_user=f"{row.week}:{user.id}")
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Tento týždeň už máš tip.") from None
    return entry


def settle_due(db: Session, now: Optional[datetime] = None) -> int:
    """Background job (Mondays): closes every past round that has not been settled yet."""
    now = now or utcnow()
    settled = 0
    for row in db.query(Challenge).filter(Challenge.settled_at.is_(None), Challenge.week != week_id(now)).all():
        end = _price(row.coin)
        if end is None:
            continue
        row.end_price, row.settled_at = end, now
        entries = db.query(ChallengeEntry).filter(ChallengeEntry.week == row.week).all()
        best = min(entries, key=lambda e: (abs(e.price - end), e.created_at), default=None)
        if best is not None:
            row.winner_user_id = best.user_id
            notify(db, best.user_id, "challenge_won", coin=row.coin, week=row.week, price=best.price, end=end)
        settled += 1
    db.commit()
    return settled


def wins(db: Session, user_id: int) -> int:
    return db.query(Challenge).filter(Challenge.winner_user_id == user_id).count()


def _error_pct(guess: Optional[float], end: Optional[float]) -> Optional[float]:
    return round(abs(guess - end) / end * 100, 2) if guess and end else None


def summary(db: Session, user: Optional[User] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or utcnow()
    row = current(db, now)
    out: Dict[str, Any] = {"current": None, "last": None}
    if row is not None:
        out["current"] = {"week": row.week, "coin": row.coin, "start_price": row.start_price, "ai_price": row.ai_price,
                          "deadline": deadline(row).isoformat() + "Z", "open": now < deadline(row),
                          "ends_at": (deadline(row) + timedelta(days=4)).isoformat() + "Z",
                          "entries": db.query(ChallengeEntry).filter(ChallengeEntry.week == row.week).count()}
        if user is not None:
            mine = db.query(ChallengeEntry).filter(ChallengeEntry.week == row.week, ChallengeEntry.user_id == user.id).first()
            out["current"]["my_price"] = mine.price if mine else None
    last = (db.query(Challenge).filter(Challenge.settled_at.isnot(None)).order_by(Challenge.settled_at.desc()).first())
    if last is not None:
        entries = db.query(ChallengeEntry).filter(ChallengeEntry.week == last.week).all()
        ai_error = _error_pct(last.ai_price, last.end_price)
        winner = db.get(User, last.winner_user_id) if last.winner_user_id else None
        best = next((e for e in entries if e.user_id == last.winner_user_id), None)
        out["last"] = {"week": last.week, "coin": last.coin, "end_price": last.end_price, "ai_price": last.ai_price,
                       "ai_error_pct": ai_error, "entries": len(entries),
                       "beat_ai": sum(1 for e in entries if ai_error is not None and _error_pct(e.price, last.end_price) < ai_error),
                       "winner": (winner.nickname or "anonymous") if winner else None,
                       "winner_error_pct": _error_pct(best.price if best else None, last.end_price),
                       "you_won": bool(user and last.winner_user_id == user.id)}
    if user is not None:
        out["my_wins"] = wins(db, user.id)
    return out
