"""Premium analytics tools. The market scanner also has a free preview (top 5 coins)."""

from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, QUANT_LABEL, RATE_LIMIT_AI_ENDPOINT
from app.deps import get_current_user, get_db
from app.models import User
from app.rate_limit import rate_limit_by_user
from app.services import app_settings, insights
from app.services.premium import is_premium, require_premium

router = APIRouter(prefix="/api/tools", tags=["tools"])

Horizon = Literal["4h", "24h", "1T", "1M", "1R"]


def _coin(coin: str) -> str:
    coin = coin.upper()
    if coin not in DEFAULT_COIN_IDS:
        raise HTTPException(status_code=400, detail="Táto minca nie je podporovaná.")
    return coin


@router.get("/model-ranking")
def model_ranking(coin: str = Query(max_length=10), horizon: Horizon = Query(),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_premium(user)
    return insights.model_ranking(db, _coin(coin), horizon)


class ForecastPoint(BaseModel):
    model: str = Field(max_length=64)
    start: float = Field(gt=0)
    final: float = Field(gt=0)


class ConsensusIn(BaseModel):
    coin: str = Field(max_length=10)
    horizon: Horizon
    forecasts: List[ForecastPoint] = Field(min_length=1, max_length=10)


@router.post("/consensus")
def consensus(payload: ConsensusIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_premium(user)
    weights = insights.model_weights(db, _coin(payload.coin), payload.horizon)
    result = insights.consensus([f.model_dump() for f in payload.forecasts], weights)
    if result is None:
        raise HTTPException(status_code=400, detail="Na konsenzus chýbajú predikcie.")
    return result


class SimulateIn(BaseModel):
    coin: str = Field(max_length=10)
    horizon: Literal["24h", "1T", "1M"]
    model: str = Field(default=QUANT_LABEL, max_length=64)
    allow_short: bool = False
    fee_pct: float = Field(default=0.1, ge=0, le=2)


@router.post("/simulate", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def simulate(payload: SimulateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_premium(user)
    result = insights.simulate(db, _coin(payload.coin), payload.horizon, payload.model, payload.allow_short, payload.fee_pct)
    if result is None:
        raise HTTPException(status_code=404, detail="Pre tento model zatiaľ nie je dosť vyhodnotených predikcií.")
    return result


@router.get("/scanner", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def scanner(user: User = Depends(get_current_user)) -> dict:
    rows = insights.scan_market()
    full = is_premium(user) or not app_settings.premium_mode()      # no paywall while Premium is switched off
    visible = rows if full else [r for r in rows if r["coin"] in insights.FREE_SCANNER_COINS]
    return {"rows": visible, "locked": 0 if full else len(rows) - len(visible),
            "premium_mode": app_settings.premium_mode()}
