"""Stripe set up from the admin panel: one secret key in, the product, prices, webhook and customer portal are created.

The key and the webhook secret are stored encrypted. Environment variables, when set, still take precedence."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Optional

import requests
from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL
from app.database import SessionLocal
from app.models import AppSetting
from app.security import decrypt_secret, encrypt_secret

logger = logging.getLogger("aca.stripe")

STRIPE_API = "https://api.stripe.com/v1"
_KEY = "stripe_credentials"
WEBHOOK_EVENTS = ("checkout.session.completed", "invoice.paid", "customer.subscription.created",
                  "customer.subscription.updated")
CURRENCIES = {"eur": ("€{amount}", 2), "czk": ("{amount} Kč", 2), "usd": ("${amount}", 2)}

_cache: dict[str, Any] = {}
_cache_at = 0.0
_lock = threading.Lock()


class StripeSetupError(Exception):
    """Message is shown to the admin (Slovak, mapped to the UI language on the frontend)."""


def webhook_url() -> str:
    base = os.environ.get("BACKEND_PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or APP_PUBLIC_URL
    return f"{base.rstrip('/')}/api/billing/webhook"


def stored() -> dict[str, Any]:
    """Decrypted credentials saved from the admin panel ({} when none)."""
    global _cache, _cache_at
    with _lock:
        if _cache_at and time.monotonic() - _cache_at < 30:
            return dict(_cache)
    db = SessionLocal()
    try:
        row = db.get(AppSetting, _KEY)
        data = json.loads(decrypt_secret(row.value_json) or "{}") if row else {}
    except (json.JSONDecodeError, TypeError):
        data = {}
    finally:
        db.close()
    with _lock:
        _cache, _cache_at = data, time.monotonic()
    return dict(data)


def _save(db: Session, data: dict[str, Any]) -> None:
    global _cache_at
    row = db.get(AppSetting, _KEY)
    if not data:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(AppSetting(key=_KEY, value_json=encrypt_secret(json.dumps(data))))
    else:
        row.value_json = encrypt_secret(json.dumps(data))
    db.commit()
    with _lock:
        _cache_at = 0.0


def _call(method: str, path: str, key: str, data: Optional[dict] = None) -> dict:
    try:
        res = requests.request(method, f"{STRIPE_API}{path}", data=data, auth=(key, ""), timeout=20)
    except requests.RequestException as exc:
        raise StripeSetupError("Stripe sa nepodarilo kontaktovať. Skús to znova.") from exc
    if res.status_code == 401:
        raise StripeSetupError("Stripe kľúč je neplatný.")
    if res.status_code >= 400:
        logger.warning("Stripe %s %s zlyhal: %s", method, path, res.status_code)
        message = ((res.json() if res.headers.get("content-type", "").startswith("application/json") else {})
                   .get("error", {}).get("message", ""))
        raise StripeSetupError(f"Stripe odmietol požiadavku: {message[:160]}" if message else "Stripe odmietol požiadavku.")
    return res.json()


def price_label(amount_cents: int, currency: str, period: str) -> str:
    template, decimals = CURRENCIES[currency]
    value = amount_cents / 10 ** decimals
    amount = f"{value:.0f}" if value == int(value) else f"{value:.2f}"
    return f"{template.format(amount=amount)} / {'month' if period == 'month' else 'year'}"


def account_status(key: str) -> dict[str, Any]:
    acct = _call("GET", "/account", key)
    return {"mode": "live" if key.startswith(("sk_live_", "rk_live_")) else "test",
            "charges_enabled": bool(acct.get("charges_enabled")), "payouts_enabled": bool(acct.get("payouts_enabled")),
            "details_submitted": bool(acct.get("details_submitted")), "country": acct.get("country"),
            "email": acct.get("email")}


def connect(db: Session, secret_key: Optional[str], monthly_cents: int, yearly_cents: Optional[int], currency: str) -> dict:
    """Creates (or re-creates) everything Stripe needs and stores it. A missing key reuses the saved one."""
    current = stored()
    key = (secret_key or "").strip() or current.get("secret_key", "")
    if not key.startswith(("sk_live_", "sk_test_", "rk_live_", "rk_test_")):
        raise StripeSetupError("Vlož tajný kľúč zo Stripe (začína sk_live_ alebo sk_test_).")
    if currency not in CURRENCIES:
        raise StripeSetupError("Nepodporovaná mena.")
    status = account_status(key)
    same_account = key == current.get("secret_key")

    product_id = current.get("product_id") if same_account else None
    if not product_id:
        product_id = _call("POST", "/products", key, {"name": "AI Crypto Analytics Premium",
                                                      "description": "Premium tools for AI Crypto Analytics"})["id"]

    def price(amount: int, interval: str) -> str:
        return _call("POST", "/prices", key, {"product": product_id, "currency": currency, "unit_amount": str(amount),
                                              "recurring[interval]": interval})["id"]

    monthly = price(monthly_cents, "month")
    yearly = price(yearly_cents, "year") if yearly_cents else ""

    url = webhook_url()
    for hook in _call("GET", "/webhook_endpoints?limit=100", key).get("data", []):
        if hook.get("url") == url:
            _call("DELETE", f"/webhook_endpoints/{hook['id']}", key)
    hook_data = {"url": url, "description": "AI Crypto Analytics"}
    for i, event in enumerate(WEBHOOK_EVENTS):
        hook_data[f"enabled_events[{i}]"] = event
    webhook = _call("POST", "/webhook_endpoints", key, hook_data)

    portal = current.get("portal_id") if same_account else None
    if not portal:
        portal = _call("POST", "/billing_portal/configurations", key, {
            "business_profile[headline]": "AI Crypto Analytics Premium",
            "features[subscription_cancel][enabled]": "true",
            "features[subscription_cancel][mode]": "at_period_end",
            "features[payment_method_update][enabled]": "true",
            "features[invoice_history][enabled]": "true",
        })["id"]

    _save(db, {"secret_key": key, "price_monthly": monthly, "price_yearly": yearly, "webhook_secret": webhook["secret"],
               "product_id": product_id, "portal_id": portal, "currency": currency,
               "monthly_cents": monthly_cents, "yearly_cents": yearly_cents or 0})
    from app.services import app_settings
    labels = {"premium_price_label": price_label(monthly_cents, currency, "month")}
    if yearly_cents:
        labels["premium_price_label_yearly"] = price_label(yearly_cents, currency, "year")
    app_settings.update(db, labels)
    return status


def disconnect(db: Session) -> None:
    current = stored()
    if current.get("secret_key"):
        try:
            for hook in _call("GET", "/webhook_endpoints?limit=100", current["secret_key"]).get("data", []):
                if hook.get("url") == webhook_url():
                    _call("DELETE", f"/webhook_endpoints/{hook['id']}", current["secret_key"])
        except StripeSetupError:
            pass                            # the key may already be revoked; forget it anyway
    _save(db, {})


def key_hint(key: str) -> str:
    return f"{key[:8]}…{key[-4:]}" if len(key) > 16 else "…"
