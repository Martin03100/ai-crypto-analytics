"""app/routers/portfolio.py — AI analyza portfolia.

Analyza sa NEUKLADA automaticky - uzivatel ju musi explicitne ulozit
tlacidlom "Uložiť analýzu" (POST /save), rovnako ako pri predikciach.
"""

from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import PortfolioHistory, User
from app.rate_limit import rate_limit_by_user
from app.config import RATE_LIMIT_AI_ENDPOINT
from app.schemas import (
    AIResultOut, PaginatedPortfolioHistory, PortfolioHistoryOut, PortfolioRequest, SavePortfolioRequest,
)
from app.services.ai_engine import get_portfolio_analysis

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.post("/analyze", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def analyze_portfolio(payload: PortfolioRequest, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> AIResultOut:
    api_key = get_decrypted_api_key(db, user.id, payload.provider)
    holdings = [h.model_dump() for h in payload.holdings]
    result = get_portfolio_analysis(payload.provider, holdings, api_key, payload.lang)
    return AIResultOut(**result.as_dict())


@router.post("/save", response_model=PortfolioHistoryOut, status_code=201)
def save_portfolio_analysis(payload: SavePortfolioRequest, user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)) -> PortfolioHistoryOut:
    holdings = [h.model_dump() for h in payload.holdings]
    model_label = "mock" if payload.is_mock else payload.provider
    entry = PortfolioHistory(
        user_id=user.id, holdings_json=json.dumps(holdings, ensure_ascii=False),
        analysis_json=json.dumps(payload.analysis_data, ensure_ascii=False), model_used=model_label,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return PortfolioHistoryOut(
        id=entry.id, holdings=holdings, analysis_data=payload.analysis_data,
        model_used=entry.model_used, created_at=entry.created_at,
    )


@router.get("/history", response_model=PaginatedPortfolioHistory)
def get_portfolio_history(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)) -> PaginatedPortfolioHistory:
    base_query = db.query(PortfolioHistory).filter(PortfolioHistory.user_id == user.id)
    total = base_query.count()
    rows = (
        base_query.order_by(PortfolioHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items: List[PortfolioHistoryOut] = []
    for row in rows:
        try:
            holdings = json.loads(row.holdings_json)
            analysis_data = json.loads(row.analysis_json)
        except json.JSONDecodeError:
            holdings, analysis_data = [], {}
        items.append(PortfolioHistoryOut(
            id=row.id, holdings=holdings, analysis_data=analysis_data,
            model_used=row.model_used, created_at=row.created_at,
        ))
    return PaginatedPortfolioHistory(items=items, total=total, page=page, page_size=page_size)


@router.delete("/history/{entry_id}")
def delete_portfolio_analysis(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = db.query(PortfolioHistory).filter(PortfolioHistory.id == entry_id, PortfolioHistory.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    db.delete(row)
    db.commit()
    return {"success": True}
