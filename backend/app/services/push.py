"""Web Push: browser notifications for alerts, "AI changed its mind", results and calendar reminders.

The VAPID key pair is created on first use and kept in the database (private key encrypted), so the
feature needs no configuration. Notifications are queued on the database session by `notify()` and
sent only after that session commits, from a small worker pool, so a slow push service never delays
a request and nothing is sent for a rolled-back change."""

from __future__ import annotations

import base64
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL
from app.database import SessionLocal
from app.models import AppSetting, PushSubscription, User
from app.security import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

CATEGORIES = ("alerts", "flips", "results", "events")
KIND_CATEGORY = {"price_alert": "alerts", "direction_flip": "flips", "forecast_evaluated": "results",
                 "duel_settled": "results", "challenge_won": "results", "event_reminder": "events"}
KEY_ROW = "vapid_keys"
MAX_SUBSCRIPTIONS = 10          # per user (phones, laptops, browsers)
_lock = threading.Lock()
_keys: Optional[Dict[str, str]] = None
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="push")
_QUEUE = "aca_push_queue"
INLINE = False                  # tests deliver synchronously


# ---------- preferences ----------

def prefs(user: User) -> Dict[str, bool]:
    try:
        stored = json.loads(user.notify_prefs_json) if user.notify_prefs_json else {}
    except (json.JSONDecodeError, TypeError):
        stored = {}
    return {c: bool(stored.get(c, True)) for c in CATEGORIES}


def set_prefs(user: User, changes: Dict[str, bool]) -> Dict[str, bool]:
    current = prefs(user)
    current.update({k: bool(v) for k, v in changes.items() if k in CATEGORIES})
    user.notify_prefs_json = json.dumps(current)
    return current


# ---------- keys ----------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _new_keys() -> Dict[str, str]:
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode("ascii")
    public = private.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint)
    return {"public": _b64(public), "private_pem": pem}


def keys() -> Dict[str, str]:
    """{"public": base64url application server key, "private_pem": PEM}; created once and stored encrypted."""
    global _keys
    with _lock:
        if _keys:
            return _keys
        db = SessionLocal()
        try:
            row = db.get(AppSetting, KEY_ROW)
            if row is not None:
                stored = json.loads(row.value_json)
                pem = decrypt_secret(stored.get("private", ""))
                if pem:
                    _keys = {"public": stored["public"], "private_pem": pem}
                    return _keys
            if row is not None:
                logger.error("Web Push keys could not be decrypted (secret changed?); new keys are created and "
                             "browsers have to turn notifications on again")
            fresh = _new_keys()
            value = json.dumps({"public": fresh["public"], "private": encrypt_secret(fresh["private_pem"])})
            if row is None:
                db.add(AppSetting(key=KEY_ROW, value_json=value))
            else:
                row.value_json = value
            db.commit()
            _keys = fresh
            return _keys
        finally:
            db.close()


def public_key() -> str:
    return keys()["public"]


# ---------- texts ----------

TEXTS: Dict[str, Dict[str, str]] = {
    "en": {"price_alert": "{coin}: your alert fired", "direction_flip_up": "The AI turned bullish on {coin}",
           "direction_flip_down": "The AI turned bearish on {coin}", "forecast_evaluated": "Your {coin} forecast was evaluated",
           "duel_settled": "Your duel with the AI is settled", "challenge_won": "You won the weekly challenge on {coin}!",
           "event_reminder": "Starting within an hour: {event}", "open": "Open the app to see the details."},
    "sk": {"price_alert": "{coin}: tvoje upozornenie sa spustilo", "direction_flip_up": "AI zmenila názor: {coin} vidí rast",
           "direction_flip_down": "AI zmenila názor: {coin} vidí pokles", "forecast_evaluated": "Tvoja predikcia {coin} je vyhodnotená",
           "duel_settled": "Tvoj súboj s AI je vyhodnotený", "challenge_won": "Vyhral si týždennú výzvu na {coin}!",
           "event_reminder": "Do hodiny začína: {event}", "open": "Otvor appku a pozri si podrobnosti."},
    "cs": {"price_alert": "{coin}: tvé upozornění se spustilo", "direction_flip_up": "AI změnila názor: {coin} vidí růst",
           "direction_flip_down": "AI změnila názor: {coin} vidí pokles", "forecast_evaluated": "Tvá predikce {coin} je vyhodnocená",
           "duel_settled": "Tvůj souboj s AI je vyhodnocený", "challenge_won": "Vyhrál jsi týdenní výzvu na {coin}!",
           "event_reminder": "Do hodiny začíná: {event}", "open": "Otevři appku a podívej se na podrobnosti."},
    "de": {"price_alert": "{coin}: dein Alarm wurde ausgelöst", "direction_flip_up": "Die KI ist jetzt bullisch für {coin}",
           "direction_flip_down": "Die KI ist jetzt bärisch für {coin}", "forecast_evaluated": "Deine {coin}-Prognose wurde ausgewertet",
           "duel_settled": "Dein Duell mit der KI ist entschieden", "challenge_won": "Du hast die Wochen-Challenge zu {coin} gewonnen!",
           "event_reminder": "Beginnt in weniger als einer Stunde: {event}", "open": "Öffne die App für Details."},
    "pl": {"price_alert": "{coin}: twój alert się uruchomił", "direction_flip_up": "AI zmieniła zdanie: {coin} – wzrost",
           "direction_flip_down": "AI zmieniła zdanie: {coin} – spadek", "forecast_evaluated": "Twoja prognoza {coin} została oceniona",
           "duel_settled": "Twój pojedynek z AI został rozstrzygnięty", "challenge_won": "Wygrałeś cotygodniowe wyzwanie na {coin}!",
           "event_reminder": "Za mniej niż godzinę: {event}", "open": "Otwórz aplikację, aby zobaczyć szczegóły."},
}

EVENT_NAMES: Dict[str, Dict[str, str]] = {
    "en": {"fomc": "Fed rate decision", "cpi": "US inflation (CPI)", "nfp": "US jobs report",
           "options_monthly": "Monthly crypto options expiry", "options_quarterly": "Quarterly crypto options expiry",
           "halving": "Bitcoin halving", "unlock": "{coin} token unlock"},
    "sk": {"fomc": "Rozhodnutie Fedu o sadzbách", "cpi": "Inflácia v USA (CPI)", "nfp": "Trh práce v USA",
           "options_monthly": "Mesačná expirácia krypto opcií", "options_quarterly": "Štvrťročná expirácia krypto opcií",
           "halving": "Halving Bitcoinu", "unlock": "Odomknutie tokenov {coin}"},
    "cs": {"fomc": "Rozhodnutí Fedu o sazbách", "cpi": "Inflace v USA (CPI)", "nfp": "Trh práce v USA",
           "options_monthly": "Měsíční expirace krypto opcí", "options_quarterly": "Čtvrtletní expirace krypto opcí",
           "halving": "Halving Bitcoinu", "unlock": "Odemčení tokenů {coin}"},
    "de": {"fomc": "Zinsentscheid der Fed", "cpi": "US-Inflation (CPI)", "nfp": "US-Arbeitsmarktbericht",
           "options_monthly": "Monatlicher Krypto-Optionsverfall", "options_quarterly": "Quartalsweiser Krypto-Optionsverfall",
           "halving": "Bitcoin-Halving", "unlock": "Token-Unlock {coin}"},
    "pl": {"fomc": "Decyzja Fed ws. stóp", "cpi": "Inflacja w USA (CPI)", "nfp": "Raport z rynku pracy USA",
           "options_monthly": "Miesięczne wygaśnięcie opcji krypto", "options_quarterly": "Kwartalne wygaśnięcie opcji krypto",
           "halving": "Halving Bitcoina", "unlock": "Odblokowanie tokenów {coin}"},
}


def message(kind: str, data: Dict[str, Any], lang: str) -> Optional[Dict[str, str]]:
    texts = TEXTS.get(lang) or TEXTS["en"]
    coin = str(data.get("coin") or "")
    if kind == "direction_flip":
        key = "direction_flip_up" if data.get("direction") == "up" else "direction_flip_down"
    elif kind in texts:
        key = kind
    else:
        return None
    event_name = ""
    if kind == "event_reminder":
        names = EVENT_NAMES.get(lang) or EVENT_NAMES["en"]
        event_name = names.get(str(data.get("title_key")), "").format(coin=coin)
    url = {"price_alert": "/dashboard", "direction_flip": f"/forecast?coin={coin}" if coin else "/forecast",
           "event_reminder": "/calendar", "challenge_won": "/dashboard"}.get(kind, "/dashboard")
    return {"title": texts[key].format(coin=coin, event=event_name), "body": texts["open"], "url": url,
            "tag": f"{kind}:{coin}"}


# ---------- queue and delivery ----------

def queue(db: Session, user_id: int, kind: str, data: Dict[str, Any]) -> None:
    if kind in KIND_CATEGORY:
        db.info.setdefault(_QUEUE, []).append((user_id, kind, dict(data)))


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    pending = session.info.pop(_QUEUE, None)
    if pending:
        if INLINE:
            deliver_all(pending)
        else:
            _pool.submit(deliver_all, pending)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_QUEUE, None)


def deliver_all(pending: List[tuple]) -> int:
    sent = 0
    db = SessionLocal()
    try:
        for user_id, kind, data in pending:
            sent += deliver(db, user_id, kind, data)
        db.commit()
    except Exception:  # noqa: BLE001 - a failed push must never break anything else
        logger.exception("Web push delivery failed")
        db.rollback()
    finally:
        db.close()
    return sent


def deliver(db: Session, user_id: int, kind: str, data: Dict[str, Any]) -> int:
    user = db.get(User, user_id)
    if user is None or user.disabled or not prefs(user).get(KIND_CATEGORY.get(kind, ""), False):
        return 0
    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    if not subs:
        return 0
    payload = message(kind, data, user.lang or "en")
    if payload is None:
        return 0
    sent = 0
    for sub in subs:
        status = send(sub, payload)
        if status in (404, 410):            # the browser dropped the subscription
            db.delete(sub)
        elif status in (401, 403):          # signed with keys the push service no longer accepts
            logger.warning("Web Push rejected (%s) for subscription %s", status, sub.id)
        elif status and status < 300:
            sub.last_ok_at = datetime.now(timezone.utc).replace(tzinfo=None)
            sent += 1
    return sent


def send(sub: PushSubscription, payload: Dict[str, str]) -> Optional[int]:
    """Returns the push service's HTTP status (None when it could not be reached)."""
    from py_vapid import Vapid
    from pywebpush import WebPushException, webpush

    try:
        vapid = Vapid.from_pem(keys()["private_pem"].encode("ascii"))
        res = webpush({"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                      json.dumps(payload, ensure_ascii=False), vapid_private_key=vapid,
                      vapid_claims={"sub": APP_PUBLIC_URL}, ttl=6 * 3600, timeout=10)
        return getattr(res, "status_code", 201)
    except WebPushException as exc:
        return getattr(exc.response, "status_code", None)
    except Exception:  # noqa: BLE001
        logger.warning("Web push to %s failed", sub.endpoint[:40], exc_info=True)
        return None
