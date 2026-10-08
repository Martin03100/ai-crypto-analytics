"""One-time use of authenticator (TOTP) codes and of the 2FA recovery codes."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import JWT_SECRET_KEY
from app.models import User
from app.security import totp_matching_step


INVALID, REUSED, OK, RECOVERY = "invalid", "reused", "ok", "recovery"

RECOVERY_CODE_COUNT = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"     # no 0/o, 1/l/i: easy to copy from paper
_RECOVERY_LENGTH = 8


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


def _recovery_hash(normalized: str) -> str:
    # Keyed with a server secret: a leaked database alone does not let anyone guess the codes offline.
    key = hashlib.sha256(f"2fa-recovery:{JWT_SECRET_KEY}".encode("utf-8")).digest()
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize(code: str) -> str:
    return re.sub(r"[\s-]", "", code or "").lower()


def _hashes(user: User) -> List[str]:
    try:
        value = json.loads(user.totp_recovery_json or "[]")
    except json.JSONDecodeError:
        return []
    return [h for h in value if isinstance(h, str)] if isinstance(value, list) else []


def new_recovery_codes(user: User) -> List[str]:
    """Replace the user's recovery codes with fresh ones; returns them once, formatted "abcd-efgh"."""
    raw = ["".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_LENGTH)) for _ in range(RECOVERY_CODE_COUNT)]
    user.totp_recovery_json = json.dumps([_recovery_hash(c) for c in raw])
    return [f"{c[:4]}-{c[4:]}" for c in raw]


def recovery_codes_left(user: User) -> int:
    return len(_hashes(user))


def consume_recovery_code(db: Session, user: User, code: str) -> bool:
    normalized = _normalize(code)
    if len(normalized) != _RECOVERY_LENGTH:
        return False
    current = user.totp_recovery_json
    hashes = _hashes(user)
    digest = _recovery_hash(normalized)
    match = next((h for h in hashes if hmac.compare_digest(h, digest)), None)
    if match is None:
        return False
    hashes.remove(match)
    remaining = json.dumps(hashes)
    # Conditional update: two parallel sign-ins cannot both spend the same code.
    used = (db.query(User).filter(User.id == user.id, User.totp_recovery_json == current)
            .update({"totp_recovery_json": remaining}, synchronize_session=False))
    if not used:
        return False
    user.totp_recovery_json = remaining
    return True


def verify_second_factor(db: Session, user: User, secret: str, code: str) -> str:
    """OK / REUSED / INVALID for an authenticator code, RECOVERY when a recovery code was accepted (and spent)."""
    compact = (code or "").strip().replace(" ", "")
    if compact.isdigit() and len(compact) == 6:
        return consume_totp_code(db, user, secret, compact)
    return RECOVERY if consume_recovery_code(db, user, code) else INVALID
