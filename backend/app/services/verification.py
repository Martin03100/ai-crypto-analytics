"""app/services/verification.py - odoslanie kodu na overenie emailu."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.config import EMAIL_VERIFICATION_CODE_MINUTES
from app.models import EmailVerificationCode, User
from app.security import generate_reset_code
from app.services.email_service import render_verification_email, send_email


def send_verification_code(db: Session, user: User, background_tasks: BackgroundTasks) -> None:
    """Vytvori novy kod (stare zneplatni) a odosle ho emailom AZ PO odpovedi."""
    db.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id).delete(synchronize_session=False)
    code, code_hash = generate_reset_code()
    db.add(EmailVerificationCode(user_id=user.id, code_hash=code_hash,
                                 expires_at=datetime.now(timezone.utc) + timedelta(minutes=EMAIL_VERIFICATION_CODE_MINUTES)))
    db.commit()
    text_body, html_body = render_verification_email(user.username, code, EMAIL_VERIFICATION_CODE_MINUTES)
    background_tasks.add_task(send_email, user.email, "Over si email — AI Crypto Analytics", text_body, html_body)
