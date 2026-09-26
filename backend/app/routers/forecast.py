"""app/routers/forecast.py — AI predikcia ceny + historia.

Analyza sa NEUKLADA automaticky po vygenerovani - uzivatel ju musi
explicitne ulozit tlacidlom "Uložiť analýzu" (POST /save), viz bod 4.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PROVIDER_LABELS, RATE_LIMIT_AI_ENDPOINT
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import ForecastEvaluation, ForecastHistory, PriceTip, User
from app.rate_limit import rate_limit_by_user
from app.schemas import (
    AIResultOut, CostEstimateOut, ForecastAccuracyOut, ForecastHistoryOut, ForecastRequest, PaginatedForecastHistory, SaveForecastRequest, TipRequest, BulkDeleteRequest,
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
    db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == row.id).delete(synchronize_session=False)
    db.query(PriceTip).filter(PriceTip.forecast_id == row.id).delete(synchronize_session=False)
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
    if row.model_used == "mock":
        # Ukazkove data su vygenerovane demonstracnym modelom (nie AI) - ich
        # "presnost" by bola nezmyselne cislo, ktore by pouzivatela len
        # zavadzalo. Radsej jasne povieme, ze sa presnost nesleduje.
        return ForecastAccuracyOut(status="mock", predicted_prices=predicted_prices, actual_prices=[],
                                   time_labels=time_labels, matures_at="")
    created_at = row.created_at
    if isinstance(forecast_data.get("vytvorene"), str):
        try:
            created_at = datetime.fromisoformat(forecast_data["vytvorene"])  # presny cas generovania
        except ValueError:
            pass
    result = compute_forecast_accuracy(row.crypto_symbol, row.timeframe, predicted_prices, time_labels, created_at)
    _record_evaluation(db, row, result)
    tip = db.query(PriceTip).filter(PriceTip.forecast_id == row.id, PriceTip.user_id == user.id).first()
    _settle_tip(tip, result)
    db.commit()
    can_tip = (tip is None and bool(predicted_prices)
               and datetime.now(timezone.utc) - _created_at(row, forecast_data) <= _TIP_WINDOW)
    return ForecastAccuracyOut(
        **result, can_tip=can_tip, tip_price=tip.tip_price if tip else None,
        tip_outcome=tip.outcome if tip else None, ai_final_price=predicted_prices[-1] if predicted_prices else None,
    )


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


# ---------------------------------------------------------------------------
# Rebricek presnosti AI + sutaz "tvoj tip vs AI"
# ---------------------------------------------------------------------------
_TIP_WINDOW = timedelta(hours=2)
_HORIZON_DAYS = {"24h": 1, "1T": 7, "1M": 30, "1R": 365}


def _created_at(row: ForecastHistory, forecast_data: dict) -> datetime:
    created = row.created_at
    raw = forecast_data.get("vytvorene")
    if isinstance(raw, str):
        try:
            created = datetime.fromisoformat(raw)
        except ValueError:
            pass
    return created if created.tzinfo else created.replace(tzinfo=timezone.utc)


def _record_evaluation(db: Session, row: ForecastHistory, result: dict) -> None:
    if result.get("status") != "completed" or not result.get("actual_prices"):
        return
    if db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == row.id).first():
        return
    db.add(ForecastEvaluation(
        forecast_id=row.id, user_id=row.user_id, provider=row.model_used, coin=row.crypto_symbol,
        timeframe=row.timeframe, accuracy_pct=result["accuracy_pct"],
        baseline_accuracy_pct=result.get("baseline_accuracy_pct"),
        direction_correct=bool(result.get("direction_correct")), actual_final_price=result["actual_prices"][-1],
    ))


def _settle_tip(tip, result: dict) -> None:
    if tip is None or tip.outcome or result.get("status") != "completed" or not result.get("actual_prices"):
        return
    actual = result["actual_prices"][-1]
    user_error, ai_error = abs(tip.tip_price - actual), abs(tip.ai_price - actual)
    tip.outcome = "tie" if abs(user_error - ai_error) < 1e-9 else ("win" if user_error < ai_error else "loss")


def _evaluate_pending(db: Session, limit: int = 5, deadline_seconds: float = 8.0) -> None:
    """Rebricek nema cron - pri kazdom zobrazeni vyhodnoti par dozretych, este
    nevyhodnotenych predikcii (paralelne, s casovym limitom kvoli ~40s limitu
    Netlify proxy). Co sa nestihne, dokonci sa pri dalsom zobrazeni."""
    candidates = (
        db.query(ForecastHistory)
        .filter(ForecastHistory.model_used != "mock", ForecastHistory.id.not_in(select(ForecastEvaluation.forecast_id)))
        .order_by(ForecastHistory.created_at.asc()).limit(50).all()
    )
    now = datetime.now(timezone.utc)
    ready = []
    for row in candidates:
        try:
            data = json.loads(row.forecast_json)
        except json.JSONDecodeError:
            continue
        created = _created_at(row, data)
        if data.get("ceny") and now >= created + timedelta(days=_HORIZON_DAYS.get(row.timeframe, 7)):
            ready.append((row, data, created))
        if len(ready) >= limit:
            break
    if not ready:
        return
    pool = ThreadPoolExecutor(max_workers=limit)
    try:
        jobs = [(row, pool.submit(compute_forecast_accuracy, row.crypto_symbol, row.timeframe,
                                  data.get("ceny", []), data.get("casove_body", []), created))
                for row, data, created in ready]
        end = time.monotonic() + deadline_seconds
        for row, future in jobs:
            try:
                result = future.result(timeout=max(0.1, end - time.monotonic()))
            except Exception:  # noqa: BLE001
                continue
            _record_evaluation(db, row, result)
            _settle_tip(db.query(PriceTip).filter(PriceTip.forecast_id == row.id).first(), result)
        db.commit()
    finally:
        pool.shutdown(wait=False)


@router.post("/history/{entry_id}/tip", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def submit_tip(entry_id: int, payload: TipRequest, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, ForecastHistory.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    try:
        forecast_data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        forecast_data = {}
    predicted = forecast_data.get("ceny") or []
    if row.model_used == "mock" or not predicted:
        raise HTTPException(status_code=400, detail="Na ukážkové dáta sa tipovať nedá.")
    if datetime.now(timezone.utc) - _created_at(row, forecast_data) > _TIP_WINDOW:
        raise HTTPException(status_code=400, detail="Tipovať sa dá len do 2 hodín od vytvorenia predikcie.")
    if db.query(PriceTip).filter(PriceTip.forecast_id == row.id).first():
        raise HTTPException(status_code=400, detail="Na túto predikciu si už tipoval.")
    db.add(PriceTip(user_id=user.id, forecast_id=row.id, tip_price=payload.price, ai_price=float(predicted[-1])))
    db.commit()
    return {"success": True}


@router.get("/leaderboard", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def leaderboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Verejny rebricek AI providerov (zo VSETKYCH vyhodnotenych predikcii) +
    vysledky sutaze. Obsahuje len suhrnne cisla - ziadne udaje o pouzivateloch."""
    _evaluate_pending(db)
    stats: dict = {}
    for ev in db.query(ForecastEvaluation).all():
        s = stats.setdefault(ev.provider, {"count": 0, "hits": 0, "acc": 0.0, "beats": 0})
        s["count"] += 1
        s["hits"] += 1 if ev.direction_correct else 0
        s["acc"] += ev.accuracy_pct
        s["beats"] += 1 if ev.baseline_accuracy_pct is not None and ev.accuracy_pct > ev.baseline_accuracy_pct else 0
    providers = sorted(
        ({"provider": name, "evaluated": s["count"], "direction_hit_pct": round(s["hits"] / s["count"] * 100, 1),
          "avg_accuracy_pct": round(s["acc"] / s["count"], 1), "beats_baseline_pct": round(s["beats"] / s["count"] * 100, 1)}
         for name, s in stats.items()),
        key=lambda p: (p["direction_hit_pct"], p["beats_baseline_pct"], p["avg_accuracy_pct"]), reverse=True,
    )

    def summary(tips) -> dict:
        wins = sum(1 for t in tips if t.outcome == "win")
        losses = sum(1 for t in tips if t.outcome == "loss")
        ties = sum(1 for t in tips if t.outcome == "tie")
        return {"wins": wins, "losses": losses, "ties": ties, "total": wins + losses + ties}

    settled = db.query(PriceTip).filter(PriceTip.outcome.isnot(None)).all()
    pending = db.query(PriceTip).filter(PriceTip.user_id == user.id, PriceTip.outcome.is_(None)).count()
    return {
        "providers": providers,
        "challenge": {"you": {**summary([t for t in settled if t.user_id == user.id]), "pending": pending},
                      "everyone": summary(settled)},
    }



@router.post("/history/bulk-delete")
def bulk_delete_forecasts(payload: BulkDeleteRequest, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)) -> dict:
    """Zmaze viac ulozenych predikcii naraz - LEN vlastne (cudzie ID sa ticho ignoruju)."""
    ids = [row.id for row in db.query(ForecastHistory.id).filter(
        ForecastHistory.user_id == user.id, ForecastHistory.id.in_(payload.ids)).all()]
    if ids:
        db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(PriceTip).filter(PriceTip.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(ForecastHistory).filter(ForecastHistory.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    return {"success": True, "deleted": len(ids)}
