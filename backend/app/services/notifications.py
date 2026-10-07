"""In-app notifications (forecast results, duels, rewards)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Notification

KINDS = {"forecast_evaluated", "duel_settled", "referral_reward", "premium_started", "price_alert", "challenge_won"}
KEEP_PER_USER = 50


def notify(db: Session, user_id: int, kind: str, **data) -> None:
    """Added to the caller's session; it is committed together with the event that caused it."""
    if kind not in KINDS:
        raise ValueError(f"Unknown notification kind: {kind}")
    db.add(Notification(user_id=user_id, kind=kind, data_json=json.dumps(data, ensure_ascii=False)))


def as_dict(row: Notification) -> dict:
    try:
        data = json.loads(row.data_json)
    except json.JSONDecodeError:
        data = {}
    created = row.created_at.replace(tzinfo=timezone.utc) if row.created_at and not row.created_at.tzinfo else row.created_at
    return {"id": row.id, "kind": row.kind, "data": data, "created_at": created.isoformat() if created else None,
            "read": row.read_at is not None}


def latest(db: Session, user_id: int) -> tuple[list[dict], int]:
    rows = (db.query(Notification).filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc()).all())
    for old in rows[KEEP_PER_USER:]:
        db.delete(old)
    if len(rows) > KEEP_PER_USER:
        db.commit()
    kept = rows[:KEEP_PER_USER]
    return [as_dict(r) for r in kept], sum(1 for r in kept if r.read_at is None)


def mark_all_read(db: Session, user_id: int) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(Notification).filter(Notification.user_id == user_id, Notification.read_at.is_(None)).update(
        {Notification.read_at: now}, synchronize_session=False)
    db.commit()
