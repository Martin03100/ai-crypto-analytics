"""Portfolio tracker and the PDF report (Premium)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, RATE_LIMIT_AI_ENDPOINT
from app.deps import get_current_user, get_db
from app.models import PortfolioPosition, User
from app.rate_limit import rate_limit_by_user
from app.schemas import MAX_DB_ID
from app.services import report, tracker
from app.services.premium import require_premium

router = APIRouter(tags=["tracker"])


@router.get("/api/positions")
def positions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_premium(user)
    return tracker.summary(db, user)


class PositionIn(BaseModel):
    coin: str = Field(max_length=10)
    amount: float = Field(gt=0, lt=1e15)
    avg_buy_price: float = Field(gt=0, lt=1e9)


@router.put("/api/positions", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def save_position(payload: PositionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Adds a coin or replaces its amount and average buy price."""
    require_premium(user)
    coin = payload.coin.upper()
    if coin not in DEFAULT_COIN_IDS:
        raise HTTPException(status_code=400, detail="Táto minca nie je podporovaná.")
    row = db.query(PortfolioPosition).filter(PortfolioPosition.user_id == user.id, PortfolioPosition.coin == coin).first()
    if row is None:
        if db.query(PortfolioPosition).filter(PortfolioPosition.user_id == user.id).count() >= tracker.MAX_POSITIONS:
            raise HTTPException(status_code=400, detail=f"Môžeš sledovať najviac {tracker.MAX_POSITIONS} mincí.")
        db.add(PortfolioPosition(user_id=user.id, coin=coin, amount=payload.amount, avg_buy_price=payload.avg_buy_price))
    else:
        row.amount, row.avg_buy_price = payload.amount, payload.avg_buy_price
    db.commit()
    return tracker.summary(db, user)


@router.delete("/api/positions/{position_id}")
def delete_position(position_id: int = Path(ge=1, le=MAX_DB_ID), user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    require_premium(user)
    deleted = db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id, PortfolioPosition.user_id == user.id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Pozícia nebola nájdená.")
    return tracker.summary(db, user)


@router.get("/api/report.pdf", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def pdf_report(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    require_premium(user)
    name = f"ai-crypto-report-{datetime.now(timezone.utc):%Y-%m-%d}.pdf"
    return Response(report.build_report(db, user), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
