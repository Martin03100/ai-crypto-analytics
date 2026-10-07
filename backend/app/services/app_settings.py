"""Settings the admin changes from the web (feature switches, limits, prices, announcement).

Stripe credentials are stored separately and encrypted (see stripe_connect)."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from sqlalchemy.orm import Session

from app.config import PREMIUM_PRICE_LABEL, REFERRAL_REWARD_DAYS
from app.database import SessionLocal
from app.models import AppSetting

# key -> (default, kind, limits)
SCHEMA: dict[str, tuple[Any, str, tuple]] = {
    # Master switch: off = no Premium anywhere (pages, prices, seller details), the app looks completely free.
    "premium_mode": (False, "bool", ()),
    "signups_enabled": (True, "bool", ()),
    "chat_enabled": (True, "bool", ()),
    "compare_enabled": (True, "bool", ()),
    "backtest_enabled": (True, "bool", ()),
    "tipsters_enabled": (True, "bool", ()),
    "waitlist_enabled": (True, "bool", ()),
    "digest_enabled": (True, "bool", ()),
    "referrals_enabled": (True, "bool", ()),
    "premium_price_label": (PREMIUM_PRICE_LABEL, "str", (40,)),
    "premium_price_label_yearly": ("€39 / year", "str", (40,)),
    "free_schedules": (5, "int", (0, 50)),
    "premium_schedules": (20, "int", (1, 200)),
    "referral_reward_days": (REFERRAL_REWARD_DAYS, "int", (1, 365)),
    "referral_trial_days": (14, "int", (0, 60)),
    "free_alerts": (1, "int", (0, 50)),
    "premium_alerts": (25, "int", (1, 200)),
    "premium_trial_days": (7, "int", (0, 30)),
    "operator_name": ("", "str", (120,)),
    "operator_business_id": ("", "str", (60,)),
    "operator_address": ("", "str", (200,)),
    "announcement": ("", "str", (280,)),
    "announcement_level": ("info", "choice", ("info", "warn", "success")),
}

PUBLIC_KEYS = ("premium_mode", "signups_enabled", "chat_enabled", "compare_enabled", "backtest_enabled", "tipsters_enabled",
               "waitlist_enabled", "digest_enabled", "referrals_enabled", "announcement", "announcement_level",
               "operator_name", "operator_business_id", "operator_address")

_TTL_SECONDS = 30
_cache: dict[str, Any] = {}
_cache_at = 0.0
_lock = threading.Lock()


class SettingError(ValueError):
    pass


def validate(key: str, value: Any) -> Any:
    if key not in SCHEMA:
        raise SettingError(f"Neznáme nastavenie: {key}")
    _default, kind, limits = SCHEMA[key]
    if kind == "bool" and isinstance(value, bool):
        return value
    if kind == "int" and isinstance(value, int) and not isinstance(value, bool) and limits[0] <= value <= limits[1]:
        return value
    if kind == "str" and isinstance(value, str) and len(value.strip()) <= limits[0]:
        return value.strip()
    if kind == "choice" and value in limits:
        return value
    raise SettingError(f"Neplatná hodnota pre {key}.")


def _load() -> dict[str, Any]:
    values = {k: spec[0] for k, spec in SCHEMA.items()}
    db = SessionLocal()
    try:
        for row in db.query(AppSetting).all():
            if row.key in SCHEMA:
                try:
                    values[row.key] = validate(row.key, json.loads(row.value_json))
                except (json.JSONDecodeError, SettingError):
                    pass
    finally:
        db.close()
    return values


def all_settings() -> dict[str, Any]:
    global _cache, _cache_at
    with _lock:
        if not _cache or time.monotonic() - _cache_at > _TTL_SECONDS:
            _cache, _cache_at = _load(), time.monotonic()
        return dict(_cache)


def get(key: str) -> Any:
    return all_settings()[key]


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = {}


def update(db: Session, changes: dict[str, Any]) -> dict[str, Any]:
    clean = {key: validate(key, value) for key, value in changes.items()}
    for key, value in clean.items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value_json=json.dumps(value)))
        else:
            row.value_json = json.dumps(value)
    db.commit()
    invalidate()
    return all_settings()


def require_feature(key: str) -> None:
    """Raises 403 when the admin has switched the feature off."""
    from fastapi import HTTPException

    if not get(key):
        raise HTTPException(status_code=403, detail="Táto funkcia je momentálne vypnutá.")


def public_settings() -> dict[str, Any]:
    values = all_settings()
    public = {k: values[k] for k in PUBLIC_KEYS}
    if not values["premium_mode"]:   # nothing about selling is shown while Premium is switched off
        for key in ("operator_name", "operator_business_id", "operator_address", "waitlist_enabled"):
            public[key] = "" if key.startswith("operator") else False
    return public


def premium_mode() -> bool:
    return bool(get("premium_mode"))
