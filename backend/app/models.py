"""
app/models.py
==============
SQLAlchemy ORM modely. API kluce su ulozene VYHRADNE v sifrovanej podobe
(pozri app/security.py::encrypt_secret) - stlpec sa vola encrypted_key
aby bolo na prvy pohlad jasne, ze plain-text sa tu nikdy neuklada.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    # Zvysi sa pri "odhlasit zo vsetkych zariadeni" / zmene hesla - kazdy JWT
    # vydany PRED touto zmenou tym okamzite prestane platit (viz app/deps.py).
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Email - povinny pri registracii (routers/auth.py), pouziva sa na
    # prihlasovaci identifikator pre "Zabudnuté heslo" aj ako jedinecny
    # identifikator naprieč uctami. Stlpec ostava nullable na urovni DB
    # (spatna kompatibilita s uctami vytvorenymi este pred touto zmenou),
    # ale API vrstva ho pri registracii vzdy vyzaduje a kontroluje na
    # jedinecnost (viz routers/auth.py, routers/account.py).
    email: Mapped[str] = mapped_column(String(255), nullable=True, default=None)
    # Ochrana proti hrubej sile pri prihlaseni (viz app/config.py MAX_FAILED_LOGIN_ATTEMPTS).
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=None)

    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # AES-256 (Fernet) sifrovana hodnota - NIKDY plain text. Viz app/security.py.
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Posledne 4 znaky plain kluca pre maskovany nahlad v UI (napr. "sk-...4a2b").
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

    user: Mapped["User"] = relationship(back_populates="forecasts")


class CommunityVote(Base):
    __tablename__ = "community_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sentiment_vote: Mapped[str] = mapped_column(String(16), nullable=False)
    voted_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    user: Mapped["User"] = relationship(back_populates="votes")


class PortfolioHistory(Base):
    """Ulozena AI analyza portfolia — vznika VYHRADNE na explicitnu ziadost
    pouzivatela (tlacidlo 'Uložiť analýzu'), nie automaticky."""
    __tablename__ = "portfolio_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    holdings_json: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    user: Mapped["User"] = relationship(back_populates="portfolio_snapshots")


class PasswordResetToken(Base):
    """Token pre 'Zabudnuté heslo'. Uklada sa iba SHA-256 hash tokenu (nie
    token samotny), podobne ako pri API klucoch nikdy neukladame citatelne
    tajomstvo do DB. Token je jednorazovy (used) a casovo obmedzeny."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User"] = relationship(back_populates="reset_tokens")
