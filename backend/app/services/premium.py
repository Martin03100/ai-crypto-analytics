"""Premium membership, invite rewards and ambassador badges."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import MAX_REWARDED_REFERRALS
from app.models import User
from app.services import app_settings
from app.services.notifications import notify

FREE_SCHEDULES = 5          # defaults; the admin can change both in the admin panel
PREMIUM_SCHEDULES = 20
BADGES = ((10, "gold"), (5, "silver"), (1, "bronze"))
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_premium(user: User) -> bool:
    """Premium counts only while the admin has Premium switched on."""
    return bool(user and user.premium_until and user.premium_until > _now() and app_settings.premium_mode())


def require_premium(user: User) -> None:
    """403 for Premium-only features: "switched off" while Premium mode is off, otherwise "part of Premium"."""
    from fastapi import HTTPException

    if not app_settings.premium_mode():
        raise HTTPException(status_code=403, detail="Táto funkcia je momentálne vypnutá.")
    if not is_premium(user):
        raise HTTPException(status_code=403, detail="Táto funkcia je dostupná v Premium.")


def extend_premium(user: User, days: int) -> None:
    start = max(user.premium_until or _now(), _now())
    user.premium_until = start + timedelta(days=days)


def set_premium_until(user: User, until: Optional[datetime]) -> None:
    """Paid period from Stripe; never shortens time earned through invites."""
    if until is not None:
        until = until.astimezone(timezone.utc).replace(tzinfo=None) if until.tzinfo else until
        if user.premium_until is None or until > user.premium_until:
            user.premium_until = until


def max_schedules(user: User) -> int:
    return app_settings.get("premium_schedules" if is_premium(user) else "free_schedules")


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


def invited_signups(db: Session, referrer_id: int) -> int:
    """Friends who signed up with the invite link and confirmed their email."""
    return db.query(User).filter(User.referred_by_id == referrer_id, User.email_verified.isnot(False),
                                 User.disabled.isnot(True)).count()


def rewarded_referrals(db: Session, referrer_id: int) -> int:
    return db.query(User).filter(User.referred_by_id == referrer_id, User.referral_rewarded.is_(True)).count()


def ambassador_badge(signups: int) -> Optional[str]:
    return next((name for minimum, name in BADGES if signups >= minimum), None)


def trial_days_for(user: User) -> int:
    """Invited friends get a longer free trial; one trial per Stripe customer."""
    if user.stripe_customer_id:
        return 0
    key = "referral_trial_days" if user.referred_by_id and app_settings.get("referrals_enabled") else "premium_trial_days"
    return app_settings.get(key)


def reward_referrer_for_purchase(db: Session, buyer: User) -> bool:
    """The inviter gets free Premium when the invited friend makes their first payment. The caller commits."""
    if not buyer.referred_by_id or buyer.referral_rewarded or not app_settings.get("referrals_enabled"):
        return False
    referrer = db.get(User, buyer.referred_by_id)
    eligible = (referrer is not None and not referrer.disabled
                and rewarded_referrals(db, referrer.id) < MAX_REWARDED_REFERRALS)
    buyer.referral_rewarded = True
    if not eligible:
        return False
    days = app_settings.get("referral_reward_days")
    extend_premium(referrer, days)
    notify(db, referrer.id, "referral_reward", days=days)
    return True
