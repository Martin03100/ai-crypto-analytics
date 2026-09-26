"""app/schemas.py — Pydantic modely pre request/response validaciu."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import math

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str = Field(min_length=3, max_length=255)
    captcha_token: Optional[str] = Field(default=None, max_length=4096)


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = Field(default=None, max_length=10)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    totp_enabled: bool = False


class ApiKeyIn(BaseModel):
    provider: str
    api_key: str
    # len pre vlastny (OpenAI-kompatibilny) provider
    base_url: Optional[str] = Field(default=None, max_length=300)
    model: Optional[str] = Field(default=None, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdateEmailRequest(BaseModel):
    email: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str
    captcha_token: Optional[str] = Field(default=None, max_length=4096)


class VerifyEmailRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=6)


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
    # Horna hranica 30 mincí: chráni pred degenerovaným vstupom (AI analýza
    # stovky pozícií by aj tak nebola prakticky čitateľná) A zároveň drží
    # najhorší možný výstup AI odpovede predvídateľne pod _MAX_OUTPUT_TOKENS
    # limitom v ai_engine.py, takže sa nikdy neoreže uprostred JSON-u.
    holdings: List[HoldingIn] = Field(max_length=30)
    lang: str = "en"


class ForecastRequest(BaseModel):
    # Dlzky zodpovedaju stlpcom v DB - Postgres (Neon) by pri dlhsej hodnote
    # vratil chybu 500 namiesto zrozumitelnej 422.
    provider: str = Field(max_length=32)
    coin: str = Field(min_length=1, max_length=16)
    horizon: Literal["24h", "1T", "1M", "1R"]
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

    @field_serializer("created_at")
    def _utc_created_at(self, value: datetime) -> str:
        # DB uklada UTC cas bez casoveho pasma - bez neho by ho prehliadac
        # povazoval za lokalny cas (v Prahe posun o 1-2 hodiny).
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()

    model_config = ConfigDict(from_attributes=True)


class ForecastAccuracyOut(BaseModel):
    """status: "pending" (horizont este neubehol) | "unavailable" (data sa
    nepodarilo zohnat) | "completed" (realne porovnanie hotove)."""
    status: str
    accuracy_pct: Optional[float] = None
    predicted_prices: List[float]
    actual_prices: List[float]
    time_labels: List[str]
    matures_at: str
    direction_correct: Optional[bool] = None      # trafila predikcia smer (rast/pokles)?
    baseline_accuracy_pct: Optional[float] = None  # presnost naivneho odhadu "cena sa nezmeni"
    # sutaz "tvoj tip vs AI"
    can_tip: bool = False
    tip_price: Optional[float] = None
    tip_outcome: Optional[str] = None
    ai_final_price: Optional[float] = None


class BulkDeleteRequest(BaseModel):
    ids: List[int] = Field(min_length=1, max_length=100)


class TipRequest(BaseModel):
    price: float = Field(gt=0, lt=1e12)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class CostEstimateOut(BaseModel):
    """Odhad ceny PRED skutocnym volanim AI (potvrdzovacie okno na
    frontende). is_mock=true znamena, ze pouzivatel nema pripojeny API kluc -
    skutocne volanie by teda bolo zadarmo (mock rezim), odhad sa neratal."""
    is_mock: bool
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class SaveForecastRequest(BaseModel):
    provider: str = Field(max_length=32)
    coin: str = Field(min_length=1, max_length=16)
    horizon: Literal["24h", "1T", "1M", "1R"]
    forecast_data: Dict[str, Any]
    is_mock: bool = False


class SavePortfolioRequest(BaseModel):
    provider: str
    holdings: List[HoldingIn] = Field(max_length=30)
    analysis_data: Dict[str, Any]
    is_mock: bool = False


class PortfolioHistoryOut(BaseModel):
    id: int
    holdings: List[Dict[str, Any]]
    analysis_data: Dict[str, Any]
    model_used: str
    created_at: datetime

    @field_serializer("created_at")
    def _utc_created_at(self, value: datetime) -> str:
        # DB uklada UTC cas bez casoveho pasma - bez neho by ho prehliadac
        # povazoval za lokalny cas (v Prahe posun o 1-2 hodiny).
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()

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


class NewsSentimentRequest(BaseModel):
    """Predtym surovy `dict` bez validacie - neobmedzeny zoznam titulkov by
    vedel vytvorit obrovsky prompt (a zbytocne minut tokeny)."""
    provider: Optional[str] = None
    titles: List[str] = Field(default_factory=list, max_length=20)
    lang: str = "en"


class DailyDigestRequest(BaseModel):
    provider: str
    lang: str = "en"
