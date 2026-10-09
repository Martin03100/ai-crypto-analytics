"""Premium analytics: smart model, consensus, strategy simulator and market scanner."""

import json
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import ForecastEvaluation, ForecastHistory, User
from app.services import insights
from tests.conftest import csrf_headers, set_app_settings


def _premium(username):
    set_app_settings(premium_mode=True)
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update(
            {"premium_until": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)})
        db.commit()
    finally:
        db.close()


def _evals(rows):
    """rows: (provider, coin, horizon, hit, start, predicted, actual, days_ago)"""
    db = SessionLocal()
    try:
        for i, (provider, coin, horizon, hit, start, predicted, actual, days_ago) in enumerate(rows, start=1):
            created = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
            db.add(ForecastHistory(id=i, user_id=1, crypto_symbol=coin, timeframe=horizon, model_used=provider,
                                   forecast_json=json.dumps({"ceny": [predicted], "aktualna_cena": start}), created_at=created))
            db.add(ForecastEvaluation(forecast_id=i, user_id=1, provider=provider, coin=coin, timeframe=horizon,
                                      accuracy_pct=95.0, direction_correct=hit, actual_final_price=actual))
        db.commit()
    finally:
        db.close()


def test_ranking_shrinks_small_samples_and_falls_back(client):
    _evals([("Lucky", "BTC", "24h", True, 1, 2, 2, 1)] * 1
           + [("Steady", "BTC", "24h", i % 4 != 0, 1, 2, 2, i + 2) for i in range(20)])
    db = SessionLocal()
    try:
        r = insights.model_ranking(db, "BTC", "24h")
        assert r["scope"] == "coin_horizon" and r["best"] == "Steady"      # 1/1 hit does not beat 15/20
        assert insights.model_ranking(db, "ETH", "24h")["scope"] == "horizon"
        assert insights.model_ranking(db, "ETH", "1M")["scope"] == "all"
    finally:
        db.close()


def test_ranking_without_data_suggests_free_model(client):
    db = SessionLocal()
    try:
        assert insights.model_ranking(db, "BTC", "24h") == {"scope": "none", "ranking": [], "best": "Quant (free model)"}
    finally:
        db.close()


def test_consensus_weights_and_strength():
    forecasts = [{"model": "A", "start": 100, "final": 103}, {"model": "B", "start": 100, "final": 101},
                 {"model": "C", "start": 100, "final": 98}]
    c = insights.consensus(forecasts, {"A": 0.6, "B": 0.6, "C": 0.3})
    assert c["direction"] == "up" and c["agreement_pct"] == 80 and c["strength"] == "strong"
    assert c["median_change_pct"] == 1.0 and c["min_change_pct"] == -2.0 and c["max_change_pct"] == 3.0
    split = insights.consensus(forecasts[:1] + forecasts[2:], {})
    assert split["agreement_pct"] == 50 and split["strength"] == "split"
    assert insights.consensus([{"model": "x", "start": 0, "final": 1}], {}) is None


def test_simulator_math():
    trades = [{"date": "d1", "start": 100, "predicted": 110, "actual": 110},     # long, +10 %
              {"date": "d2", "start": 110, "predicted": 100, "actual": 99},      # flat (no shorting)
              {"date": "d3", "start": 99, "predicted": 120, "actual": 89.1}]     # long, -10 %
    r = insights._simulate(trades, allow_short=False, fee_pct=0)
    assert r["trades"] == 2 and r["win_rate_pct"] == 50.0
    assert r["strategy_return_pct"] == -1.0 and r["hodl_return_pct"] == -10.9
    assert r["max_drawdown_pct"] == 10.0 and len(r["curve"]) == 4
    short = insights._simulate(trades, allow_short=True, fee_pct=0)
    assert short["trades"] == 3 and short["strategy_return_pct"] == 8.9     # 1.1 x 1.1 x 0.9
    assert insights._simulate([], False, 0) is None


def test_non_overlapping_trades():
    t = [{"ts": h * 3600, "x": h} for h in (0, 10, 24, 30, 50)]
    assert [x["x"] for x in insights._non_overlapping(t, 24)] == [0, 24, 50]


def test_simulate_endpoint_uses_saved_ai_forecasts(registered):
    client, username, _p = registered
    body = {"coin": "BTC", "horizon": "24h", "model": "Gemini"}
    set_app_settings(premium_mode=True)          # the limits and gates below exist only while Premium is on
    assert client.post("/api/tools/simulate", json=body, headers=csrf_headers(client)).status_code == 403
    _premium(username)
    assert client.post("/api/tools/simulate", json=body, headers=csrf_headers(client)).status_code == 404
    _evals([("Gemini", "BTC", "24h", True, 100, 105, 104, 3), ("Gemini", "BTC", "24h", False, 104, 106, 100, 2)])
    r = client.post("/api/tools/simulate", json=body, headers=csrf_headers(client)).json()
    expected = round((1.038 * (1 + (100 / 104 - 1) - 0.002) - 1) * 100, 2)     # 0.1 % fee on entry and exit
    assert r["trades"] == 2 and r["hodl_return_pct"] == 0.0 and r["strategy_return_pct"] == expected
    assert r["model"] == "Gemini" and r["periods"] == 2
    assert client.post("/api/tools/simulate", json={**body, "fee_pct": 5}, headers=csrf_headers(client)).status_code == 422


def test_consensus_and_ranking_endpoints(registered):
    client, username, _p = registered
    body = {"coin": "BTC", "horizon": "24h", "forecasts": [{"model": "A", "start": 100, "final": 101}]}
    set_app_settings(premium_mode=True)          # the limits and gates below exist only while Premium is on
    assert client.post("/api/tools/consensus", json=body, headers=csrf_headers(client)).status_code == 403
    assert client.get("/api/tools/model-ranking?coin=BTC&horizon=24h").status_code == 403
    _premium(username)
    assert client.post("/api/tools/consensus", json=body, headers=csrf_headers(client)).json()["direction"] == "up"
    assert client.get("/api/tools/model-ranking?coin=BTC&horizon=24h").json()["scope"] == "none"
    assert client.get("/api/tools/model-ranking?coin=FAKE&horizon=24h").status_code == 400


def test_scanner_free_preview_and_premium(registered, monkeypatch):
    client, username, _p = registered
    rows = [{"coin": c, "price": 1.0, "expected_24h_pct": 0.1, "rsi": 50, "signal": "neutral"} for c in ("BTC", "PEPE", "ETH", "SUI")]
    monkeypatch.setattr(insights, "scan_market", lambda: rows)
    assert client.get("/api/tools/scanner").json()["locked"] == 0          # Premium off: nothing is locked
    set_app_settings(premium_mode=True)
    free = client.get("/api/tools/scanner").json()
    assert [r["coin"] for r in free["rows"]] == ["BTC", "ETH"] and free["locked"] == 2
    _premium(username)
    full = client.get("/api/tools/scanner").json()
    assert len(full["rows"]) == 4 and full["locked"] == 0


def test_rsi_and_signal():
    day = 86_400_000
    rising = [[i * day, 100 + i] for i in range(20)]
    falling = [[i * day, 200 - i * 5] for i in range(20)]
    assert insights.daily_rsi(rising) == 100.0 and insights.daily_rsi(falling) == 0.0
    assert insights.daily_rsi(rising[:5]) is None
    assert insights.signal(1.0, 80) == "overbought" and insights.signal(-1, 20) == "oversold"
    assert insights.signal(0.6, 50) == "bullish" and insights.signal(-0.6, 50) == "bearish" and insights.signal(0.1, None) == "neutral"
