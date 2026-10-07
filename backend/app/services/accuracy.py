"""Deeper accuracy views for the public track record: confidence calibration and accuracy by market move."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import ForecastEvaluation, ForecastHistory

BUCKETS = ((0, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 101))
FLAT_BAND_PCT = 2.0           # a realized move within ±2 % counts as a sideways market
MAX_ROWS = 20000


def _rows(db: Session) -> List[tuple]:
    return (db.query(ForecastEvaluation, ForecastHistory.forecast_json)
            .join(ForecastHistory, ForecastHistory.id == ForecastEvaluation.forecast_id)
            .filter(ForecastEvaluation.is_demo.isnot(True))
            .order_by(ForecastEvaluation.id.desc()).limit(MAX_ROWS).all())


def _parse(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def regime(start: Optional[float], end: Optional[float]) -> Optional[str]:
    if not start or not end or start <= 0:
        return None
    move = (end - start) / start * 100
    return "up" if move > FLAT_BAND_PCT else "down" if move < -FLAT_BAND_PCT else "flat"


def calibration(rows) -> List[Dict[str, Any]]:
    """Does "80 % confident" mean right 80 % of the time? Direction hits per stated confidence band."""
    out = []
    for low, high in BUCKETS:
        picked = [(c, ev.direction_correct) for ev, c in rows if c is not None and low <= c < high]
        if picked:
            out.append({"band": f"{low}–{min(high, 100)}", "low": low, "high": min(high, 100), "forecasts": len(picked),
                        "claimed_pct": round(sum(c for c, _ in picked) / len(picked), 1),
                        "actual_pct": round(sum(1 for _, hit in picked if hit) / len(picked) * 100, 1)})
    return out


def by_regime(rows) -> List[Dict[str, Any]]:
    stats: Dict[tuple, List[bool]] = {}
    for ev, reg, _beats in rows:
        if reg:
            stats.setdefault((ev.provider, reg), []).append(ev.direction_correct)
    providers = sorted({p for p, _ in stats})
    return [{"provider": p, **{reg: ({"forecasts": len(v), "hit_pct": round(sum(v) / len(v) * 100, 1)}
                                     if (v := stats.get((p, reg))) else None) for reg in ("up", "down", "flat")}}
            for p in providers]


def insights(db: Session) -> Dict[str, Any]:
    cal, reg = [], []
    for ev, raw in _rows(db):
        data = _parse(raw)
        conf = data.get("confidence_score")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool) and 0 <= conf <= 100:
            cal.append((ev, float(conf)))
        start = data.get("aktualna_cena")
        reg.append((ev, regime(start if isinstance(start, (int, float)) else None, ev.actual_final_price), None))
    return {"calibration": calibration(cal), "regimes": by_regime(reg), "flat_band_pct": FLAT_BAND_PCT}
