"""API schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

import json
import math
import re

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


MAX_DB_ID = 2_147_483_647
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str = Field(min_length=3, max_length=255)
    captcha_token: Optional[str] = Field(default=None, max_length=4096)
    lang: Optional[str] = Field(default=None, pattern=r"^(en|sk|cs|de|pl)$")
    referral_code: Optional[str] = Field(default=None, max_length=16, pattern=r"^[A-Za-z0-9]*$")


class LoginRequest(BaseModel):
    username: str
    password: str
    # A 6-digit authenticator code or a one-time recovery code ("abcd-efgh").
    totp_code: Optional[str] = Field(default=None, max_length=20)
    # Needed only after several failed attempts (instead of locking the account, which anyone could do).
    captcha_token: Optional[str] = Field(default=None, max_length=4096)


class TokenResponse(BaseModel):
    """The session lives only in the HttpOnly cookie; the token is not exposed to JavaScript."""
    access_token: Optional[str] = None
    token_type: str = "bearer"
    username: str
    user_id: int
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    totp_enabled: bool = False
    premium: bool = False
    admin: bool = False
    simple_mode: Optional[bool] = None


class ApiKeyIn(BaseModel):
    provider: str = Field(max_length=32)
    api_key: str = Field(max_length=4096)
    base_url: Optional[str] = Field(default=None, max_length=300)
    model: Optional[str] = Field(default=None, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdateEmailRequest(BaseModel):
    email: Optional[str] = None
    # Required once the current address is confirmed: a stolen session alone must not be able to redirect the
    # account's emails (and with them the password reset).
    password: Optional[str] = Field(default=None, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str
    captcha_token: Optional[str] = Field(default=None, max_length=4096)


class VerifyEmailRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpDisableRequest(BaseModel):
    """Also used to issue new recovery codes; `code` may be a recovery code when the phone is lost."""
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=20)


class VerifyResetCodeRequest(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class ApiKeyStatus(BaseModel):
    provider: str
    label: str
    connected: bool
    masked_preview: Optional[str] = None


class HoldingIn(BaseModel):
    minca: str = Field(max_length=20)
    mnozstvo: float = Field(le=1e15)
    coin_id: Optional[str] = Field(default=None, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")

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
    provider: str = Field(max_length=32)
    holdings: List[HoldingIn] = Field(max_length=30)
    lang: str = "en"


class ForecastRequest(BaseModel):
    provider: str = Field(max_length=32)
    coin: str = Field(min_length=1, max_length=16)
    horizon: Literal["4h", "24h", "1T", "1M", "1R"]
    lang: str = "en"


class AIResultOut(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    is_mock: bool = False
    error_message: Optional[str] = None
    provider_used: Optional[str] = None


class ForecastHistoryOut(BaseModel):
    id: int
    crypto_symbol: str
    timeframe: str
    model_used: str
    forecast_data: Dict[str, Any]
    created_at: datetime
    share_token: Optional[str] = None

    @field_serializer("created_at")
    def _utc_created_at(self, value: datetime) -> str:
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()

    model_config = ConfigDict(from_attributes=True)


class ForecastAccuracyOut(BaseModel):
    status: str
    accuracy_pct: Optional[float] = None
    predicted_prices: List[float]
    actual_prices: List[float]
    time_labels: List[str]
    matures_at: str
    direction_correct: Optional[bool] = None
    baseline_accuracy_pct: Optional[float] = None
    can_tip: bool = False
    tip_price: Optional[float] = None
    tip_outcome: Optional[str] = None
    ai_final_price: Optional[float] = None


class BulkDeleteRequest(BaseModel):
    ids: List[Annotated[int, Field(ge=1, le=MAX_DB_ID)]] = Field(min_length=1, max_length=100)


class TipRequest(BaseModel):
    price: float = Field(gt=0, lt=1e12)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class CostEstimateOut(BaseModel):
    is_mock: bool
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_total_tokens: int = 0
    estimated_cost_usd: float = 0.0


_MAX_SAVED_JSON_BYTES = 64 * 1024


def _check_json_size(value: Dict[str, Any]) -> Dict[str, Any]:
    try:
        size = len(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        raise ValueError("Neplatné dáta.") from None
    if size > _MAX_SAVED_JSON_BYTES:
        raise ValueError("Ukladané dáta sú príliš veľké.")
    return value


class SaveForecastRequest(BaseModel):
    provider: str = Field(max_length=32)
    coin: str = Field(min_length=1, max_length=16)
    horizon: Literal["4h", "24h", "1T", "1M", "1R"]
    forecast_data: Dict[str, Any]
    is_mock: bool = False

    @field_validator("forecast_data")
    @classmethod
    def _limit_size(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _check_json_size(value)


class SavePortfolioRequest(BaseModel):
    provider: str = Field(max_length=32)
    holdings: List[HoldingIn] = Field(max_length=30)
    analysis_data: Dict[str, Any]
    is_mock: bool = False

    @field_validator("analysis_data")
    @classmethod
    def _limit_size(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _check_json_size(value)


class PortfolioHistoryOut(BaseModel):
    id: int
    holdings: List[Dict[str, Any]]
    analysis_data: Dict[str, Any]
    model_used: str
    created_at: datetime

    @field_serializer("created_at")
    def _utc_created_at(self, value: datetime) -> str:
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()

    model_config = ConfigDict(from_attributes=True)


class PaginatedForecastHistory(BaseModel):
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


class NewsSentimentRequest(BaseModel):
    provider: Optional[str] = None
    titles: List[str] = Field(default_factory=list, max_length=20)
    lang: str = "en"


class DailyDigestRequest(BaseModel):
    provider: str
    lang: str = "en"


class ScheduleCreate(BaseModel):
    provider: str = Field(max_length=32)
    coin: str = Field(min_length=2, max_length=10)
    horizon: Literal["4h", "24h", "1T", "1M"]
    frequency: Literal["daily", "weekly"]
    weekday: Optional[int] = Field(default=None, ge=0, le=6)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    timezone: str = Field(default="UTC", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_+\-/]+$")
    lang: Literal["en", "sk", "cs", "de", "pl"] = "en"


class ScheduleUpdate(BaseModel):
    active: bool


class ScheduleOut(BaseModel):
    id: int
    provider: str
    coin: str
    horizon: str
    frequency: str
    weekday: Optional[int]
    hour: int
    minute: int
    timezone: str
    active: bool
    next_run_at: datetime
    last_run_at: Optional[datetime]
    last_status: Optional[str]
    last_error: Optional[str]
    last_forecast_id: Optional[int]

    @field_serializer("next_run_at", "last_run_at")
    def _utc(self, value: Optional[datetime]) -> Optional[str]:
        return None if value is None else (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()

    model_config = ConfigDict(from_attributes=True)


class ScheduleList(BaseModel):
    items: List[ScheduleOut]
    max: int


class WatchlistIn(BaseModel):
    coins: List[Annotated[str, Field(min_length=2, max_length=10)]] = Field(max_length=12)
