"""Scoring of saved forecasts: checks forecasts whose horizon has ended against the real price, settles the
"beat the AI" duels and sums the results per model (the leaderboard and the public track record).

Used by the forecast API (scoring on request) and by the background scheduler (every few minutes).
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import HORIZON_HOURS
from app.models import ForecastEvaluation, ForecastHistory, PriceTip
from app.services.ai_engine import compute_forecast_accuracy
from app.services.demo_data import DEMO_LABEL_LIKE, is_demo_label
from app.services.notifications import notify
from app.services.stats import RELIABLE_SAMPLE, wilson_interval

def numeric_prices(value) -> List[float]:
    import math
    if not isinstance(value, list):
        return []
    if not all(isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) for p in value):
        return []
    return [float(p) for p in value]


_TIP_WINDOW = timedelta(hours=2)


_TIP_WINDOW_SHARE = 0.1


def tip_window(timeframe: str) -> timedelta:
    """How long after a forecast a user may still tip its final price: 2 hours, but at most a tenth of the horizon
    (a 4-hour forecast: 24 minutes), so the human never sees much more of the move than the AI did."""
    hours = HORIZON_HOURS.get(timeframe, 7 * 24)
    return min(_TIP_WINDOW, timedelta(hours=hours * _TIP_WINDOW_SHARE))


def forecast_created_at(row: ForecastHistory, forecast_data: dict) -> datetime:
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


def record_evaluation(db: Session, row: ForecastHistory, result: dict) -> None:
    if result.get("status") != "completed" or not result.get("actual_prices"):
        return
    if db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id == row.id).first():
        return
    try:
        data = json.loads(row.forecast_json)
    except json.JSONDecodeError:
        data = {}
    data = data if isinstance(data, dict) else {}

    def number(value):
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    db.add(ForecastEvaluation(
        forecast_id=row.id, user_id=row.user_id, provider=row.model_used, coin=row.crypto_symbol,
        timeframe=row.timeframe, accuracy_pct=result["accuracy_pct"],
        baseline_accuracy_pct=result.get("baseline_accuracy_pct"),
        direction_correct=bool(result.get("direction_correct")), actual_final_price=result["actual_prices"][-1],
        is_demo=True if is_demo_label(row.model_used) else None,
        confidence=number(data.get("confidence_score")),
        start_price=number(data.get("aktualna_cena")) or number(result.get("start_price")),
    ))
    if not is_demo_label(row.model_used) and row.hidden_at is None:
        notify(db, row.user_id, "forecast_evaluated", forecast_id=row.id, coin=row.crypto_symbol, horizon=row.timeframe,
               provider=row.model_used, direction_correct=bool(result.get("direction_correct")),
               accuracy_pct=result["accuracy_pct"])


def commit_ignoring_duplicates(db: Session) -> None:
    """Another request may have evaluated the same forecast concurrently; that result is equally valid."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def settle_tip(db: Session, tip, result: dict) -> None:
    if tip is None or tip.outcome or result.get("status") != "completed" or not result.get("actual_prices"):
        return
    actual = result["actual_prices"][-1]
    user_error, ai_error = abs(tip.tip_price - actual), abs(tip.ai_price - actual)
    tip.outcome = "tie" if abs(user_error - ai_error) < 1e-9 else ("win" if user_error < ai_error else "loss")
    if not tip.is_demo:
        notify(db, tip.user_id, "duel_settled", forecast_id=tip.forecast_id, outcome=tip.outcome,
               tip_price=tip.tip_price, ai_price=tip.ai_price, actual_price=actual)


_EVAL_MAX_ATTEMPTS = 8


_EVAL_RETRY_AFTER = timedelta(hours=6)


def _matured(now: datetime):
    """SQL condition: the forecast horizon has passed, so unripe long-horizon forecasts never fill the batch."""
    return or_(
        *[(ForecastHistory.timeframe == tf) & (ForecastHistory.created_at <= now - timedelta(hours=hours))
          for tf, hours in HORIZON_HOURS.items()],
        ForecastHistory.timeframe.not_in(list(HORIZON_HOURS)) & (ForecastHistory.created_at <= now - timedelta(days=7)),
    )


def _mark_attempt(row: ForecastHistory, now: datetime, give_up: bool = False) -> None:
    row.eval_attempts = _EVAL_MAX_ATTEMPTS if give_up else (row.eval_attempts or 0) + 1
    row.eval_last_try_at = now


def evaluate_pending(db: Session, limit: int = 5, deadline_seconds: float = 8.0) -> None:
    now = datetime.now(timezone.utc)
    # Deleted forecasts that can never be scored are not needed any more.
    db.query(ForecastHistory).filter(ForecastHistory.hidden_at.isnot(None),
                                     ForecastHistory.eval_attempts >= _EVAL_MAX_ATTEMPTS).delete(synchronize_session=False)
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
        if not isinstance(data, dict) or not numeric_prices(data.get("ceny")):
            _mark_attempt(row, now, give_up=True)  # can never be scored
            continue
        ready.append((row, data, forecast_created_at(row, data)))
    if not ready:
        commit_ignoring_duplicates(db)
        return
    pool = ThreadPoolExecutor(max_workers=limit)
    try:
        jobs = [(row, pool.submit(compute_forecast_accuracy, row.crypto_symbol, row.timeframe,
                                  numeric_prices(data.get("ceny")), data.get("casove_body", []), created))
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
            record_evaluation(db, row, result)
            settle_tip(db, db.query(PriceTip).filter(PriceTip.forecast_id == row.id).first(), result)
            if row.hidden_at is not None:   # deleted by the user: the result is kept, the forecast itself goes now
                db.delete(row)
        commit_ignoring_duplicates(db)
    finally:
        pool.shutdown(wait=False)


MIN_SAMPLE = 5


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
         "direction_ci": wilson_interval(hits or 0, n),
         "avg_accuracy_pct": round(acc or 0.0, 1), "avg_error_pct": round(100 - (acc or 0.0), 1),
         "beats_baseline_pct": round((beats or 0) / n * 100, 1),
         "low_sample": n < MIN_SAMPLE, "reliable": n >= RELIABLE_SAMPLE}
        for name, n, hits, acc, beats in rows
    ]
    providers.sort(key=lambda p: (not p["low_sample"], p["direction_hit_pct"], p["beats_baseline_pct"],
                                  p["avg_accuracy_pct"]), reverse=True)
    return providers


def tip_summary(db: Session, user_id: Optional[int] = None) -> dict:
    query = db.query(PriceTip.outcome, func.count()).filter(PriceTip.outcome.isnot(None))
    if user_id is not None:
        query = query.filter(PriceTip.user_id == user_id)
    else:  # the community figure never includes generated demo tips
        query = query.filter(PriceTip.is_demo.isnot(True))
    counts = dict(query.group_by(PriceTip.outcome).all())
    wins, losses, ties = counts.get("win", 0), counts.get("loss", 0), counts.get("tie", 0)
    return {"wins": wins, "losses": losses, "ties": ties, "total": wins + losses + ties}
