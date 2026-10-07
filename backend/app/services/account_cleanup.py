"""Account data cleanup."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    ApiKey, AuditEvent, ChallengeEntry, CommunityVote, EmailVerificationCode, ForecastEvaluation, ForecastHistory, ForecastSchedule,
    Notification, PasswordResetToken, PortfolioHistory, PortfolioPosition, PortfolioSnapshot, PriceAlert, PriceTip, User,
)

_USER_TABLES = (ApiKey, ForecastHistory, PortfolioHistory, CommunityVote, PasswordResetToken, ForecastEvaluation,
                PriceTip, EmailVerificationCode, AuditEvent, ForecastSchedule, Notification, PriceAlert,
                PortfolioPosition, PortfolioSnapshot, ChallengeEntry)


def delete_user_data(db: Session, user: User) -> None:
    for model in _USER_TABLES:
        db.query(model).filter(model.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)


def is_abandoned_signup(db: Session, user: User) -> bool:
    """A sign-up that never confirmed its email and holds nothing of value (so a squatter cannot block an address).

    An account that changed its email (and is waiting to confirm the new one) or has any history is never
    released, otherwise anyone could delete it by registering with that address."""
    if user.email_verified is not False:
        return False
    if user.premium_until or user.stripe_customer_id:
        return False
    if db.query(AuditEvent.id).filter(AuditEvent.user_id == user.id, AuditEvent.action != "register",
                                      AuditEvent.action.notlike("login%")).first():
        return False
    for model in (ForecastHistory, PortfolioHistory, PriceTip, ForecastSchedule, PortfolioPosition):
        if db.query(model.id).filter(model.user_id == user.id).first():
            return False
    return True


def release_email_if_unverified(db: Session, email: str, requester_id: int | None = None) -> bool:
    holder = db.query(User).filter(User.email == email).first()
    if holder is None or holder.id == requester_id or not is_abandoned_signup(db, holder):
        return False
    delete_user_data(db, holder)
    db.flush()
    return True
