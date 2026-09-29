"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone

from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    forecasts: Mapped[list["ForecastHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    votes: Mapped[list["CommunityVote"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    portfolio_snapshots: Mapped[list["PortfolioHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True, default=None)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)

    email_verified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    totp_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    totp_pending_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    totp_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)

    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_suffix: Mapped[str] = mapped_column(String(8), nullable=False)

    user: Mapped["User"] = relationship(back_populates="api_keys")


class ForecastHistory(Base):
    __tablename__ = "forecast_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    crypto_symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    model_used: Mapped[str] = mapped_column(String(32), nullable=False)
    forecast_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    # Random, unguessable token for the public read-only link; None = not shared.
    share_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None, index=True)

    user: Mapped["User"] = relationship(back_populates="forecasts")


class CommunityVote(Base):
    __tablename__ = "community_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sentiment_vote: Mapped[str] = mapped_column(String(16), nullable=False)
    voted_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    user: Mapped["User"] = relationship(back_populates="votes")


class PortfolioHistory(Base):
    __tablename__ = "portfolio_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    holdings_json: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    user: Mapped["User"] = relationship(back_populates="portfolio_snapshots")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User"] = relationship(back_populates="reset_tokens")



class ForecastEvaluation(Base):
    __tablename__ = "forecast_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    coin: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    accuracy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_accuracy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    direction_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_final_price: Mapped[float] = mapped_column(Float, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PriceTip(Base):
    __tablename__ = "price_tips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    forecast_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    tip_price: Mapped[float] = mapped_column(Float, nullable=False)
    ai_price: Mapped[float] = mapped_column(Float, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)



class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditEvent(Base):
    """Security-relevant account actions, shown to the user as an activity log."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
