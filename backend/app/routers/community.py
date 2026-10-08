"""Membership, notifications, nickname, weekly digest and billing for the signed-in user."""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL, MAX_REWARDED_REFERRALS, RATE_LIMIT_ACCOUNT_SENSITIVE
from app.deps import get_current_user, get_db
from app.models import StripeEvent, User
from app.rate_limit import rate_limit_by_user
from app.services import app_settings, audit, billing, challenge, notifications, telegram
from app.services.account_data import export_user_data, personal_stats
from app.services.premium import (
    ambassador_badge, ensure_referral_code, invited_signups, is_premium, require_premium, rewarded_referrals,
)

logger = logging.getLogger("aca.community")
router = APIRouter(tags=["community"])

NICKNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,20}$")


def premium_info() -> dict:
    s = app_settings.all_settings()
    if not s["premium_mode"]:
        return {"enabled": False}
    return {"enabled": True, "billing_enabled": billing.checkout_ready(), "yearly": billing.yearly_available(),
            "price_label": s["premium_price_label"], "price_label_yearly": s["premium_price_label_yearly"],
            "trial_days": s["premium_trial_days"], "referral_trial_days": s["referral_trial_days"],
            "limits": {"free": {"schedules": s["free_schedules"], "alerts": s["free_alerts"]},
                       "premium": {"schedules": s["premium_schedules"], "alerts": s["premium_alerts"]}},
            "referral_days": s["referral_reward_days"], "referrals_enabled": s["referrals_enabled"]}


def _require_premium_mode() -> None:
    if not app_settings.premium_mode():
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/account/membership")
def membership(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    code = ensure_referral_code(db, user)
    premium = is_premium(user)
    signups = invited_signups(db, user.id)
    return {
        "premium": premium, "premium_until": user.premium_until.isoformat() + "Z" if premium else None,
        "has_billing": bool(user.stripe_customer_id),
        "nickname": user.nickname, "digest_opt_in": bool(user.digest_opt_in), "lang": user.lang or "en",
        "briefing_opt_in": bool(user.briefing_opt_in) and premium,
        "telegram": {"available": telegram.enabled(), "linked": bool(user.telegram_chat_id)},
        "referral_code": code, "referral_link": f"{APP_PUBLIC_URL}/?ref={code}",
        "referral_signups": signups, "badge": ambassador_badge(signups), "challenge_wins": challenge.wins(db, user.id),
        **({"referrals_rewarded": rewarded_referrals(db, user.id), "referrals_max": MAX_REWARDED_REFERRALS}
           if app_settings.premium_mode() else {}),
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
    briefing_opt_in: bool | None = None
    lang: str | None = Field(default=None, pattern=r"^(en|sk|cs|de|pl)$")


@router.put("/api/account/preferences")
def set_preferences(payload: PreferencesIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if payload.digest_opt_in is not None:
        user.digest_opt_in = payload.digest_opt_in
    if payload.lang is not None:
        user.lang = payload.lang
    if payload.briefing_opt_in is not None:
        if payload.briefing_opt_in:
            require_premium(user)
        user.briefing_opt_in = payload.briefing_opt_in
    db.commit()
    return {"digest_opt_in": bool(user.digest_opt_in), "lang": user.lang or "en",
            "briefing_opt_in": bool(user.briefing_opt_in)}


@router.get("/api/account/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    items, unread = notifications.latest(db, user.id)
    return {"items": items, "unread": unread}


@router.post("/api/account/notifications/read")
def read_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    notifications.mark_all_read(db, user.id)
    return {"success": True}


def _billing_ready() -> None:
    if not billing.checkout_ready():
        raise HTTPException(status_code=503, detail="Platby za Premium zatiaľ nie sú spustené.")


class CheckoutIn(BaseModel):
    plan: Literal["monthly", "yearly"] = "monthly"
    # The buyer accepts the Terms and asks for Premium to start right away (EU consumer law, services).
    accept_terms: bool = False
    start_immediately: bool = False


@router.post("/api/billing/checkout", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def checkout(payload: CheckoutIn, request: Request, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)) -> dict:
    _billing_ready()
    if not (payload.accept_terms and payload.start_immediately):
        raise HTTPException(status_code=400, detail="Pred platbou potvrď podmienky a okamžité spustenie služby.")
    audit.record(db, user.id, "premium_checkout_consent", request)
    db.commit()
    try:
        return {"url": billing.create_checkout_url(user, payload.plan)}
    except billing.BillingError:
        raise HTTPException(status_code=502, detail="Platobnú bránu sa nepodarilo otvoriť. Skús to o chvíľu.") from None


@router.get("/api/account/stats")
def my_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Premium: the user's own accuracy by model, coin and horizon."""
    require_premium(user)
    return personal_stats(db, user.id)


@router.post("/api/account/telegram/link", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def telegram_link(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_premium(user)
    if not telegram.enabled():
        raise HTTPException(status_code=403, detail="Táto funkcia je momentálne vypnutá.")
    return {"url": telegram.link_url(db, user)}


@router.delete("/api/account/telegram")
def telegram_unlink(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    user.telegram_chat_id, user.telegram_link_code = None, None
    db.commit()
    return {"success": True}


@router.get("/api/account/export")
def export_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """GDPR access and portability: everything stored about the account, as one JSON file."""
    body = json.dumps(export_user_data(db, user), ensure_ascii=False, indent=2, default=str)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="ai-crypto-analytics-data.json"'})


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
    event_id = str(event.get("id") or "")[:255] if isinstance(event, dict) else ""
    if event_id:
        if db.get(StripeEvent, event_id) is not None:
            return {"received": True, "duplicate": True}
        db.add(StripeEvent(id=event_id))
    billing.handle_event(db, event)
    return {"received": True}


@router.get("/api/challenge")
def my_challenge(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return challenge.summary(db, user)


class ChallengeEntryIn(BaseModel):
    price: float = Field(gt=0, lt=1e9)


@router.post("/api/challenge/entry", status_code=201, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def enter_challenge(payload: ChallengeEntryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    try:
        challenge.enter(db, user, payload.price)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return challenge.summary(db, user)
