"""Account data cleanup."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    ApiKey, CommunityVote, EmailVerificationCode, ForecastEvaluation, ForecastHistory, PasswordResetToken,
    PortfolioHistory, PriceTip, User,
)

_USER_TABLES = (ApiKey, ForecastHistory, PortfolioHistory, CommunityVote, PasswordResetToken, ForecastEvaluation,
                PriceTip, EmailVerificationCode)


def delete_user_data(db: Session, user: User) -> None:
    for model in _USER_TABLES:
        db.query(model).filter(model.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)


def release_email_if_unverified(db: Session, email: str, requester_id: int | None = None) -> bool:
    holder = db.query(User).filter(User.email == email).first()
    if holder is None or holder.id == requester_id or holder.email_verified is not False:
        return False
    delete_user_data(db, holder)
    db.flush()
    return True
