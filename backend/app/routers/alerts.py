"""Price alerts of the signed-in user."""

from __future__ import annotations

from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, RATE_LIMIT_AI_ENDPOINT
from app.deps import get_current_user, get_db
from app.models import PriceAlert, User
from app.rate_limit import rate_limit_by_user
from app.schemas import MAX_DB_ID
from app.services.alerts import LIMITS, PREMIUM_KINDS, alert_limit
from app.services.premium import require_premium

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _out(a: PriceAlert) -> dict:
    stamp = lambda v: v.replace(tzinfo=timezone.utc).isoformat() if v else None  # noqa: E731
    return {"id": a.id, "kind": a.kind, "coin": a.coin, "direction": a.direction, "target_price": a.target_price, "active": a.active,
            "created_at": stamp(a.created_at), "triggered_at": stamp(a.triggered_at), "triggered_price": a.triggered_price}


@router.get("")
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = (db.query(PriceAlert).filter(PriceAlert.user_id == user.id)
            .order_by(PriceAlert.active.desc(), PriceAlert.created_at.desc()).limit(100).all())
    return {"items": [_out(a) for a in rows], "max": alert_limit(user),
            "active": sum(1 for a in rows if a.active), "coins": list(DEFAULT_COIN_IDS),
            "premium_kinds": list(PREMIUM_KINDS)}


class AlertIn(BaseModel):
    kind: Literal["price", "move", "rsi", "fear_greed"] = "price"
    coin: str = Field(min_length=2, max_length=10)
    direction: Literal["above", "below"]
    target_price: float = Field(gt=0, lt=1e9)


@router.post("", status_code=201, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def create_alert(payload: AlertIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    coin = "ALL" if payload.kind == "fear_greed" else payload.coin.upper()
    if coin != "ALL" and coin not in DEFAULT_COIN_IDS:
        raise HTTPException(status_code=400, detail="Táto minca nie je podporovaná.")
    low, high = LIMITS[payload.kind]
    if not low <= payload.target_price <= high:
        raise HTTPException(status_code=400, detail="Hodnota alarmu je mimo povoleného rozsahu.")
    if payload.kind in PREMIUM_KINDS:
        require_premium(user)
    limit = alert_limit(user)
    if db.query(PriceAlert).filter(PriceAlert.user_id == user.id, PriceAlert.active.is_(True)).count() >= limit:
        raise HTTPException(status_code=400, detail=f"Môžeš mať najviac {limit} aktívnych alarmov.")
    alert = PriceAlert(user_id=user.id, kind=payload.kind, coin=coin, direction=payload.direction,
                       target_price=payload.target_price)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _out(alert)


@router.delete("/{alert_id}")
def delete_alert(alert_id: int = Path(ge=1, le=MAX_DB_ID), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> dict:
    deleted = db.query(PriceAlert).filter(PriceAlert.id == alert_id, PriceAlert.user_id == user.id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Alarm nebol nájdený.")
    return {"success": True}
