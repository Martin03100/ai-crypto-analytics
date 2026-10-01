"""Scheduled forecasts: the server creates and saves a forecast for the user at a chosen time."""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import QUANT_PROVIDER, provider_label
from app.database import SessionLocal
from app.models import ForecastHistory, ForecastSchedule

logger = logging.getLogger("aca.schedules")

MAX_SCHEDULES_PER_USER = 5
POLL_SECONDS = 60
_BATCH = 10
_PARALLEL_RUNS = 3          # one slow AI provider must not hold up everyone else's schedule


def utcnow() -> datetime:
    """Naive UTC, the format schedule times are stored in."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def zone(name: str) -> Optional[ZoneInfo]:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def compute_next_run(frequency: str, weekday: Optional[int], hour: int, minute: int, tz_name: str,
                     after: datetime) -> datetime:
    """First run strictly after `after` (naive UTC) at the given wall-clock time in the user's time zone.

    Working in the user's zone keeps the run at e.g. 08:00 local across daylight-saving changes.
    """
    tz = zone(tz_name) or timezone.utc
    local_after = after.replace(tzinfo=timezone.utc).astimezone(tz)
    day = local_after.date()
    for _ in range(9):   # at most one week ahead, plus slack for a skipped (DST) hour
        if frequency != "weekly" or day.weekday() == (weekday or 0):
            candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            utc = candidate.astimezone(timezone.utc).replace(tzinfo=None)
            if utc > after:
                return utc
        day += timedelta(days=1)
    raise ValueError("no run time found")   # unreachable for valid input


def _next_run(schedule: ForecastSchedule, after: datetime) -> datetime:
    return compute_next_run(schedule.frequency, schedule.weekday, schedule.hour, schedule.minute,
                            schedule.timezone, after)


def _run_one(schedule_id: int) -> None:
    """Create the forecast for one already-claimed schedule, in its own database session."""
    db = SessionLocal()
    try:
        schedule = db.get(ForecastSchedule, schedule_id)
        if schedule is None:
            return
        schedule.last_run_at = utcnow()
        try:
            _create_forecast(db, schedule)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - one broken schedule must not stop the others
            db.rollback()
            logger.warning("Planovana predikcia %s zlyhala: %s", schedule_id, exc)
            db.query(ForecastSchedule).filter(ForecastSchedule.id == schedule_id).update(
                {"last_run_at": utcnow(), "last_status": "error", "last_error": "internal"}, synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _create_forecast(db, schedule: ForecastSchedule) -> None:
    from app.deps import get_decrypted_api_key, save_limit_reached
    from app.services.ai_engine import get_coin_forecast

    api_key = None
    if schedule.provider != QUANT_PROVIDER:
        api_key = get_decrypted_api_key(db, schedule.user_id, schedule.provider)
        if not api_key:
            schedule.last_status, schedule.last_error = "error", "missing_key"
            return
    if save_limit_reached(db, ForecastHistory, schedule.user_id):
        schedule.last_status, schedule.last_error = "error", "limit"
        return
    result = get_coin_forecast(schedule.provider, schedule.coin, schedule.horizon, api_key, schedule.lang)
    if not result.success or not result.data or result.is_mock:
        schedule.last_status, schedule.last_error = "error", (result.error_message or "failed")[:255]
        return
    used = result.provider_used or schedule.provider
    entry = ForecastHistory(user_id=schedule.user_id, crypto_symbol=schedule.coin, timeframe=schedule.horizon,
                            model_used=provider_label(used) or used,
                            forecast_json=json.dumps(result.data, ensure_ascii=False))
    db.add(entry)
    db.flush()
    schedule.last_forecast_id = entry.id
    schedule.last_status = "fallback" if used != schedule.provider else "ok"
    schedule.last_error = (result.error_message or "")[:255] or None


def claim_due_schedules(now: datetime) -> list[int]:
    """Move each due schedule to its next run time and return the ids this call won.

    The claim is a conditional UPDATE on the run time read before the loop (plus `<= now`), so when several
    workers poll at once exactly one of them gets each schedule.
    """
    db = SessionLocal()
    try:
        due = [(row.id, row.next_run_at, row) for row in (
            db.query(ForecastSchedule)
            .filter(ForecastSchedule.active.is_(True), ForecastSchedule.next_run_at <= now)
            .order_by(ForecastSchedule.next_run_at.asc()).limit(_BATCH).all())]
        targets = [(sid, seen, _next_run(row, now)) for sid, seen, row in due]
        won = []
        for sid, seen, next_run in targets:
            claimed = (db.query(ForecastSchedule)
                       .filter(ForecastSchedule.id == sid, ForecastSchedule.next_run_at == seen,
                               ForecastSchedule.next_run_at <= now, ForecastSchedule.active.is_(True))
                       .update({"next_run_at": next_run}, synchronize_session=False))
            db.commit()
            if claimed:
                won.append(sid)
        return won
    finally:
        db.close()


def run_due_schedules(now: Optional[datetime] = None) -> int:
    """Claim and run the schedules whose time has come; returns how many ran."""
    won = claim_due_schedules(now or utcnow())
    if won:
        with ThreadPoolExecutor(max_workers=min(_PARALLEL_RUNS, len(won))) as pool:
            list(pool.map(_run_one, won))
    return len(won)


_stop = threading.Event()


def _loop() -> None:
    while not _stop.wait(POLL_SECONDS):
        try:
            run_due_schedules()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Planovac predikcii: %s", exc)


def start_scheduler() -> None:
    _stop.clear()
    threading.Thread(target=_loop, name="forecast-scheduler", daemon=True).start()
    logger.info("Planovac predikcii spusteny (kazdych %ss).", POLL_SECONDS)


def stop_scheduler() -> None:
    _stop.set()
