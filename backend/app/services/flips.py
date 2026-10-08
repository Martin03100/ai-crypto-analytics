"""Background checks that notify users: "the AI changed its mind" and calendar reminders.

Direction flips: every few hours the free statistical model's 24h outlook is computed for the coins on
users' watchlists. When the outlook turns from rising to falling (or back) - ignoring small moves and
at most once per coin per cooldown - everyone following that coin gets a notification."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional, Set

from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS
from app.models import CoinSignalState, EventReminder, User
from app.services import push
from app.services.notifications import notify

logger = logging.getLogger(__name__)

FLAT_BAND_PCT = 0.4                  # |24h change| below this is "no clear view"
COOLDOWN = timedelta(hours=12)
STALE_AFTER = timedelta(hours=24)
MAX_COINS = 20
DEFAULT_WATCHLIST = ["BTC", "ETH", "SOL"]
REMIND_BEFORE = timedelta(minutes=60)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def direction(change_pct: Optional[float]) -> str:
    if change_pct is None or abs(change_pct) < FLAT_BAND_PCT:
        return "flat"
    return "up" if change_pct > 0 else "down"


def watchers(db: Session) -> Dict[str, Set[int]]:
    """coin -> ids of active users who follow it."""
    out: Dict[str, Set[int]] = {}
    for user_id, raw, disabled in db.query(User.id, User.watchlist_json, User.disabled).all():
        if disabled:
            continue
        try:
            coins = json.loads(raw) if raw else DEFAULT_WATCHLIST
        except (json.JSONDecodeError, TypeError):
            coins = DEFAULT_WATCHLIST
        for coin in coins if isinstance(coins, list) else []:
            if coin in DEFAULT_COIN_IDS:
                out.setdefault(coin, set()).add(user_id)
    return out


def _quant_change(coin: str) -> Optional[float]:
    from app.services.coin_page import _outlook
    outlook = _outlook(coin, "24h")
    return outlook["change_pct"] if outlook else None


def check_flips(db: Session, change_for: Callable[[str], Optional[float]] = _quant_change,
                now: Optional[datetime] = None) -> int:
    now = now or _now()
    followed = watchers(db)
    coins = sorted(followed, key=lambda c: -len(followed[c]))[:MAX_COINS]
    notified = 0
    for coin in coins:
        change = change_for(coin)
        if change is None:
            continue
        new = direction(change)
        state = db.get(CoinSignalState, coin)
        if state is None:
            db.add(CoinSignalState(coin=coin, direction=new, last_trend=new if new != "flat" else None,
                                   change_pct=change, updated_at=now))
            continue
        if now - state.updated_at > STALE_AFTER:      # nobody followed it for a while: start over, no alert
            state.last_trend = new if new != "flat" else None
            state.flipped_at = None
        # last_trend = the view users were last told about (or the first one seen); a reversal inside the
        # cooldown is not remembered, so it is announced later if it lasts.
        flipped = (new != "flat" and state.last_trend not in (None, new)
                   and (state.flipped_at is None or now - state.flipped_at >= COOLDOWN))
        state.direction, state.change_pct, state.updated_at = new, change, now
        if state.last_trend is None and new != "flat":
            state.last_trend = new
        if flipped:
            state.last_trend, state.flipped_at = new, now
            for user_id in followed[coin]:
                user = db.get(User, user_id)
                if user is not None and push.prefs(user)["flips"]:
                    notify(db, user_id, "direction_flip", coin=coin, direction=new, change_pct=round(change, 2))
                    notified += 1
    db.commit()
    return notified


def send_event_reminders(db: Session, now: Optional[datetime] = None) -> int:
    now = now or _now()
    due = (db.query(EventReminder)
           .filter(EventReminder.sent_at.is_(None), EventReminder.event_at <= now + REMIND_BEFORE,
                   EventReminder.event_at >= now - timedelta(hours=1)).all())
    for row in due:
        notify(db, row.user_id, "event_reminder", event_id=row.event_id, title_key=row.title_key,
               coin=row.coin or "", at=row.event_at.isoformat() + "Z")
        row.sent_at = now
    # Reminders for events long gone are dropped.
    db.query(EventReminder).filter(EventReminder.event_at < now - timedelta(days=2)).delete()
    db.commit()
    return len(due)
