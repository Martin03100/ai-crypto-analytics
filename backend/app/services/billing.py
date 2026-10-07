"""Premium subscriptions through Stripe Checkout (REST API, no SDK)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from app.models import User
from app.services.notifications import notify
from app.services.premium import set_premium_until

logger = logging.getLogger("aca.billing")

STRIPE_API = "https://api.stripe.com/v1"
SIGNATURE_TOLERANCE_SECONDS = 300


class BillingError(Exception):
    pass


def billing_enabled() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID and STRIPE_WEBHOOK_SECRET)


def _post(path: str, data: dict) -> dict:
    try:
        res = requests.post(f"{STRIPE_API}{path}", data=data, auth=(STRIPE_SECRET_KEY, ""), timeout=15)
    except requests.RequestException as exc:
        raise BillingError(str(exc)) from exc
    if res.status_code >= 400:
        logger.warning("Stripe %s zlyhal: %s %s", path, res.status_code, res.text[:300])
        raise BillingError(f"Stripe {res.status_code}")
    return res.json()


def create_checkout_url(user: User) -> str:
    data = {
        "mode": "subscription",
        "line_items[0][price]": STRIPE_PRICE_ID,
        "line_items[0][quantity]": "1",
        "success_url": f"{APP_PUBLIC_URL}/premium?status=success",
        "cancel_url": f"{APP_PUBLIC_URL}/premium?status=cancel",
        "client_reference_id": str(user.id),
        "allow_promotion_codes": "true",
        "subscription_data[metadata][user_id]": str(user.id),
    }
    if user.stripe_customer_id:
        data["customer"] = user.stripe_customer_id
    elif user.email:
        data["customer_email"] = user.email
    return _post("/checkout/sessions", data)["url"]


def create_portal_url(user: User) -> str:
    if not user.stripe_customer_id:
        raise BillingError("no customer")
    return _post("/billing_portal/sessions", {"customer": user.stripe_customer_id,
                                              "return_url": f"{APP_PUBLIC_URL}/settings"})["url"]


def verify_signature(payload: bytes, header: Optional[str], secret: str = "", now: Optional[float] = None) -> bool:
    secret = secret or STRIPE_WEBHOOK_SECRET
    if not header or not secret:
        return False
    parts = [p.split("=", 1) for p in header.split(",") if "=" in p]
    timestamps = [v for k, v in parts if k == "t"]
    signatures = [v for k, v in parts if k == "v1"]
    if not timestamps or not signatures or not timestamps[0].isdigit():
        return False
    if abs((now or time.time()) - int(timestamps[0])) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), timestamps[0].encode() + b"." + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in signatures)


def _ts(value) -> Optional[datetime]:
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if isinstance(value, (int, float)) else None


def _metadata_user_id(obj: dict) -> str:
    """Our user id travels in the subscription metadata; Stripe copies it to invoices in two API shapes."""
    for meta in (obj.get("metadata"), (obj.get("subscription_details") or {}).get("metadata"),
                 ((obj.get("parent") or {}).get("subscription_details") or {}).get("metadata")):
        if isinstance(meta, dict) and str(meta.get("user_id", "")).isdigit():
            return str(meta["user_id"])
    return ""


def _user_for(db: Session, obj: dict) -> Optional[User]:
    customer = obj.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer).first() if customer else None
    if user is None and (uid := _metadata_user_id(obj)):
        user = db.get(User, int(uid))
        if user is not None and customer and not user.stripe_customer_id:
            user.stripe_customer_id = customer
    return user


def handle_event(db: Session, event: dict) -> None:
    kind = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    if kind == "checkout.session.completed":
        ref = str(obj.get("client_reference_id") or "")
        user = db.get(User, int(ref)) if ref.isdigit() else None
        if user is not None and obj.get("customer"):
            user.stripe_customer_id = obj["customer"]
            notify(db, user.id, "premium_started")
    elif kind == "invoice.paid":
        user = _user_for(db, obj)
        ends = [_ts((line.get("period") or {}).get("end")) for line in (obj.get("lines") or {}).get("data", [])]
        ends = [e for e in ends if e]
        if user is not None and ends:
            set_premium_until(user, max(ends))
    elif kind in ("customer.subscription.created", "customer.subscription.updated"):
        user = _user_for(db, obj)
        items = (obj.get("items") or {}).get("data") or [{}]
        end = _ts(obj.get("current_period_end") or items[0].get("current_period_end"))
        if user is not None and end and obj.get("status") in ("active", "trialing"):
            set_premium_until(user, end)
    db.commit()
