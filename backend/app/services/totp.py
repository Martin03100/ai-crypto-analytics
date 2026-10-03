"""One-time use of authenticator (TOTP) codes."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import User
from app.security import totp_matching_step


INVALID, REUSED, OK = "invalid", "reused", "ok"


def consume_totp_code(db: Session, user: User, secret: str, code: str) -> str:
    """Accept the code only if it is valid and newer than the last accepted one, and remember it.

    Returns OK, INVALID (wrong code) or REUSED (a correct code from a time step that was already used, e.g. the
    same code twice, or the current code right after the next one was accepted from a phone whose clock runs
    ahead). The check and the update are one conditional UPDATE, so parallel requests cannot both use a code.
    """
    step = totp_matching_step(secret, code) if secret else None
    if step is None:
        return INVALID
    used = (db.query(User)
            .filter(User.id == user.id, or_(User.totp_last_step.is_(None), User.totp_last_step < step))
            .update({"totp_last_step": step}, synchronize_session=False))
    if not used:
        return REUSED
    user.totp_last_step = step
    return OK
