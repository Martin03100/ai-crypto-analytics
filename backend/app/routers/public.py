"""Public, read-only endpoints (no login)."""

from __future__ import annotations

import json
import re
from datetime import timezone
from typing import Optional

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import RATE_LIMIT_MARKET_PUBLIC, RATE_LIMIT_WAITLIST
from app.deps import get_db
from app.models import ForecastEvaluation, ForecastHistory, PriceTip, User, WaitlistEntry
from app.rate_limit import rate_limit_by_ip
from app.routers.forecast import _MIN_SAMPLE, _tip_summary, provider_stats
from app.routers.community import premium_info
from app.services import accuracy, app_settings, cards, challenge, coin_page, status_check
from app.utils.ttl_cache import TTLCache
from app.services.app_settings import public_settings, require_feature
from app.services.digest import check_unsubscribe_token
from app.services.premium import ambassador_badge, invited_signups, is_premium
from app.services.stats import RELIABLE_SAMPLE, wilson_interval
from app.services.status_check import collect_status

router = APIRouter(prefix="/api/public", tags=["public"])

# Only these fields leave the server; the signature and anything added later stay private.
_SHARED_FIELDS = ("ceny", "casove_body", "odovodnenie", "pasmo", "aktualna_cena", "confidence_score",
                  "risk_level", "denna_volatilita_pct", "vytvorene", "zdroje_dat")


@router.get("/forecasts/{token}", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def shared_forecast(token: str = Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
                    db: Session = Depends(get_db)) -> dict:
    row = db.query(ForecastHistory).filter(ForecastHistory.share_token == token).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Zdieľaná predikcia neexistuje alebo jej zdieľanie bolo zrušené.")
    try:
        data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        data = {}
    data = {key: data[key] for key in _SHARED_FIELDS if isinstance(data, dict) and key in data}
    evaluation = db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == row.id).first()
    created = row.created_at.replace(tzinfo=timezone.utc) if row.created_at and not row.created_at.tzinfo else row.created_at
    return {
        "coin": row.crypto_symbol, "horizon": row.timeframe, "model": row.model_used,
        "created_at": created.isoformat() if created else None, "forecast_data": data,
        "evaluation": None if evaluation is None else {
            "accuracy_pct": evaluation.accuracy_pct, "baseline_accuracy_pct": evaluation.baseline_accuracy_pct,
            "direction_correct": evaluation.direction_correct, "actual_final_price": evaluation.actual_final_price,
        },
    }


@router.get("/status", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def service_status() -> dict:
    # Cached for a minute, so hammering this endpoint cannot hammer the external services.
    return collect_status()


_RECENT_LIMIT = 10


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if not value.tzinfo else value).isoformat()


@router.get("/track-record", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def track_record(db: Session = Depends(get_db)) -> dict:
    """Public, anonymous accuracy record of every evaluated forecast (demo data excluded)."""
    return _track_record(db)


def _track_record(db: Session) -> dict:
    real = ForecastEvaluation.is_demo.isnot(True)
    total, hits, beats = db.query(
        func.count(),
        func.sum(case((ForecastEvaluation.direction_correct == True, 1), else_=0)),  # noqa: E712
        func.sum(case(((ForecastEvaluation.baseline_accuracy_pct.isnot(None))
                       & (ForecastEvaluation.accuracy_pct > ForecastEvaluation.baseline_accuracy_pct), 1), else_=0)),
    ).filter(real).one()
    recent = (db.query(ForecastEvaluation).filter(real)
              .order_by(ForecastEvaluation.evaluated_at.desc(), ForecastEvaluation.id.desc()).limit(_RECENT_LIMIT).all())
    return {
        "providers": provider_stats(db, real),
        "min_sample": _MIN_SAMPLE,
        "reliable_sample": RELIABLE_SAMPLE,
        "totals": {
            "evaluated": total or 0,
            "direction_hit_pct": round((hits or 0) / total * 100, 1) if total else None,
            "direction_ci": wilson_interval(hits or 0, total or 0),
            "beats_baseline_pct": round((beats or 0) / total * 100, 1) if total else None,
        },
        # Only what the forecast was about and how it turned out; never who made it.
        "recent": [
            {"coin": e.coin, "horizon": e.timeframe, "provider": e.provider, "direction_correct": e.direction_correct,
             "accuracy_pct": round(e.accuracy_pct, 1), "error_pct": round(100 - e.accuracy_pct, 1),
             "evaluated_at": _iso(e.evaluated_at)}
            for e in recent
        ],
        "challenge": _tip_summary(db),
    }


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistRequest(BaseModel):
    email: str = Field(min_length=6, max_length=255)
    lang: str = Field(default="en", pattern=r"^(en|sk|cs|de|pl)$")
    source: Optional[str] = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9_.-]*$")


_insights_cache = TTLCache(ttl_seconds=600)


@router.get("/accuracy-insights", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def accuracy_insights(db: Session = Depends(get_db)) -> dict:
    """Confidence calibration and accuracy in rising, falling and sideways markets."""
    cached = _insights_cache.get("all")
    if cached is None:
        cached = accuracy.insights(db)
        _insights_cache.set("all", cached)
    return cached


@router.get("/coin/{coin}", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def coin_page_data(coin: str = Path(min_length=2, max_length=10, pattern=r"^[A-Za-z0-9]+$"), db: Session = Depends(get_db)) -> dict:
    page = coin_page.build(db, coin)
    if page is None:
        raise HTTPException(status_code=404, detail="Táto minca nie je podporovaná.")
    return page


@router.get("/status/history", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def status_history(db: Session = Depends(get_db)) -> dict:
    return status_check.history(db)


@router.get("/challenge", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def public_challenge(db: Session = Depends(get_db)) -> dict:
    return challenge.summary(db)


@router.post("/waitlist", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_WAITLIST))])
def join_waitlist(payload: WaitlistRequest, db: Session = Depends(get_db)) -> dict:
    require_feature("waitlist_enabled")
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Zadaj platnú e-mailovú adresu.")
    if db.query(WaitlistEntry.id).filter(WaitlistEntry.email == email).first() is None:
        db.add(WaitlistEntry(email=email, lang=payload.lang, source=(payload.source or "").lower() or None))
        try:
            db.commit()
        except IntegrityError:  # signed up twice at the same moment
            db.rollback()
    # Same answer for a new and an existing address, so the endpoint cannot be used to check who signed up.
    return {"success": True}


_CARD_TTL = timedelta(minutes=10)
_card_cache: dict[str, tuple[datetime, bytes]] = {}


def _png(key: str, render) -> Response:
    now = datetime.now(timezone.utc)
    cached = _card_cache.get(key)
    if cached is None or now - cached[0] > _CARD_TTL:
        if len(_card_cache) > 500:
            _card_cache.clear()
        cached = (now, render())
        _card_cache[key] = cached
    return Response(cached[1], media_type="image/png", headers={"Cache-Control": "public, max-age=600"})


@router.get("/track-record/card.png", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def track_record_card(db: Session = Depends(get_db)) -> Response:
    def render():
        data = _track_record(db)
        return cards.track_record_card(data["totals"], data["providers"])
    return _png("track-record", render)


@router.get("/forecasts/{token}/card.png", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def shared_forecast_card(token: str = Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
                         fmt: Literal["wide", "square", "story"] = Query(default="wide"),
                         db: Session = Depends(get_db)) -> Response:
    shared = shared_forecast(token, db)
    data = shared["forecast_data"]
    prices = [p for p in data.get("ceny", []) if isinstance(p, (int, float)) and not isinstance(p, bool)]
    start = data.get("aktualna_cena") if isinstance(data.get("aktualna_cena"), (int, float)) else None
    state = "done" if shared["evaluation"] else "pending"
    if fmt != "wide":
        return _png(f"forecast:{token}:{state}:{fmt}", lambda: cards.forecast_card_tall(
            fmt, shared["coin"], shared["horizon"], shared["model"], prices, start, shared["evaluation"]))
    return _png(f"forecast:{token}:{state}", lambda: cards.forecast_card(
        shared["coin"], shared["horizon"], shared["model"], prices, start, shared["evaluation"]))


def week_start(now: datetime) -> datetime:
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/tipsters", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def tipsters(period: Literal["week", "all"] = Query(default="week"), db: Session = Depends(get_db)) -> dict:
    """Best price tippers who chose a public nickname; the weekly board is the "Beat the AI" challenge."""
    require_feature("tipsters_enabled")
    since = week_start(datetime.now(timezone.utc).replace(tzinfo=None))
    settled = (PriceTip.outcome.isnot(None)) & (PriceTip.is_demo.isnot(True))
    if period == "week":
        settled = settled & (PriceTip.created_at >= since)
    wins = func.sum(case((PriceTip.outcome == "win", 1), else_=0))
    rows = (db.query(User, func.count(PriceTip.id), wins).join(PriceTip, PriceTip.user_id == User.id)
            .filter(settled, User.nickname.isnot(None)).group_by(User.id)
            .order_by(wins.desc(), func.count(PriceTip.id).asc()).limit(10).all())
    outcomes = dict(db.query(PriceTip.outcome, func.count()).filter(settled).group_by(PriceTip.outcome).all())
    return {
        "period": period, "week_start": since.isoformat() + "Z",
        "leaders": [{"nickname": u.nickname, "duels": n, "wins": int(w or 0), "win_pct": round((w or 0) / n * 100),
                     "premium": is_premium(u) and app_settings.premium_mode(), "badge": ambassador_badge(invited_signups(db, u.id)),
                     "challenge_wins": challenge.wins(db, u.id)}
                    for u, n, w in rows],
        "humans_vs_ai": {"wins": outcomes.get("win", 0), "losses": outcomes.get("loss", 0), "ties": outcomes.get("tie", 0)},
    }


@router.get("/premium")
def premium() -> dict:
    return premium_info()


@router.get("/config")
def public_config() -> dict:
    """Feature switches and the announcement banner the admin controls, plus the Premium offer."""
    return {**public_settings(), "premium": premium_info()}


class UnsubscribeRequest(BaseModel):
    user_id: int = Field(ge=1)
    token: str = Field(min_length=16, max_length=64)


@router.post("/digest/unsubscribe", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_WAITLIST))])
def unsubscribe_digest(payload: UnsubscribeRequest, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, payload.user_id)
    if user is None or not check_unsubscribe_token(user.id, payload.token):
        raise HTTPException(status_code=400, detail="Odkaz na odhlásenie je neplatný.")
    user.digest_opt_in = False
    db.commit()
    return {"success": True}
