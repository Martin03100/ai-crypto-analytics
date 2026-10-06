"""Public, read-only endpoints (no login)."""

from __future__ import annotations

import json
import re
from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import RATE_LIMIT_MARKET_PUBLIC, RATE_LIMIT_WAITLIST
from app.deps import get_db
from app.models import ForecastEvaluation, ForecastHistory, WaitlistEntry
from app.rate_limit import rate_limit_by_ip
from app.routers.forecast import _MIN_SAMPLE, _tip_summary, provider_stats
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
        "totals": {
            "evaluated": total or 0,
            "direction_hit_pct": round((hits or 0) / total * 100, 1) if total else None,
            "beats_baseline_pct": round((beats or 0) / total * 100, 1) if total else None,
        },
        # Only what the forecast was about and how it turned out; never who made it.
        "recent": [
            {"coin": e.coin, "horizon": e.timeframe, "provider": e.provider, "direction_correct": e.direction_correct,
             "accuracy_pct": round(e.accuracy_pct, 1), "evaluated_at": _iso(e.evaluated_at)}
            for e in recent
        ],
        "challenge": _tip_summary(db),
    }


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistRequest(BaseModel):
    email: str = Field(min_length=6, max_length=255)
    lang: str = Field(default="en", pattern=r"^(en|sk|cs)$")
    source: Optional[str] = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9_.-]*$")


@router.post("/waitlist", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_WAITLIST))])
def join_waitlist(payload: WaitlistRequest, db: Session = Depends(get_db)) -> dict:
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
