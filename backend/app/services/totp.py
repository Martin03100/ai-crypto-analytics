"""One-time use of authenticator (TOTP) codes."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import User
from app.security import totp_matching_step


def consume_totp_code(db: Session, user: User, secret: str, code: str) -> bool:
    """Accept the code only if it is valid and newer than the last accepted one, and remember it.

    The check and the update are one conditional UPDATE, so two parallel requests cannot both use the same code.
    """
    step = totp_matching_step(secret, code) if secret else None
    if step is None:
        return False
    used = (db.query(User)
            .filter(User.id == user.id, or_(User.totp_last_step.is_(None), User.totp_last_step < step))
            .update({"totp_last_step": step}, synchronize_session=False))
    if not used:
        return False
    user.totp_last_step = step
    return True
