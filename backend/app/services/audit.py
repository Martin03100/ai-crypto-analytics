"""Account activity (audit) log."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.rate_limit import get_client_ip

logger = logging.getLogger("aca.audit")

# Kept per user; older rows are pruned so the table cannot grow without bound.
MAX_EVENTS_PER_USER = 200

ACTIONS = frozenset({
    "register", "login_success", "login_failed", "account_locked", "logout", "logout_all",
    "password_changed", "password_reset", "email_changed", "api_key_saved", "api_key_deleted",
    "twofa_enabled", "twofa_disabled", "share_created", "share_revoked", "demo_data_loaded",
    "admin_settings_changed", "admin_user_changed",
})


def client_info(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    user_agent = (request.headers.get("user-agent") or "")[:255] or None
    return get_client_ip(request)[:64], user_agent


def record(db: Session, user_id: int, action: str, request: Optional[Request] = None,
           details: Optional[str] = None) -> None:
    """Add an audit row to the session. The caller commits together with the action itself,
    so a failed action never leaves a misleading log entry behind."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown audit action: {action}")
    ip, user_agent = client_info(request)
    db.add(AuditEvent(user_id=user_id, action=action, ip=ip, user_agent=user_agent,
                      details=(details or None) and details[:255]))
    db.flush()  # sessions run with autoflush off; the new row must be visible to the prune query
    _prune(db, user_id)


def _prune(db: Session, user_id: int) -> None:
    stale_ids = [row.id for row in (
        db.query(AuditEvent.id).filter(AuditEvent.user_id == user_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(MAX_EVENTS_PER_USER).all()
    )]
    if stale_ids:
        db.query(AuditEvent).filter(AuditEvent.id.in_(stale_ids)).delete(synchronize_session=False)


def is_new_device(db: Session, user_id: int, user_agent: Optional[str]) -> bool:
    """True when the user has signed in before, but never from this browser.

    The browser (user agent) is the device key on purpose: IP addresses change all the time
    on mobile networks and would trigger an alert on nearly every login."""
    if not user_agent:
        return False
    seen_before = db.query(AuditEvent.id).filter(
        AuditEvent.user_id == user_id, AuditEvent.action.in_(("login_success", "register")),
    ).first() is not None
    if not seen_before:
        return False
    same_device = db.query(AuditEvent.id).filter(
        AuditEvent.user_id == user_id, AuditEvent.action.in_(("login_success", "register")),
        AuditEvent.user_agent == user_agent,
    ).first()
    return same_device is None


def describe_user_agent(user_agent: Optional[str]) -> str:
    """Short human-readable device description, e.g. 'Chrome on Windows'."""
    ua = user_agent or ""
    if not ua:
        return "Unknown device"
    browser = next((name for token, name in (
        ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"),
    ) if token in ua), "Browser")
    system = next((name for token, name in (
        ("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iOS"),
        ("Mac OS X", "macOS"), ("Linux", "Linux"),
    ) if token in ua), "")
    return f"{browser} ({system})" if system else browser
