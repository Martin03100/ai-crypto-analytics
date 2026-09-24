"""app/schemas.py — Pydantic modely pre request/response validaciu."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str = Field(min_length=3, max_length=255)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int
    email: Optional[str] = None


class ApiKeyIn(BaseModel):
    provider: str
    api_key: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdateEmailRequest(BaseModel):
    email: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ApiKeyStatus(BaseModel):
    provider: str
    label: str
    connected: bool
    masked_preview: Optional[str] = None


class HoldingIn(BaseModel):
    minca: str
    mnozstvo: float
    coin_id: Optional[str] = None  # voliteľné CoinGecko id pre custom mince

    @field_validator("mnozstvo")
    @classmethod
    def validate_mnozstvo(cls, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("Množstvo musí byť platné číslo.")
        if value < 0:
            raise ValueError("Množstvo nemôže byť záporné.")
        return value

    @field_validator("minca")
    @classmethod
    def validate_minca(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("Symbol mince nemôže byť prázdny.")
        return cleaned


class PortfolioRequest(BaseModel):
    provider: str
    holdings: List[HoldingIn]
    lang: str = "en"


class ForecastRequest(BaseModel):
    provider: str
    coin: str
    horizon: str
    lang: str = "en"


class AIResultOut(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    is_mock: bool = False
    error_message: Optional[str] = None


class ForecastHistoryOut(BaseModel):
    id: int
    crypto_symbol: str
    timeframe: str
    model_used: str
    forecast_data: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaveForecastRequest(BaseModel):
    provider: str
    coin: str
    horizon: str
    forecast_data: Dict[str, Any]
    is_mock: bool = False


class SavePortfolioRequest(BaseModel):
    provider: str
    holdings: List[HoldingIn]
    analysis_data: Dict[str, Any]
    is_mock: bool = False


class PortfolioHistoryOut(BaseModel):
    id: int
    holdings: List[Dict[str, Any]]
    analysis_data: Dict[str, Any]
    model_used: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedForecastHistory(BaseModel):
    """Stranky historie predikcii namiesto jedneho neobmedzeneho zoznamu -
    starsie zaznamy uz nie su navzdy "neviditelne" za pevnym .limit()."""
    items: List[ForecastHistoryOut]
    total: int
    page: int
    page_size: int


class PaginatedPortfolioHistory(BaseModel):
    items: List[PortfolioHistoryOut]
    total: int
    page: int
    page_size: int


class VoteRequest(BaseModel):
    sentiment_vote: str


class DailyDigestRequest(BaseModel):
    provider: str
    lang: str = "en"
