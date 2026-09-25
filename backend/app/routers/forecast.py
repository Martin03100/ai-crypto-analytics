"""app/routers/forecast.py — AI predikcia ceny + historia.

Analyza sa NEUKLADA automaticky po vygenerovani - uzivatel ju musi
explicitne ulozit tlacidlom "Uložiť analýzu" (POST /save), viz bod 4.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import PROVIDER_LABELS, RATE_LIMIT_AI_ENDPOINT
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import ForecastHistory, User
from app.rate_limit import rate_limit_by_user
from app.schemas import (
    AIResultOut, CostEstimateOut, ForecastAccuracyOut, ForecastHistoryOut, ForecastRequest, PaginatedForecastHistory, SaveForecastRequest,
)
from app.services.ai_engine import compute_forecast_accuracy, estimate_forecast_cost, get_coin_forecast

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.post("", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def generate_forecast(payload: ForecastRequest, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> AIResultOut:
    api_key = get_decrypted_api_key(db, user.id, payload.provider)
    result = get_coin_forecast(payload.provider, payload.coin, payload.horizon, api_key, payload.lang)
    return AIResultOut(**result.as_dict())


@router.post("/estimate-cost", response_model=CostEstimateOut,
             dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def estimate_forecast_cost_endpoint(payload: ForecastRequest, user: User = Depends(get_current_user),
                                     db: Session = Depends(get_db)) -> CostEstimateOut:
    """Odhad ceny PRED kliknutim na skutocne "Analyzovat" - frontend toto
    zavola najprv a ukaze potvrdzovacie okno, aby pouzivatel vedel priblizny
    naklad este predtym, nez sa realne minu tokeny."""
    api_key = get_decrypted_api_key(db, user.id, payload.provider)
    if not api_key:
        return CostEstimateOut(is_mock=True)
    result = estimate_forecast_cost(payload.provider, payload.coin, payload.horizon)
    return CostEstimateOut(is_mock=False, **result)


@router.post("/save", response_model=ForecastHistoryOut, status_code=201)
def save_forecast(payload: SaveForecastRequest, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ForecastHistoryOut:
    model_label = "mock" if payload.is_mock else PROVIDER_LABELS.get(payload.provider, payload.provider)
    entry = ForecastHistory(
        user_id=user.id, crypto_symbol=payload.coin, timeframe=payload.horizon,
        model_used=model_label, forecast_json=json.dumps(payload.forecast_data, ensure_ascii=False),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return ForecastHistoryOut(
        id=entry.id, crypto_symbol=entry.crypto_symbol, timeframe=entry.timeframe,
        model_used=entry.model_used, forecast_data=payload.forecast_data, created_at=entry.created_at,
    )


@router.delete("/history/{entry_id}")
def delete_forecast(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, ForecastHistory.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.get("/history/{entry_id}/accuracy", response_model=ForecastAccuracyOut,
            dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def get_forecast_accuracy(entry_id: int, user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)) -> ForecastAccuracyOut:
    """Spatne porovna ulozenu predikciu so skutocnym vyvojom ceny odvtedy
    (viz ai_engine.py::compute_forecast_accuracy) - da pouzivatelovi realny
    dokaz namiesto len sluby, ci AI predikcie maju vypovednu hodnotu."""
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, ForecastHistory.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    try:
        forecast_data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        forecast_data = {}
    predicted_prices = forecast_data.get("ceny", [])
    time_labels = forecast_data.get("casove_body", [])
    result = compute_forecast_accuracy(row.crypto_symbol, row.timeframe, predicted_prices, time_labels, row.created_at)
    return ForecastAccuracyOut(**result)


@router.get("/history", response_model=PaginatedForecastHistory)
def get_history(symbol: Optional[str] = Query(default=None), days_back: int = Query(default=30, ge=1, le=365),
                 page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PaginatedForecastHistory:
    date_from = datetime.now(timezone.utc) - timedelta(days=days_back)
    query = db.query(ForecastHistory).filter(
        ForecastHistory.user_id == user.id, ForecastHistory.created_at >= date_from
    )
    if symbol:
        query = query.filter(ForecastHistory.crypto_symbol == symbol)

    total = query.count()
    rows = (
        query.order_by(ForecastHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: List[ForecastHistoryOut] = []
    for row in rows:
        try:
            forecast_data = json.loads(row.forecast_json)
        except json.JSONDecodeError:
            forecast_data = {}
        items.append(ForecastHistoryOut(
            id=row.id, crypto_symbol=row.crypto_symbol, timeframe=row.timeframe,
            model_used=row.model_used, forecast_data=forecast_data, created_at=row.created_at,
        ))
    return PaginatedForecastHistory(items=items, total=total, page=page, page_size=page_size)
