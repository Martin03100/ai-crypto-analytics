"""Forecast API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

import secrets

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, QUANT_PROVIDER, RATE_LIMIT_AI_ENDPOINT, provider_label
from app.deps import ensure_below_save_limit, get_current_user, get_db, get_decrypted_api_key
from app.models import ForecastEvaluation, ForecastHistory, PriceTip, User
from app.rate_limit import rate_limit_by_user
from app.security import sign_forecast, verify_forecast_signature
from app.schemas import MAX_DB_ID
from app.schemas import (
    AIResultOut, CostEstimateOut, ForecastAccuracyOut, ForecastHistoryOut, ForecastRequest, PaginatedForecastHistory, SaveForecastRequest, TipRequest, BulkDeleteRequest,
)
from app.services import audit, jobs
from app.services.app_settings import require_feature
from app.services.backtest import BACKTEST_SETUP, run_backtest
from app.services.demo_data import demo_accuracy, is_demo_label
from app.services.ai_engine import compute_forecast_accuracy, estimate_forecast_cost, get_coin_forecast
from app.services.stats import RELIABLE_SAMPLE
from app.services.csv_safe import UTF8_BOM, price_error, safe_cell
from app.services.scoring import (
    MIN_SAMPLE, commit_ignoring_duplicates, evaluate_pending, forecast_created_at, numeric_prices, provider_stats,
    record_evaluation, settle_tip, tip_summary, tip_window,
)

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.post("", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def generate_forecast(payload: ForecastRequest, request: Request, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    if provider_label(payload.provider) is None:
        raise HTTPException(status_code=400, detail="Neznamy AI provider.")
    api_key = None if payload.provider == QUANT_PROVIDER else get_decrypted_api_key(db, user.id, payload.provider)
    user_id = user.id

    def compute() -> dict:
        result = get_coin_forecast(payload.provider, payload.coin, payload.horizon, api_key, payload.lang)
        if result.success and result.data and not result.is_mock:
            # Sign for the provider that actually produced the data, so a quant fallback
            # can only be saved (and scored on the leaderboard) as the quant model.
            signed_provider = result.provider_used or payload.provider
            result.data["podpis"] = sign_forecast(user_id, signed_provider, payload.coin, payload.horizon,
                                                  result.data["ceny"], str(result.data.get("vytvorene", "")),
                                                  content=result.data)
        return AIResultOut(**result.as_dict()).model_dump()

    return jobs.respond(request, user_id, compute)


@router.get("/backtest", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def backtest(coin: str = Query(min_length=2, max_length=10), horizon: str = Query(max_length=4),
             user: User = Depends(get_current_user)) -> dict:
    require_feature("backtest_enabled")
    if coin.upper() not in DEFAULT_COIN_IDS or horizon not in BACKTEST_SETUP:
        raise HTTPException(status_code=400, detail="Backtest podporuje základné mince a horizonty 24h, 1T a 1M.")
    ok, data, error = run_backtest(coin, horizon)
    if not ok:
        raise HTTPException(status_code=503, detail=error)
    return data


@router.post("/estimate-cost", response_model=CostEstimateOut,
             dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def estimate_forecast_cost_endpoint(payload: ForecastRequest, user: User = Depends(get_current_user),
                                     db: Session = Depends(get_db)) -> CostEstimateOut:
    api_key = None if payload.provider == QUANT_PROVIDER else get_decrypted_api_key(db, user.id, payload.provider)
    if not api_key:
        return CostEstimateOut(is_mock=True)
    result = estimate_forecast_cost(payload.provider, payload.coin, payload.horizon)
    return CostEstimateOut(is_mock=False, **result)


# A generated forecast must be saved soon after it was made: otherwise one could wait until the horizon has passed
# and save only the forecasts that turned out right, which would bias the public track record.
SAVE_WINDOW = timedelta(minutes=15)
_DUPLICATE_SAVE = "Táto predikcia už je uložená."


def _parse_iso(raw: object) -> Optional[datetime]:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _visible(user_id: int):
    """The user's own forecasts, without the ones they deleted that still wait for scoring."""
    return (ForecastHistory.user_id == user_id) & ForecastHistory.hidden_at.is_(None)


@router.post("/save", response_model=ForecastHistoryOut, status_code=201, dependencies=[Depends(rate_limit_by_user(30, 60))])
def save_forecast(payload: SaveForecastRequest, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ForecastHistoryOut:
    label = provider_label(payload.provider)
    if label is None:
        raise HTTPException(status_code=400, detail="Neznamy AI provider.")
    signature = None
    if payload.is_mock:
        model_label = "mock"
    else:
        data = payload.forecast_data
        prices, created = data.get("ceny"), data.get("vytvorene")
        if (not isinstance(prices, list) or not isinstance(created, str)
                or not verify_forecast_signature(data.get("podpis"), user.id, payload.provider, payload.coin,
                                                 payload.horizon, prices, created, content=data)):
            raise HTTPException(status_code=400, detail="Predikciu sa nepodarilo overiť. Vygeneruj ju znova a ulož ju bez úprav.")
        created_at, now = _parse_iso(created), datetime.now(timezone.utc)
        if created_at is None or created_at > now + timedelta(minutes=2) or now - created_at > SAVE_WINDOW:
            raise HTTPException(status_code=400, detail="Predikcia je staršia ako 15 minút, už sa nedá uložiť. Vygeneruj novú.")
        signature = data["podpis"]
        if db.query(ForecastHistory.id).filter(ForecastHistory.signature == signature).first() is not None:
            raise HTTPException(status_code=409, detail=_DUPLICATE_SAVE)
        model_label = label
    ensure_below_save_limit(db, ForecastHistory, user.id, ForecastHistory.hidden_at.is_(None))
    entry = ForecastHistory(
        user_id=user.id, crypto_symbol=payload.coin.upper(), timeframe=payload.horizon,
        model_used=model_label, forecast_json=json.dumps(payload.forecast_data, ensure_ascii=False), signature=signature,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:          # the same forecast saved twice at the same moment
        db.rollback()
        raise HTTPException(status_code=409, detail=_DUPLICATE_SAVE) from None
    db.refresh(entry)
    return ForecastHistoryOut(
        id=entry.id, crypto_symbol=entry.crypto_symbol, timeframe=entry.timeframe,
        model_used=entry.model_used, forecast_data=payload.forecast_data, created_at=entry.created_at,
    )


def remove_forecasts(db: Session, rows: List[ForecastHistory]) -> None:
    """Delete forecasts from the user's history without changing the public track record.

    Sample and demo forecasts are deleted outright. A scored forecast is deleted, but its result (and a settled duel)
    stays in the anonymous statistics. A forecast that is not scored yet is only hidden: it is still scored when its
    horizon ends (so a forecast going wrong cannot be deleted away) and removed right after that."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        if row.model_used == "mock" or is_demo_label(row.model_used):
            db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == row.id).delete(synchronize_session=False)
            db.query(PriceTip).filter(PriceTip.forecast_id == row.id).delete(synchronize_session=False)
            db.delete(row)
        elif db.query(ForecastEvaluation.id).filter(ForecastEvaluation.forecast_id == row.id).first() is not None:
            db.query(PriceTip).filter(PriceTip.forecast_id == row.id, PriceTip.outcome.is_(None)).delete(synchronize_session=False)
            db.delete(row)
        else:
            row.hidden_at, row.share_token = now, None


@router.delete("/history/{entry_id}")
def delete_forecast(entry_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    remove_forecasts(db, [_own_forecast(db, user, entry_id)])
    db.commit()
    return {"success": True}


def _own_forecast(db: Session, user: User, entry_id: int) -> ForecastHistory:
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, _visible(user.id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    return row


@router.post("/history/{entry_id}/share")
def share_forecast(entry_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], request: Request,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = _own_forecast(db, user, entry_id)
    if row.model_used == "mock":
        raise HTTPException(status_code=400, detail="Ukážkové dáta sa nedajú zdieľať, nie sú to skutočná predikcia.")
    if is_demo_label(row.model_used):
        raise HTTPException(status_code=400, detail="Demo predikcie sa nedajú zdieľať, sú to vygenerované testovacie dáta.")
    if not row.share_token:
        row.share_token = secrets.token_urlsafe(24)
        audit.record(db, user.id, "share_created", request, f"{row.crypto_symbol} {row.timeframe}")
        db.commit()
    return {"share_token": row.share_token}


@router.delete("/history/{entry_id}/share")
def unshare_forecast(entry_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], request: Request,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = _own_forecast(db, user, entry_id)
    if row.share_token:
        row.share_token = None
        audit.record(db, user.id, "share_revoked", request, f"{row.crypto_symbol} {row.timeframe}")
        db.commit()
    return {"success": True}


@router.get("/history/{entry_id}/accuracy", response_model=ForecastAccuracyOut,
            dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def get_forecast_accuracy(entry_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)) -> ForecastAccuracyOut:
    row = _own_forecast(db, user, entry_id)
    try:
        forecast_data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        forecast_data = {}
    if not isinstance(forecast_data, dict):
        forecast_data = {}
    predicted_prices = numeric_prices(forecast_data.get("ceny"))
    time_labels = forecast_data.get("casove_body", []) if isinstance(forecast_data.get("casove_body"), list) else []
    if row.model_used == "mock":
        return ForecastAccuracyOut(status="mock", predicted_prices=predicted_prices, actual_prices=[],
                                   time_labels=time_labels, matures_at="")
    created_at = forecast_created_at(row, forecast_data)
    if is_demo_label(row.model_used):   # generated data: scored from its stored synthetic outcome, no network
        result = demo_accuracy(forecast_data, created_at, row.timeframe)
    else:
        result = compute_forecast_accuracy(row.crypto_symbol, row.timeframe, predicted_prices, time_labels, created_at)
    record_evaluation(db, row, result)
    tip = db.query(PriceTip).filter(PriceTip.forecast_id == row.id, PriceTip.user_id == user.id).first()
    settle_tip(db, tip, result)
    commit_ignoring_duplicates(db)
    can_tip = (tip is None and bool(predicted_prices)
               and datetime.now(timezone.utc) - forecast_created_at(row, forecast_data) <= tip_window(row.timeframe))
    return ForecastAccuracyOut(
        **result, can_tip=can_tip, tip_price=tip.tip_price if tip else None,
        tip_outcome=tip.outcome if tip else None, ai_final_price=predicted_prices[-1] if predicted_prices else None,
    )


@router.get("/history/export.csv", dependencies=[Depends(rate_limit_by_user(10, 60))])
def export_history_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    import csv
    import io

    rows = db.query(ForecastHistory).filter(_visible(user.id)).order_by(ForecastHistory.created_at.desc()).all()
    evaluations = {e.forecast_id: e for e in db.query(ForecastEvaluation).filter(ForecastEvaluation.user_id == user.id)}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["created_at_utc", "coin", "horizon", "model", "price_at_forecast", "predicted_final_price",
                     "predicted_change_pct", "actual_final_price", "price_error_pct", "direction_correct"])
    for row in rows:
        try:
            data = json.loads(row.forecast_json)
        except json.JSONDecodeError:
            data = {}
        data = data if isinstance(data, dict) else {}
        prices = numeric_prices(data.get("ceny"))
        start = data.get("aktualna_cena") if isinstance(data.get("aktualna_cena"), (int, float)) else None
        final = prices[-1] if prices else None
        change = round((final - start) / start * 100, 2) if start and final is not None else None
        ev = evaluations.get(row.id)
        created = row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at
        writer.writerow([safe_cell(v) for v in (
            created.isoformat(timespec="seconds"), row.crypto_symbol, row.timeframe, row.model_used, start, final, change,
            ev.actual_final_price if ev else None, price_error(ev.accuracy_pct) if ev else None,
            (ev.direction_correct if ev else None),
        )])
    return Response(content=UTF8_BOM + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="forecast-history.csv"'})


@router.get("/history", response_model=PaginatedForecastHistory)
def get_history(symbol: Optional[str] = Query(default=None, max_length=16),
                days_back: Optional[int] = Query(default=None, ge=1, le=3650),
                 page: int = Query(default=1, ge=1, le=100_000), page_size: int = Query(default=20, ge=1, le=100),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PaginatedForecastHistory:
    query = db.query(ForecastHistory).filter(_visible(user.id))
    if days_back is not None:
        query = query.filter(ForecastHistory.created_at >= datetime.now(timezone.utc) - timedelta(days=days_back))
    if symbol:
        query = query.filter(ForecastHistory.crypto_symbol == symbol.upper())

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
        if not isinstance(forecast_data, dict):
            forecast_data = {}
        items.append(ForecastHistoryOut(
            id=row.id, crypto_symbol=row.crypto_symbol, timeframe=row.timeframe,
            model_used=row.model_used, forecast_data=forecast_data, created_at=row.created_at,
            share_token=row.share_token,
        ))
    return PaginatedForecastHistory(items=items, total=total, page=page, page_size=page_size)


@router.post("/history/{entry_id}/tip", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def submit_tip(entry_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], payload: TipRequest, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    row = _own_forecast(db, user, entry_id)
    try:
        forecast_data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        forecast_data = {}
    if not isinstance(forecast_data, dict):
        forecast_data = {}
    predicted = numeric_prices(forecast_data.get("ceny"))
    if row.model_used == "mock" or not predicted:
        raise HTTPException(status_code=400, detail="Na ukážkové dáta sa tipovať nedá.")
    if datetime.now(timezone.utc) - forecast_created_at(row, forecast_data) > tip_window(row.timeframe):
        raise HTTPException(status_code=400, detail="Čas na tip pre túto predikciu už uplynul.")
    if db.query(PriceTip).filter(PriceTip.forecast_id == row.id).first():
        raise HTTPException(status_code=400, detail="Na túto predikciu si už tipoval.")
    try:
        ai_price = float(predicted[-1])
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Na túto predikciu sa tipovať nedá.") from None
    db.add(PriceTip(user_id=user.id, forecast_id=row.id, tip_price=payload.price, ai_price=ai_price,
                    is_demo=True if is_demo_label(row.model_used) else None))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Na túto predikciu si už tipoval.") from None
    return {"success": True}


@router.get("/leaderboard", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def leaderboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    evaluate_pending(db)
    providers = provider_stats(db, or_(ForecastEvaluation.is_demo.isnot(True), ForecastEvaluation.user_id == user.id))

    pending = db.query(PriceTip).filter(PriceTip.user_id == user.id, PriceTip.outcome.is_(None)).count()
    return {
        "providers": providers, "min_sample": MIN_SAMPLE, "reliable_sample": RELIABLE_SAMPLE,
        "challenge": {"you": {**tip_summary(db, user.id), "pending": pending}, "everyone": tip_summary(db)},
    }


@router.post("/history/bulk-delete")
def bulk_delete_forecasts(payload: BulkDeleteRequest, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)) -> dict:
    rows = db.query(ForecastHistory).filter(_visible(user.id), ForecastHistory.id.in_(payload.ids)).all()
    if rows:
        remove_forecasts(db, rows)
        db.commit()
    return {"success": True, "deleted": len(rows)}
