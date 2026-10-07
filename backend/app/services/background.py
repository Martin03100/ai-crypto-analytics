"""Periodic background jobs run by the scheduler thread: scoring forecasts, price alerts and scheduled emails."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import JobRun

logger = logging.getLogger("aca.background")

EVALUATE_EVERY = timedelta(minutes=10)
ALERTS_EVERY = timedelta(minutes=5)
TELEGRAM_EVERY = timedelta(minutes=1)
DIGEST_WEEKDAY, DIGEST_HOUR = 0, 8      # Monday 08:00 UTC
BRIEFING_HOUR = 7                       # every day 07:00 UTC
SNAPSHOT_HOUR = 0                       # portfolio values at 00:00 UTC
STATUS_EVERY = timedelta(minutes=15)    # service checks for the 30-day status history


def _claim(name: str, due_after: datetime, now: datetime) -> bool:
    """True for exactly one caller once `due_after` has passed since the job's last run."""
    db = SessionLocal()
    try:
        row = db.get(JobRun, name)
        if row is None:
            db.add(JobRun(name=name, last_run_at=now))
            try:
                db.commit()
                return True
            except IntegrityError:
                db.rollback()
                return False
        if row.last_run_at >= due_after:
            return False
        updated = (db.query(JobRun).filter(JobRun.name == name, JobRun.last_run_at == row.last_run_at)
                   .update({JobRun.last_run_at: now}, synchronize_session=False))
        db.commit()
        return updated == 1
    finally:
        db.close()


def last_digest_slot(now: datetime) -> datetime:
    monday = (now - timedelta(days=now.weekday())).replace(hour=DIGEST_HOUR, minute=0, second=0, microsecond=0)
    return monday if now >= monday else monday - timedelta(days=7)


def last_briefing_slot(now: datetime) -> datetime:
    today = now.replace(hour=BRIEFING_HOUR, minute=0, second=0, microsecond=0)
    return today if now >= today else today - timedelta(days=1)


def _run(name: str, job: Callable) -> None:
    db = SessionLocal()
    try:
        job(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Uloha %s zlyhala: %s", name, exc)
    finally:
        db.close()


def run_periodic_jobs(now: Optional[datetime] = None) -> list[str]:
    from app.routers.forecast import _evaluate_pending
    from app.services.alerts import check_alerts
    from app.services.challenge import settle_due, week_start
    from app.services.status_check import record_sample
    from app.services.briefing import send_morning_briefings
    from app.services.digest import send_weekly_digests
    from app.services.telegram import enabled as telegram_enabled, poll_updates
    from app.services.tracker import take_snapshots

    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    ran = []
    if _claim("evaluate_forecasts", now - EVALUATE_EVERY, now):
        _run("evaluate_forecasts", lambda db: _evaluate_pending(db, limit=10, deadline_seconds=20.0))
        ran.append("evaluate_forecasts")
    if _claim("price_alerts", now - ALERTS_EVERY, now):
        _run("price_alerts", check_alerts)
        ran.append("price_alerts")
    if telegram_enabled() and _claim("telegram", now - TELEGRAM_EVERY + timedelta(seconds=5), now):
        _run("telegram", poll_updates)
        ran.append("telegram")
    briefing = last_briefing_slot(now)
    if now - briefing < timedelta(hours=3) and _claim("morning_briefing", briefing, now):
        _run("morning_briefing", send_morning_briefings)
        ran.append("morning_briefing")
    snapshot = now.replace(hour=SNAPSHOT_HOUR, minute=0, second=0, microsecond=0)
    if _claim("portfolio_snapshots", snapshot, now):
        _run("portfolio_snapshots", take_snapshots)
        ran.append("portfolio_snapshots")
    if _claim("status_history", now - STATUS_EVERY, now):
        _run("status_history", record_sample)
        ran.append("status_history")
    if _claim("weekly_challenge", week_start(now), now):
        _run("weekly_challenge", settle_due)
        ran.append("weekly_challenge")
    slot = last_digest_slot(now)
    if now - slot < timedelta(days=1) and _claim("weekly_digest", slot, now):
        _run("weekly_digest", send_weekly_digests)
        ran.append("weekly_digest")
    return ran
