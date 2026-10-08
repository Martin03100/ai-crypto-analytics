"""Tipster profiles, accuracy over time, the weekly recap, the event calendar, "what if", CSV export,
browser push notifications, the beginner view and in-app feedback."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, RATE_LIMIT_ACCOUNT_SENSITIVE, RATE_LIMIT_AI_ENDPOINT, RATE_LIMIT_MARKET_PUBLIC
from app.deps import get_admin_user, get_current_user, get_db
from app.models import (Challenge, ChallengeEntry, EventReminder, Feedback, ForecastEvaluation, ForecastHistory, PriceAlert,
                        PriceTip, PushSubscription, User)
from app.rate_limit import check_rate_limit, rate_limit_by_ip, rate_limit_by_user
from app.schemas import MAX_DB_ID
from app.security import sanitize_text
from app.services import cards, event_calendar, profiles, push, whatif
from app.services.app_settings import require_feature

router = APIRouter(tags=["extras"])
PUBLIC = [Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))]
_card_cache: dict = {}


# ---------- public ----------

@router.get("/api/public/tipsters/{nickname}", dependencies=PUBLIC)
def tipster_profile(nickname: str = Path(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9._-]+$"),
                    db: Session = Depends(get_db)) -> dict:
    require_feature("tipsters_enabled")
    profile = profiles.tipster(db, nickname)
    if profile is None:
        raise HTTPException(status_code=404, detail="Tento profil neexistuje.")
    return profile


@router.get("/api/public/accuracy-timeline", dependencies=PUBLIC)
def accuracy_timeline(db: Session = Depends(get_db)) -> dict:
    return profiles.timeline(db)


@router.get("/api/public/weekly-summary", dependencies=PUBLIC)
def weekly_summary(db: Session = Depends(get_db)) -> dict:
    return profiles.weekly_summary(db)


@router.get("/api/public/weekly-summary/card.png", dependencies=PUBLIC)
def weekly_summary_card(fmt: Literal["square", "story"] = Query(default="square"), db: Session = Depends(get_db)) -> Response:
    hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    key = f"{fmt}:{hour}"
    png = _card_cache.get(key)
    if png is None:
        png = cards.weekly_card(fmt, profiles.weekly_summary(db))
        _card_cache.clear()
        _card_cache[key] = png
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=900"})


@router.get("/api/public/calendar", dependencies=PUBLIC)
def market_calendar(days: int = Query(default=60, ge=7, le=120)) -> dict:
    return event_calendar.upcoming(days)


# ---------- calendar reminders ----------

class ReminderIn(BaseModel):
    event_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-z_]+-\d{8}(-[a-z0-9]+)?$")


@router.get("/api/calendar/reminders")
def my_reminders(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.query(EventReminder.event_id).filter(EventReminder.user_id == user.id, EventReminder.sent_at.is_(None)).all()
    return {"event_ids": [r[0] for r in rows]}


@router.post("/api/calendar/reminders", status_code=201, dependencies=[Depends(rate_limit_by_user(30, 60))])
def add_reminder(payload: ReminderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    event = event_calendar.find(payload.event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Táto udalosť v kalendári nie je.")
    if db.query(EventReminder).filter(EventReminder.user_id == user.id).count() >= 50:
        raise HTTPException(status_code=400, detail="Môžeš mať najviac 50 pripomienok.")
    exists = db.query(EventReminder).filter(EventReminder.user_id == user.id, EventReminder.event_id == event["id"]).first()
    if exists is None:
        db.add(EventReminder(user_id=user.id, event_id=event["id"], event_at=event_calendar.event_at(event),
                             title_key=event["kind"], coin=event.get("coin")))
        try:
            db.commit()
        except IntegrityError:          # the same reminder from a second tab at the same moment
            db.rollback()
    return {"event_id": event["id"]}


@router.delete("/api/calendar/reminders/{event_id}", dependencies=[Depends(rate_limit_by_user(30, 60))])
def remove_reminder(event_id: str = Path(max_length=64), user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    db.query(EventReminder).filter(EventReminder.user_id == user.id, EventReminder.event_id == event_id).delete()
    db.commit()
    return {"removed": True}


# ---------- push notifications and preferences ----------

PUSH_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "push.services.mozilla.com",
              "notify.windows.com", "push.apple.com")


def valid_push_endpoint(endpoint: str) -> bool:
    """Only real browser push services: the server sends requests to this URL, so anything else is refused."""
    try:
        url = urlparse(endpoint)
        host, port = (url.hostname or "").lower(), url.port
    except ValueError:
        return False
    return url.scheme == "https" and port in (None, 443) and any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=255, pattern=r"^[A-Za-z0-9_\-=]+$")
    auth: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9_\-=]+$")


class PushSubscribeIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=1024)
    keys: PushKeys


class PushEndpointIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=1024)


@router.get("/api/push/key", dependencies=PUBLIC)
def push_key() -> dict:
    return {"key": push.public_key()}


@router.post("/api/push/subscribe", status_code=201, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def push_subscribe(payload: PushSubscribeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not valid_push_endpoint(payload.endpoint):
        raise HTTPException(status_code=400, detail="Tento prehliadač nepodporuje upozornenia.")
    row = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if row is None:
        mine = (db.query(PushSubscription).filter(PushSubscription.user_id == user.id)
                .order_by(PushSubscription.created_at.asc()).all())
        for old in mine[:max(0, len(mine) - push.MAX_SUBSCRIPTIONS + 1)]:
            db.delete(old)
        db.add(PushSubscription(user_id=user.id, endpoint=payload.endpoint, p256dh=payload.keys.p256dh,
                                auth=payload.keys.auth))
    else:   # the same browser, possibly a different account now
        row.user_id, row.p256dh, row.auth = user.id, payload.keys.p256dh, payload.keys.auth
    try:
        db.commit()
    except IntegrityError:              # two tabs subscribing the same browser at once: the other one won
        db.rollback()
    return {"subscribed": True, "devices": db.query(PushSubscription).filter(PushSubscription.user_id == user.id).count()}


@router.post("/api/push/unsubscribe", dependencies=[Depends(rate_limit_by_user(30, 60))])
def push_unsubscribe(payload: PushEndpointIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    db.query(PushSubscription).filter(PushSubscription.user_id == user.id,
                                      PushSubscription.endpoint == payload.endpoint).delete()
    db.commit()
    return {"subscribed": False}


@router.post("/api/push/test", dependencies=[Depends(rate_limit_by_user(3, 60))])
def push_test(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user.id).all()
    if not subs:
        raise HTTPException(status_code=400, detail="Upozornenia v prehliadači ešte nemáš zapnuté.")
    texts = {"en": "Notifications work!", "sk": "Upozornenia fungujú!", "cs": "Upozornění fungují!",
             "de": "Benachrichtigungen funktionieren!", "pl": "Powiadomienia działają!"}
    payload = {"title": "AI Crypto Analytics", "body": texts.get(user.lang or "en", texts["en"]), "url": "/settings",
               "tag": "test"}
    sent = 0
    for sub in subs:
        status = push.send(sub, payload)
        if status in (404, 410):
            db.delete(sub)
        elif status and status < 300:
            sent += 1
    db.commit()
    return {"sent": sent}


class NotifyPrefsIn(BaseModel):
    alerts: Optional[bool] = None
    flips: Optional[bool] = None
    results: Optional[bool] = None
    events: Optional[bool] = None


@router.get("/api/account/notify-prefs")
def get_notify_prefs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    devices = db.query(PushSubscription).filter(PushSubscription.user_id == user.id).count()
    return {"prefs": push.prefs(user), "devices": devices}


@router.put("/api/account/notify-prefs", dependencies=[Depends(rate_limit_by_user(30, 60))])
def set_notify_prefs(payload: NotifyPrefsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    prefs = push.set_prefs(user, payload.model_dump(exclude_none=True))
    db.commit()
    return {"prefs": prefs}


class UiModeIn(BaseModel):
    simple_mode: bool


@router.put("/api/account/ui-mode", dependencies=[Depends(rate_limit_by_user(30, 60))])
def set_ui_mode(payload: UiModeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    user.simple_mode = payload.simple_mode
    db.commit()
    return {"simple_mode": user.simple_mode}


# ---------- "what if" ----------

@router.get("/api/tools/what-if", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def what_if(coin: str = Query(min_length=2, max_length=10), days: int = Query(default=30, ge=7, le=90),
            amount: float = Query(default=1000, gt=0, le=10_000_000), _user: User = Depends(get_current_user)) -> dict:
    if coin.upper() not in DEFAULT_COIN_IDS or days not in whatif.PERIODS:
        raise HTTPException(status_code=400, detail="Nepodporovaná minca alebo obdobie.")
    ok, data, err = whatif.run(coin, days, amount)
    if not ok:
        raise HTTPException(status_code=503, detail=err)
    return data


# ---------- CSV export ----------

EXPORT_KINDS = ("forecasts", "evaluations", "alerts", "tips", "challenge")


def _cell(value):
    """Spreadsheet-safe cell: text starting with = + - @ would run as a formula in Excel."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _forecast_numbers(raw: str):
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, None
    prices = data.get("ceny") if isinstance(data, dict) else None
    start = data.get("aktualna_cena") if isinstance(data, dict) else None
    return start, prices[-1] if isinstance(prices, list) and prices else None


def export_rows(db: Session, user: User, kind: str):
    if kind == "forecasts":
        yield ["id", "created_at", "coin", "horizon", "model", "start_price", "predicted_final_price", "shared"]
        for f in (db.query(ForecastHistory).filter(ForecastHistory.user_id == user.id, ForecastHistory.hidden_at.is_(None))
                  .order_by(ForecastHistory.created_at)):
            start, final = _forecast_numbers(f.forecast_json)
            yield [f.id, f.created_at, f.crypto_symbol, f.timeframe, f.model_used, start, final, bool(f.share_token)]
    elif kind == "evaluations":
        yield ["forecast_id", "evaluated_at", "model", "coin", "horizon", "accuracy_pct", "naive_guess_accuracy_pct",
               "direction_correct", "actual_final_price"]
        for e in (db.query(ForecastEvaluation).filter(ForecastEvaluation.user_id == user.id,
                                                      ForecastEvaluation.is_demo.isnot(True))
                  .order_by(ForecastEvaluation.evaluated_at)):
            yield [e.forecast_id, e.evaluated_at, e.provider, e.coin, e.timeframe, e.accuracy_pct, e.baseline_accuracy_pct,
                   e.direction_correct, e.actual_final_price]
    elif kind == "alerts":
        yield ["id", "created_at", "kind", "coin", "direction", "target", "active", "triggered_at", "triggered_value"]
        for a in db.query(PriceAlert).filter(PriceAlert.user_id == user.id).order_by(PriceAlert.created_at):
            yield [a.id, a.created_at, a.kind, a.coin, a.direction, a.target_price, a.active, a.triggered_at, a.triggered_price]
    elif kind == "tips":
        yield ["forecast_id", "created_at", "coin", "horizon", "your_tip", "ai_price", "outcome"]
        for t, coin, tf in (db.query(PriceTip, ForecastHistory.crypto_symbol, ForecastHistory.timeframe)
                            .join(ForecastHistory, ForecastHistory.id == PriceTip.forecast_id)
                            .filter(PriceTip.user_id == user.id, PriceTip.is_demo.isnot(True)).order_by(PriceTip.created_at)):
            yield [t.forecast_id, t.created_at, coin, tf, t.tip_price, t.ai_price, t.outcome]
    else:
        yield ["week", "coin", "your_guess", "start_price", "ai_price", "end_price", "won"]
        for e, c in (db.query(ChallengeEntry, Challenge).join(Challenge, Challenge.week == ChallengeEntry.week)
                     .filter(ChallengeEntry.user_id == user.id).order_by(Challenge.week)):
            yield [c.week, c.coin, e.price, c.start_price, c.ai_price, c.end_price,
                   None if c.end_price is None else c.winner_user_id == user.id]


@router.get("/api/account/export/{kind}.csv", dependencies=[Depends(rate_limit_by_user(10, 60))])
def export_csv(kind: Literal["forecasts", "evaluations", "alerts", "tips", "challenge"],
               user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in export_rows(db, user, kind):
        writer.writerow([_cell(v) for v in row])
    name = f"ai-crypto-{kind}-{datetime.now(timezone.utc):%Y%m%d}.csv"
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


# ---------- feedback ----------

class FeedbackIn(BaseModel):
    kind: Literal["bug", "idea", "other"] = "other"
    message: str = Field(min_length=5, max_length=2000)
    page: Optional[str] = Field(default=None, max_length=200)
    lang: Optional[str] = Field(default=None, pattern=r"^(en|sk|cs|de|pl)$")
    website: Optional[str] = Field(default=None, max_length=200)     # honeypot, real people leave it empty


def _optional_user(request: Request, db: Session) -> Optional[User]:
    try:
        return get_current_user(request, None, db)
    except HTTPException:
        return None


@router.post("/api/feedback", status_code=201, dependencies=[Depends(rate_limit_by_ip(5, 600))])
def send_feedback(payload: FeedbackIn, request: Request, db: Session = Depends(get_db)) -> dict:
    if payload.website:
        return {"received": True}
    user = _optional_user(request, db)
    if user is not None:
        check_rate_limit(f"feedback-user:{user.id}", 10, 3600)
    page = (payload.page or "").split("?")[0][:200] or None
    db.add(Feedback(user_id=user.id if user else None, kind=payload.kind, message=sanitize_text(payload.message, 2000),
                    page=sanitize_text(page, 200) if page else None, lang=payload.lang))
    db.commit()
    return {"received": True}


admin_router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_admin_user)])


@admin_router.get("/feedback")
def list_feedback(status: Literal["new", "done", "all"] = Query(default="new"), db: Session = Depends(get_db)) -> dict:
    q = db.query(Feedback, User.username).outerjoin(User, User.id == Feedback.user_id)
    if status != "all":
        q = q.filter(Feedback.status == status)
    rows = q.order_by(Feedback.created_at.desc()).limit(200).all()
    return {"items": [{"id": f.id, "kind": f.kind, "message": f.message, "page": f.page, "lang": f.lang,
                       "status": f.status, "username": username, "created_at": f.created_at.isoformat() + "Z"}
                      for f, username in rows],
            "new": db.query(Feedback).filter(Feedback.status == "new").count()}


class FeedbackStatusIn(BaseModel):
    status: Literal["new", "done"]


@admin_router.patch("/feedback/{feedback_id}")
def update_feedback(payload: FeedbackStatusIn, feedback_id: int = Path(ge=1, le=MAX_DB_ID), db: Session = Depends(get_db)) -> dict:
    row = db.get(Feedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Správa sa nenašla.")
    row.status = payload.status
    db.commit()
    return {"id": row.id, "status": row.status}


@admin_router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: int = Path(ge=1, le=MAX_DB_ID), db: Session = Depends(get_db)) -> dict:
    db.query(Feedback).filter(Feedback.id == feedback_id).delete()
    db.commit()
    return {"deleted": True}
