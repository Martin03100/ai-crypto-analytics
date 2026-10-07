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
    # Time step of the last accepted sign-in code; a code is accepted only once.
    totp_last_step: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    # JSON list of coin symbols the user follows on the dashboard; None = the default set.
    watchlist_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    # Public name on the tipster leaderboard; None = the user does not appear there.
    nickname: Mapped[Optional[str]] = mapped_column(String(24), unique=True, index=True, nullable=True, default=None)
    digest_opt_in: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    lang: Mapped[Optional[str]] = mapped_column(String(4), nullable=True, default=None)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True, default=None)
    referral_code: Mapped[Optional[str]] = mapped_column(String(16), unique=True, index=True, nullable=True, default=None)
    referred_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    referral_rewarded: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    # Blocked by an admin: cannot sign in and existing sessions stop working.
    disabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    briefing_opt_in: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    telegram_link_code: Mapped[Optional[str]] = mapped_column(String(16), unique=True, index=True, nullable=True, default=None)

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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    crypto_symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    model_used: Mapped[str] = mapped_column(String(32), nullable=False)
    forecast_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    # Random, unguessable token for the public read-only link; None = not shared.
    share_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None, index=True)
    # Background evaluation bookkeeping: failed attempts and when the last one ran (for back-off / giving up).
    eval_attempts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    eval_last_try_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

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
    # Evaluations of generated demo forecasts; visible only to the user who loaded the demo data.
    is_demo: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)


class PriceTip(Base):
    __tablename__ = "price_tips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    forecast_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    tip_price: Mapped[float] = mapped_column(Float, nullable=False)
    ai_price: Mapped[float] = mapped_column(Float, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    is_demo: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)



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


class ForecastSchedule(Base):
    """A forecast the server creates and saves for the user on a regular basis."""
    __tablename__ = "forecast_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    coin: Mapped[str] = mapped_column(String(16), nullable=False)
    horizon: Mapped[str] = mapped_column(String(8), nullable=False)
    frequency: Mapped[str] = mapped_column(String(8), nullable=False)  # "daily" | "weekly"
    # The user's wall-clock time in their own time zone; next_run_at (UTC) is derived from it, so DST is handled.
    weekday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0 = Monday, for weekly schedules
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    lang: Mapped[str] = mapped_column(String(4), nullable=False, default="en")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # ok | fallback | error
    last_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_forecast_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class WaitlistEntry(Base):
    """E-mail sign-ups for the upcoming Premium plan (no account needed)."""

    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    lang: Mapped[str] = mapped_column(String(4), nullable=False, default="en")
    # utm_source of the visit (e.g. "tiktok"), so it is clear which channel brings interested users.
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)


class JobRun(Base):
    """Last run of a periodic background job, shared by all backend instances."""

    __tablename__ = "job_runs"

    name: Mapped[str] = mapped_column(String(48), primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AppSetting(Base):
    """A setting the admin changes from the web; defaults live in app.services.app_settings."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class PriceAlert(Base):
    """One-shot alert: fires once when the price crosses the target, then switches itself off."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # price: USD level · move: 24h change in % · rsi: daily RSI(14) · fear_greed: market-wide index (coin "ALL")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="price", server_default="price")
    coin: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    triggered_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"
    __table_args__ = (UniqueConstraint("user_id", "coin", name="uq_position_user_coin"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    coin: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    avg_buy_price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PortfolioSnapshot(Base):
    """Daily value of the tracked positions, for the P&L chart."""

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_snapshot_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    day: Mapped[str] = mapped_column(String(10), nullable=False)
    value_usd: Mapped[float] = mapped_column(Float, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)



class StripeEvent(Base):
    """Stripe webhook events already handled; Stripe retries deliveries, each event must apply once."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class StatusSample(Base):
    """One result of the periodic service check, for the 30-day history on the status page."""

    __tablename__ = "status_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=_now)
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class Challenge(Base):
    """Weekly "Beat the AI" round: everyone guesses one coin's price for the end of the week."""

    __tablename__ = "challenges"

    week: Mapped[str] = mapped_column(String(10), primary_key=True)          # e.g. 2026-W41
    coin: Mapped[str] = mapped_column(String(16), nullable=False)
    start_price: Mapped[float] = mapped_column(Float, nullable=False)
    ai_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    end_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    winner_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ChallengeEntry(Base):
    __tablename__ = "challenge_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    week_user: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)   # one guess per week
