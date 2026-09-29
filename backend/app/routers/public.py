"""Public, read-only endpoints (no login)."""

from __future__ import annotations

import json
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.config import RATE_LIMIT_MARKET_PUBLIC
from app.deps import get_db
from app.models import ForecastEvaluation, ForecastHistory
from app.rate_limit import rate_limit_by_ip

router = APIRouter(prefix="/api/public", tags=["public"])

# Only these fields leave the server; the signature and anything added later stay private.
_SHARED_FIELDS = ("ceny", "casove_body", "odovodnenie", "pasmo", "aktualna_cena", "confidence_score",
                  "risk_level", "denna_volatilita_pct", "vytvorene", "zdroje_dat")


@router.get("/forecasts/{token}", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def shared_forecast(token: str = Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
                    db: Session = Depends(get_db)) -> dict:
    row = db.query(ForecastHistory).filter(ForecastHistory.share_token == token).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Zdieľaná predikcia neexistuje alebo jej zdieľanie bolo zrušené.")
    try:
        data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        data = {}
    data = {key: data[key] for key in _SHARED_FIELDS if isinstance(data, dict) and key in data}
    evaluation = db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == row.id).first()
    created = row.created_at.replace(tzinfo=timezone.utc) if row.created_at and not row.created_at.tzinfo else row.created_at
    return {
        "coin": row.crypto_symbol, "horizon": row.timeframe, "model": row.model_used,
        "created_at": created.isoformat() if created else None, "forecast_data": data,
        "evaluation": None if evaluation is None else {
            "accuracy_pct": evaluation.accuracy_pct, "baseline_accuracy_pct": evaluation.baseline_accuracy_pct,
            "direction_correct": evaluation.direction_correct, "actual_final_price": evaluation.actual_final_price,
        },
    }
