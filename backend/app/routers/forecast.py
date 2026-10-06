"""Forecast API."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

import secrets

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from sqlalchemy import case, func, or_, select
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
from app.services.backtest import BACKTEST_SETUP, run_backtest
from app.services.demo_data import DEMO_LABEL_LIKE, demo_accuracy, is_demo_label
from app.services.ai_engine import compute_forecast_accuracy, estimate_forecast_cost, get_coin_forecast

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _numeric_prices(value) -> List[float]:
    import math
    if not isinstance(value, list):
        return []
    if not all(isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) for p in value):
        return []
    return [float(p) for p in value]




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
                                                  result.data["ceny"], str(result.data.get("vytvorene", "")))
        return AIResultOut(**result.as_dict()).model_dump()

    return jobs.respond(request, user_id, compute)


@router.get("/backtest", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def backtest(coin: str = Query(min_length=2, max_length=10), horizon: str = Query(max_length=4),
             user: User = Depends(get_current_user)) -> dict:
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


@router.post("/save", response_model=ForecastHistoryOut, status_code=201)
def save_forecast(payload: SaveForecastRequest, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ForecastHistoryOut:
    label = provider_label(payload.provider)
    if label is None:
        raise HTTPException(status_code=400, detail="Neznamy AI provider.")
    if payload.is_mock:
        model_label = "mock"
    else:
        data = payload.forecast_data
        prices, created = data.get("ceny"), data.get("vytvorene")
        if (not isinstance(prices, list) or not isinstance(created, str)
                or not verify_forecast_signature(data.get("podpis"), user.id, payload.provider, payload.coin,
                                                 payload.horizon, prices, created)):
            raise HTTPException(status_code=400, detail="Predikciu sa nepodarilo overiť. Vygeneruj ju znova a ulož ju bez úprav.")
        model_label = label
    ensure_below_save_limit(db, ForecastHistory, user.id)
    entry = ForecastHistory(
        user_id=user.id, crypto_symbol=payload.coin.upper(), timeframe=payload.horizon,
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
def delete_forecast(entry_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, ForecastHistory.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == row.id).delete(synchronize_session=False)
    db.query(PriceTip).filter(PriceTip.forecast_id == row.id).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"success": True}


def _own_forecast(db: Session, user: User, entry_id: int) -> ForecastHistory:
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, ForecastHistory.user_id == user.id).first()
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
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, ForecastHistory.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    try:
        forecast_data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        forecast_data = {}
    if not isinstance(forecast_data, dict):
        forecast_data = {}
    predicted_prices = _numeric_prices(forecast_data.get("ceny"))
    time_labels = forecast_data.get("casove_body", []) if isinstance(forecast_data.get("casove_body"), list) else []
    if row.model_used == "mock":
        return ForecastAccuracyOut(status="mock", predicted_prices=predicted_prices, actual_prices=[],
                                   time_labels=time_labels, matures_at="")
    created_at = _created_at(row, forecast_data)
    if is_demo_label(row.model_used):   # generated data: scored from its stored synthetic outcome, no network
        result = demo_accuracy(forecast_data, created_at, row.timeframe)
    else:
        result = compute_forecast_accuracy(row.crypto_symbol, row.timeframe, predicted_prices, time_labels, created_at)
    _record_evaluation(db, row, result)
    tip = db.query(PriceTip).filter(PriceTip.forecast_id == row.id, PriceTip.user_id == user.id).first()
    _settle_tip(tip, result)
    _commit_ignoring_duplicates(db)
    can_tip = (tip is None and bool(predicted_prices)
               and datetime.now(timezone.utc) - _created_at(row, forecast_data) <= _TIP_WINDOW)
    return ForecastAccuracyOut(
        **result, can_tip=can_tip, tip_price=tip.tip_price if tip else None,
        tip_outcome=tip.outcome if tip else None, ai_final_price=predicted_prices[-1] if predicted_prices else None,
    )


_UTF8_BOM = chr(0xFEFF)  # lets Excel detect UTF-8 (diacritics in model names)


def _csv_cell(value) -> str:
    """Spreadsheet-safe cell: text starting with a formula character is prefixed so it is never evaluated."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", chr(9), chr(13)) and not _is_number(text) else text


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


@router.get("/history/export.csv", dependencies=[Depends(rate_limit_by_user(10, 60))])
def export_history_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    import csv
    import io

    rows = (db.query(ForecastHistory).filter(ForecastHistory.user_id == user.id)
            .order_by(ForecastHistory.created_at.desc()).all())
    evaluations = {e.forecast_id: e for e in db.query(ForecastEvaluation).filter(ForecastEvaluation.user_id == user.id)}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["created_at_utc", "coin", "horizon", "model", "price_at_forecast", "predicted_final_price",
                     "predicted_change_pct", "actual_final_price", "accuracy_pct", "direction_correct"])
    for row in rows:
        try:
            data = json.loads(row.forecast_json)
        except json.JSONDecodeError:
            data = {}
        data = data if isinstance(data, dict) else {}
        prices = _numeric_prices(data.get("ceny"))
        start = data.get("aktualna_cena") if isinstance(data.get("aktualna_cena"), (int, float)) else None
        final = prices[-1] if prices else None
        change = round((final - start) / start * 100, 2) if start and final is not None else None
        ev = evaluations.get(row.id)
        created = row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at
        writer.writerow([_csv_cell(v) for v in (
            created.isoformat(timespec="seconds"), row.crypto_symbol, row.timeframe, row.model_used, start, final, change,
            ev.actual_final_price if ev else None, ev.accuracy_pct if ev else None,
            (ev.direction_correct if ev else None),
        )])
    return Response(content=_UTF8_BOM + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="forecast-history.csv"'})


@router.get("/history", response_model=PaginatedForecastHistory)
def get_history(symbol: Optional[str] = Query(default=None, max_length=16),
                days_back: Optional[int] = Query(default=None, ge=1, le=3650),
                 page: int = Query(default=1, ge=1, le=100_000), page_size: int = Query(default=20, ge=1, le=100),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PaginatedForecastHistory:
    query = db.query(ForecastHistory).filter(ForecastHistory.user_id == user.id)
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


_TIP_WINDOW = timedelta(hours=2)
_HORIZON_DAYS = {"24h": 1, "1T": 7, "1M": 30, "1R": 365}


def _created_at(row: ForecastHistory, forecast_data: dict) -> datetime:
    row_created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
    raw = forecast_data.get("vytvorene") if isinstance(forecast_data, dict) else None
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return row_created
        parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return min(parsed, row_created)
    return row_created


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
        is_demo=True if is_demo_label(row.model_used) else None,
    ))


def _commit_ignoring_duplicates(db: Session) -> None:
    """Another request may have evaluated the same forecast concurrently; that result is equally valid."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _settle_tip(tip, result: dict) -> None:
    if tip is None or tip.outcome or result.get("status") != "completed" or not result.get("actual_prices"):
        return
    actual = result["actual_prices"][-1]
    user_error, ai_error = abs(tip.tip_price - actual), abs(tip.ai_price - actual)
    tip.outcome = "tie" if abs(user_error - ai_error) < 1e-9 else ("win" if user_error < ai_error else "loss")


_EVAL_MAX_ATTEMPTS = 8
_EVAL_RETRY_AFTER = timedelta(hours=6)


def _matured(now: datetime):
    """SQL condition: the forecast horizon has passed, so unripe long-horizon forecasts never fill the batch."""
    return or_(
        *[(ForecastHistory.timeframe == tf) & (ForecastHistory.created_at <= now - timedelta(days=days))
          for tf, days in _HORIZON_DAYS.items()],
        ForecastHistory.timeframe.not_in(list(_HORIZON_DAYS)) & (ForecastHistory.created_at <= now - timedelta(days=7)),
    )


def _mark_attempt(row: ForecastHistory, now: datetime, give_up: bool = False) -> None:
    row.eval_attempts = _EVAL_MAX_ATTEMPTS if give_up else (row.eval_attempts or 0) + 1
    row.eval_last_try_at = now


def _evaluate_pending(db: Session, limit: int = 5, deadline_seconds: float = 8.0) -> None:
    now = datetime.now(timezone.utc)
    candidates = (
        db.query(ForecastHistory)
        .filter(ForecastHistory.model_used != "mock", ForecastHistory.id.not_in(select(ForecastEvaluation.forecast_id)),
                ForecastHistory.model_used.notlike(DEMO_LABEL_LIKE), _matured(now),
                or_(ForecastHistory.eval_attempts.is_(None), ForecastHistory.eval_attempts < _EVAL_MAX_ATTEMPTS),
                or_(ForecastHistory.eval_last_try_at.is_(None), ForecastHistory.eval_last_try_at <= now - _EVAL_RETRY_AFTER))
        .order_by(ForecastHistory.created_at.asc()).limit(limit).all()
    )
    ready = []
    for row in candidates:
        try:
            data = json.loads(row.forecast_json)
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict) or not _numeric_prices(data.get("ceny")):
            _mark_attempt(row, now, give_up=True)  # can never be scored
            continue
        ready.append((row, data, _created_at(row, data)))
    if not ready:
        _commit_ignoring_duplicates(db)
        return
    pool = ThreadPoolExecutor(max_workers=limit)
    try:
        jobs = [(row, pool.submit(compute_forecast_accuracy, row.crypto_symbol, row.timeframe,
                                  _numeric_prices(data.get("ceny")), data.get("casove_body", []), created))
                for row, data, created in ready]
        end = time.monotonic() + deadline_seconds
        for row, future in jobs:
            try:
                result = future.result(timeout=max(0.1, end - time.monotonic()))
            except FuturesTimeout:
                row.eval_last_try_at = now   # just slow: retry later (no lost attempt) and let others have a turn
                continue
            except Exception:  # noqa: BLE001
                _mark_attempt(row, now)
                continue
            if result.get("status") != "completed":
                _mark_attempt(row, now)  # e.g. price history unavailable: retry later, give up after a few tries
                continue
            _record_evaluation(db, row, result)
            _settle_tip(db.query(PriceTip).filter(PriceTip.forecast_id == row.id).first(), result)
        _commit_ignoring_duplicates(db)
    finally:
        pool.shutdown(wait=False)


@router.post("/history/{entry_id}/tip", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def submit_tip(entry_id: Annotated[int, Path(ge=1, le=MAX_DB_ID)], payload: TipRequest, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    row = db.query(ForecastHistory).filter(ForecastHistory.id == entry_id, ForecastHistory.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Uložená analýza nebola nájdená.")
    try:
        forecast_data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        forecast_data = {}
    if not isinstance(forecast_data, dict):
        forecast_data = {}
    predicted = _numeric_prices(forecast_data.get("ceny"))
    if row.model_used == "mock" or not predicted:
        raise HTTPException(status_code=400, detail="Na ukážkové dáta sa tipovať nedá.")
    if datetime.now(timezone.utc) - _created_at(row, forecast_data) > _TIP_WINDOW:
        raise HTTPException(status_code=400, detail="Tipovať sa dá len do 2 hodín od vytvorenia predikcie.")
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


_MIN_SAMPLE = 5


def provider_stats(db: Session, visibility) -> list[dict]:
    """Accuracy per AI provider over the evaluations matching `visibility`, best first."""
    beats_expr = case(
        ((ForecastEvaluation.baseline_accuracy_pct.isnot(None))
         & (ForecastEvaluation.accuracy_pct > ForecastEvaluation.baseline_accuracy_pct), 1), else_=0)
    rows = (
        db.query(
            ForecastEvaluation.provider, func.count().label("n"),
            func.sum(case((ForecastEvaluation.direction_correct == True, 1), else_=0)).label("hits"),  # noqa: E712
            func.avg(ForecastEvaluation.accuracy_pct).label("acc"), func.sum(beats_expr).label("beats"),
        ).filter(visibility)
        .group_by(ForecastEvaluation.provider).all()
    )
    providers = [
        {"provider": name, "evaluated": n, "direction_hit_pct": round((hits or 0) / n * 100, 1),
         "avg_accuracy_pct": round(acc or 0.0, 1), "beats_baseline_pct": round((beats or 0) / n * 100, 1),
         "low_sample": n < _MIN_SAMPLE}
        for name, n, hits, acc, beats in rows
    ]
    providers.sort(key=lambda p: (not p["low_sample"], p["direction_hit_pct"], p["beats_baseline_pct"],
                                  p["avg_accuracy_pct"]), reverse=True)
    return providers


def _tip_summary(db: Session, user_id: Optional[int] = None) -> dict:
    query = db.query(PriceTip.outcome, func.count()).filter(PriceTip.outcome.isnot(None))
    if user_id is not None:
        query = query.filter(PriceTip.user_id == user_id)
    else:  # the community figure never includes generated demo tips
        query = query.filter(PriceTip.is_demo.isnot(True))
    counts = dict(query.group_by(PriceTip.outcome).all())
    wins, losses, ties = counts.get("win", 0), counts.get("loss", 0), counts.get("tie", 0)
    return {"wins": wins, "losses": losses, "ties": ties, "total": wins + losses + ties}


@router.get("/leaderboard", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def leaderboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _evaluate_pending(db)
    providers = provider_stats(db, or_(ForecastEvaluation.is_demo.isnot(True), ForecastEvaluation.user_id == user.id))

    pending = db.query(PriceTip).filter(PriceTip.user_id == user.id, PriceTip.outcome.is_(None)).count()
    return {
        "providers": providers, "min_sample": _MIN_SAMPLE,
        "challenge": {"you": {**_tip_summary(db, user.id), "pending": pending}, "everyone": _tip_summary(db)},
    }



@router.post("/history/bulk-delete")
def bulk_delete_forecasts(payload: BulkDeleteRequest, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)) -> dict:
    ids = [row.id for row in db.query(ForecastHistory.id).filter(
        ForecastHistory.user_id == user.id, ForecastHistory.id.in_(payload.ids)).all()]
    if ids:
        db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(PriceTip).filter(PriceTip.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(ForecastHistory).filter(ForecastHistory.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    return {"success": True, "deleted": len(ids)}
