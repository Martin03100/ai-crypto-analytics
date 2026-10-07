"""Premium membership and referral rewards."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import MAX_REWARDED_REFERRALS, REFERRAL_REWARD_DAYS
from app.models import User
from app.services.notifications import notify

FREE_SCHEDULES = 5
PREMIUM_SCHEDULES = 20
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_premium(user: User) -> bool:
    return bool(user.premium_until and user.premium_until > _now())


def extend_premium(user: User, days: int) -> None:
    start = max(user.premium_until or _now(), _now())
    user.premium_until = start + timedelta(days=days)


def set_premium_until(user: User, until: Optional[datetime]) -> None:
    """Paid period from Stripe; never shortens time earned through referrals."""
    if until is not None:
        until = until.astimezone(timezone.utc).replace(tzinfo=None) if until.tzinfo else until
        if user.premium_until is None or until > user.premium_until:
            user.premium_until = until


def max_schedules(user: User) -> int:
    return PREMIUM_SCHEDULES if is_premium(user) else FREE_SCHEDULES


def ensure_referral_code(db: Session, user: User) -> str:
    if not user.referral_code:
        for _ in range(10):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
            if not db.query(User.id).filter(User.referral_code == code).first():
                user.referral_code = code
                db.commit()
                break
    return user.referral_code or ""


def find_referrer(db: Session, code: Optional[str]) -> Optional[User]:
    code = (code or "").strip().upper()
    if not code or len(code) > 16:
        return None
    return db.query(User).filter(User.referral_code == code).first()


def rewarded_referrals(db: Session, referrer_id: int) -> int:
    return db.query(User).filter(User.referred_by_id == referrer_id, User.referral_rewarded.is_(True)).count()


def grant_referral_reward(db: Session, user: User) -> bool:
    """Both people get Premium days once the invited user has a confirmed account; the caller commits."""
    if not user.referred_by_id or user.referral_rewarded:
        return False
    referrer = db.get(User, user.referred_by_id)
    referrer_eligible = referrer is not None and rewarded_referrals(db, referrer.id) < MAX_REWARDED_REFERRALS
    user.referral_rewarded = True
    extend_premium(user, REFERRAL_REWARD_DAYS)
    notify(db, user.id, "referral_reward", days=REFERRAL_REWARD_DAYS)
    if referrer_eligible:
        extend_premium(referrer, REFERRAL_REWARD_DAYS)
        notify(db, referrer.id, "referral_reward", days=REFERRAL_REWARD_DAYS)
    return True
