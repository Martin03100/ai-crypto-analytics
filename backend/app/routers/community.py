"""Membership, notifications, nickname, weekly digest and billing for the signed-in user."""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL, MAX_REWARDED_REFERRALS, PREMIUM_PRICE_LABEL, RATE_LIMIT_ACCOUNT_SENSITIVE, REFERRAL_REWARD_DAYS
from app.deps import get_current_user, get_db
from app.models import User
from app.rate_limit import rate_limit_by_user
from app.services import billing, notifications
from app.services.premium import (
    FREE_SCHEDULES, PREMIUM_SCHEDULES, ensure_referral_code, is_premium, rewarded_referrals,
)

logger = logging.getLogger("aca.community")
router = APIRouter(tags=["community"])

NICKNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,20}$")


def premium_info() -> dict:
    return {"billing_enabled": billing.billing_enabled(), "price_label": PREMIUM_PRICE_LABEL,
            "limits": {"free": {"schedules": FREE_SCHEDULES}, "premium": {"schedules": PREMIUM_SCHEDULES}},
            "referral_days": REFERRAL_REWARD_DAYS}


@router.get("/api/account/membership")
def membership(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    code = ensure_referral_code(db, user)
    until = user.premium_until.isoformat() + "Z" if user.premium_until else None
    return {
        "premium": is_premium(user), "premium_until": until, "has_billing": bool(user.stripe_customer_id),
        "nickname": user.nickname, "digest_opt_in": bool(user.digest_opt_in), "lang": user.lang or "en",
        "referral_code": code, "referral_link": f"{APP_PUBLIC_URL}/?ref={code}",
        "referrals_rewarded": rewarded_referrals(db, user.id), "referrals_max": MAX_REWARDED_REFERRALS,
        **premium_info(),
    }


class NicknameIn(BaseModel):
    nickname: str = Field(default="", max_length=20)


@router.put("/api/account/nickname", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def set_nickname(payload: NicknameIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    nickname = payload.nickname.strip()
    if not nickname:
        user.nickname = None
    else:
        if not NICKNAME_RE.match(nickname):
            raise HTTPException(status_code=400, detail="Prezývka musí mať 3–20 znakov: písmená bez diakritiky, čísla, bodku, pomlčku alebo podčiarkovník.")
        taken = db.query(User.id).filter(func.lower(User.nickname) == nickname.lower(), User.id != user.id).first()
        if taken:
            raise HTTPException(status_code=400, detail="Táto prezývka je už obsadená.")
        user.nickname = nickname
    db.commit()
    return {"nickname": user.nickname}


class PreferencesIn(BaseModel):
    digest_opt_in: bool | None = None
    lang: str | None = Field(default=None, pattern=r"^(en|sk|cs)$")


@router.put("/api/account/preferences")
def set_preferences(payload: PreferencesIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if payload.digest_opt_in is not None:
        user.digest_opt_in = payload.digest_opt_in
    if payload.lang is not None:
        user.lang = payload.lang
    db.commit()
    return {"digest_opt_in": bool(user.digest_opt_in), "lang": user.lang or "en"}


@router.get("/api/account/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    items, unread = notifications.latest(db, user.id)
    return {"items": items, "unread": unread}


@router.post("/api/account/notifications/read")
def read_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    notifications.mark_all_read(db, user.id)
    return {"success": True}


def _billing_ready() -> None:
    if not billing.billing_enabled():
        raise HTTPException(status_code=503, detail="Platby za Premium zatiaľ nie sú spustené.")


@router.post("/api/billing/checkout", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def checkout(user: User = Depends(get_current_user)) -> dict:
    _billing_ready()
    try:
        return {"url": billing.create_checkout_url(user)}
    except billing.BillingError:
        raise HTTPException(status_code=502, detail="Platobnú bránu sa nepodarilo otvoriť. Skús to o chvíľu.") from None


@router.post("/api/billing/portal", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def portal(user: User = Depends(get_current_user)) -> dict:
    _billing_ready()
    try:
        return {"url": billing.create_portal_url(user)}
    except billing.BillingError:
        raise HTTPException(status_code=502, detail="Platobnú bránu sa nepodarilo otvoriť. Skús to o chvíľu.") from None


@router.post("/api/billing/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    if not billing.billing_enabled() or not billing.verify_signature(payload, request.headers.get("stripe-signature")):
        raise HTTPException(status_code=400, detail="Invalid signature.")
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload.") from None
    billing.handle_event(db, event)
    return {"received": True}
