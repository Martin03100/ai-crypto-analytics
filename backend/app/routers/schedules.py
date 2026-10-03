"""Scheduled forecasts API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, provider_label
from app.deps import get_current_user, get_db
from app.models import ForecastSchedule, User
from app.rate_limit import rate_limit_by_user
from app.schemas import MAX_DB_ID, ScheduleCreate, ScheduleList, ScheduleOut, ScheduleUpdate
from app.services.schedules import MAX_SCHEDULES_PER_USER, compute_next_run, utcnow, zone

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _own(db: Session, user: User, schedule_id: int) -> ForecastSchedule:
    row = db.query(ForecastSchedule).filter(ForecastSchedule.id == schedule_id, ForecastSchedule.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plán predikcie nebol nájdený.")
    return row


@router.get("", response_model=ScheduleList)
def list_schedules(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ScheduleList:
    rows = db.query(ForecastSchedule).filter(ForecastSchedule.user_id == user.id).order_by(ForecastSchedule.id).all()
    return ScheduleList(items=[ScheduleOut.model_validate(r) for r in rows], max=MAX_SCHEDULES_PER_USER)


@router.post("", response_model=ScheduleOut, status_code=201,
             dependencies=[Depends(rate_limit_by_user(20, 60))])
def create_schedule(payload: ScheduleCreate, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> ScheduleOut:
    coin = payload.coin.upper()
    if provider_label(payload.provider) is None:
        raise HTTPException(status_code=400, detail="Neznamy AI provider.")
    if coin not in DEFAULT_COIN_IDS:
        raise HTTPException(status_code=400, detail="Plán predikcie podporuje len základné mince.")
    weekday = payload.weekday if payload.frequency == "weekly" else None
    if payload.frequency == "weekly" and weekday is None:
        raise HTTPException(status_code=422, detail="Pri týždennom pláne vyber deň v týždni.")
    if zone(payload.timezone) is None:
        raise HTTPException(status_code=422, detail="Neznáme časové pásmo.")
    if db.query(ForecastSchedule).filter(ForecastSchedule.user_id == user.id).count() >= MAX_SCHEDULES_PER_USER:
        raise HTTPException(status_code=400, detail=f"Môžeš mať najviac {MAX_SCHEDULES_PER_USER} plánov predikcií.")
    row = ForecastSchedule(
        user_id=user.id, provider=payload.provider, coin=coin, horizon=payload.horizon, frequency=payload.frequency,
        weekday=weekday, hour=payload.hour, minute=payload.minute, timezone=payload.timezone, lang=payload.lang,
        active=True,
        next_run_at=compute_next_run(payload.frequency, weekday, payload.hour, payload.minute, payload.timezone, utcnow()),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ScheduleOut.model_validate(row)


@router.patch("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], payload: ScheduleUpdate,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ScheduleOut:
    row = _own(db, user, schedule_id)
    if payload.active and not row.active:   # resuming: never fire for the time that passed while paused
        row.next_run_at = compute_next_run(row.frequency, row.weekday, row.hour, row.minute, row.timezone, utcnow())
    row.active = payload.active
    db.commit()
    db.refresh(row)
    return ScheduleOut.model_validate(row)


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    db.delete(_own(db, user, schedule_id))
    db.commit()
    return {"success": True}
