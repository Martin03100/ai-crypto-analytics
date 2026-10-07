"""Weekly challenge, status history, accuracy insights, coin pages, admin backup and share card formats."""

import gzip
import json
from datetime import datetime, timedelta

import pytest

from app import config
from app.database import SessionLocal
from app.models import (Challenge, ChallengeEntry, ForecastEvaluation, ForecastHistory, Notification, StatusSample,
                        User)
from app.services import accuracy, challenge, coin_page, status_check
from tests.conftest import csrf_headers

MONDAY = datetime(2026, 10, 12, 9, 0)


@pytest.fixture()
def prices(monkeypatch):
    state = {"price": 100.0}
    monkeypatch.setattr(challenge, "_price", lambda coin: state["price"])
    monkeypatch.setattr(challenge.quant_engine, "build_quant_forecast",
                        lambda coin, h, lang: (True, {"ceny": [104.0], "aktualna_cena": 100.0}, None))
    return state


def _uid(username):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).one().id
    finally:
        db.close()


def test_week_ids_rotation_and_deadline():
    assert challenge.week_id(MONDAY) == "2026-W42"
    assert challenge.coin_for("2026-W42") in challenge.ROTATION
    assert challenge.coin_for("2026-W42") != challenge.coin_for("2026-W43")
    assert challenge.deadline(Challenge(week="2026-W42")) == datetime(2026, 10, 15)


def test_challenge_round_entries_and_settlement(registered, prices):
    client, username, _p = registered
    db = SessionLocal()
    try:
        row = challenge.current(db, MONDAY)
        assert row.start_price == 100.0 and row.ai_price == 104.0
        user = db.get(User, _uid(username))
        challenge.enter(db, user, 110.0, MONDAY)
        with pytest.raises(ValueError, match="už máš tip"):
            challenge.enter(db, user, 111.0, MONDAY)
        with pytest.raises(ValueError, match="rozsahu"):
            challenge.enter(db, user, 900.0, MONDAY)
        other = User(username="rival1", password_hash="x", email="r@example.com")
        db.add(other)
        db.commit()
        challenge.enter(db, other, 120.0, MONDAY + timedelta(days=1))
        with pytest.raises(ValueError, match="uzavreté"):
            challenge.enter(db, other, 99.0, MONDAY + timedelta(days=3))
        prices["price"] = 112.0
        assert challenge.settle_due(db, MONDAY) == 0                      # this week is still running
        assert challenge.settle_due(db, MONDAY + timedelta(days=7)) == 1
        db.refresh(row)
        assert row.end_price == 112.0 and row.winner_user_id == user.id
        assert db.query(Notification).filter(Notification.kind == "challenge_won").count() == 1
        summary = challenge.summary(db, user, MONDAY + timedelta(days=7))
    finally:
        db.close()
    last = summary["last"]
    assert last["winner"] == "anonymous" and last["entries"] == 2 and last["you_won"] is True
    assert last["ai_error_pct"] == 7.14 and last["beat_ai"] == 1 and summary["my_wins"] == 1


def test_challenge_endpoints(registered, prices):
    client, _u, _p = registered
    assert client.get("/api/public/challenge").json()["current"]["coin"]
    res = client.post("/api/challenge/entry", json={"price": 101.5}, headers=csrf_headers(client))
    assert res.status_code in (201, 400)          # 400 only if the test runs after Thursday's cut-off
    if res.status_code == 201:
        assert res.json()["current"]["my_price"] == 101.5
        assert client.post("/api/challenge/entry", json={"price": 1}, headers=csrf_headers(client)).status_code == 400
    assert "my_wins" in client.get("/api/challenge").json()
    data = client.get("/api/account/export").json()
    assert "weekly_challenge_guesses" in data


def test_status_history_records_and_aggregates(client, monkeypatch):
    monkeypatch.setattr(status_check, "collect_status", lambda: {"services": [
        {"id": "backend", "status": "up", "latency_ms": 1}, {"id": "coingecko", "status": "down", "latency_ms": None},
        {"id": "blockchair", "status": "degraded", "latency_ms": 900}]})
    db = SessionLocal()
    try:
        status_check.record_sample(db)
        db.add(StatusSample(checked_at=datetime(2020, 1, 1), service="backend", status="down"))
        db.commit()
        status_check.record_sample(db)                  # also prunes samples older than ~35 days
        assert db.query(StatusSample).count() == 6
    finally:
        db.close()
    hist = client.get("/api/public/status/history").json()
    assert len(hist["days"]) == 30
    by_id = {s["id"]: s for s in hist["services"]}
    assert by_id["backend"]["uptime_pct"] == 100.0 and by_id["coingecko"]["uptime_pct"] == 0.0
    assert by_id["blockchair"]["uptime_pct"] == 100.0           # slow or rate-limited is not an outage
    assert by_id["backend"]["days"][-1]["uptime_pct"] == 100.0 and by_id["backend"]["days"][0]["uptime_pct"] is None


def test_accuracy_insights(client):
    db = SessionLocal()
    try:
        rows = [("Gemini", 85, 100, 110, True), ("Gemini", 82, 100, 90, False), ("Gemini", 55, 100, 101, True),
                ("Claude", 75, 100, 95, True)]
        for i, (provider, conf, start, end, hit) in enumerate(rows, start=1):
            db.add(ForecastHistory(id=i, user_id=1, crypto_symbol="BTC", timeframe="24h", model_used=provider,
                                   forecast_json=json.dumps({"ceny": [1], "aktualna_cena": start, "confidence_score": conf})))
            db.add(ForecastEvaluation(forecast_id=i, user_id=1, provider=provider, coin="BTC", timeframe="24h",
                                      accuracy_pct=95, direction_correct=hit, actual_final_price=end))
        db.commit()
    finally:
        db.close()
    data = client.get("/api/public/accuracy-insights").json()
    bands = {b["band"]: b for b in data["calibration"]}
    assert bands["80–90"] == {"band": "80–90", "low": 80, "high": 90, "forecasts": 2, "claimed_pct": 83.5, "actual_pct": 50.0}
    gemini = next(r for r in data["regimes"] if r["provider"] == "Gemini")
    assert gemini["up"] == {"forecasts": 1, "hit_pct": 100.0} and gemini["down"]["hit_pct"] == 0.0
    assert gemini["flat"] == {"forecasts": 1, "hit_pct": 100.0}
    assert accuracy.regime(100, 101.9) == "flat" and accuracy.regime(None, 5) is None


def test_coin_page(client, monkeypatch):
    monkeypatch.setattr(coin_page.market_data, "get_coin_markets", lambda ids: (True, {"solana": {
        "name": "Solana", "current_price": 150.0, "market_cap_rank": 5, "price_change_percentage_24h_in_currency": 3.2}}, None))
    monkeypatch.setattr(coin_page.market_data, "get_market_history", lambda cid, days: (False, {}, "x"))
    monkeypatch.setattr(coin_page.quant_engine, "build_quant_forecast", lambda coin, h, lang: (
        True, {"ceny": [151.5], "aktualna_cena": 150.0, "pasmo": {"dolne": [140.0], "horne": [160.0]}}, None))
    data = client.get("/api/public/coin/sol").json()
    assert data["name"] == "Solana" and data["outlook"][0] == {"horizon": "24h", "price": 151.5, "change_pct": 1.0,
                                                              "low": 140.0, "high": 160.0}
    assert data["signal"] == "bullish" and data["accuracy"] == []
    assert client.get("/api/public/coin/FAKE").status_code == 404


def test_admin_backup(registered, monkeypatch):
    client, username, _p = registered
    assert client.get("/api/admin/backup").status_code == 403
    monkeypatch.setattr(config, "ADMIN_USERNAMES", frozenset({username.lower()}))
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update({"totp_enabled": True})
        db.commit()
    finally:
        db.close()
    res = client.get("/api/admin/backup")
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    data = json.loads(gzip.decompress(res.content))
    assert data["tables"]["users"][0]["username"] == username and "challenge_entries" in data["tables"]


def test_share_card_formats(registered):
    from tests.conftest import signed_forecast_payload
    from PIL import Image
    import io
    client, _u, _p = registered
    entry = client.post("/api/forecast/save", json=signed_forecast_payload(client), headers=csrf_headers(client)).json()
    token = client.post(f"/api/forecast/history/{entry['id']}/share", headers=csrf_headers(client)).json()["share_token"]
    for fmt, size in (("square", (1080, 1080)), ("story", (1080, 1920)), ("wide", (1200, 630))):
        res = client.get(f"/api/public/forecasts/{token}/card.png?fmt={fmt}")
        assert res.status_code == 200 and Image.open(io.BytesIO(res.content)).size == size
    assert client.get(f"/api/public/forecasts/{token}/card.png?fmt=huge").status_code == 422


def test_deleting_account_removes_challenge_entries(registered, prices):
    client, username, password = registered
    db = SessionLocal()
    try:
        challenge.enter(db, db.get(User, _uid(username)), 100.0, MONDAY)
    finally:
        db.close()
    client.post("/api/account/delete", json={"password": password}, headers=csrf_headers(client))
    db = SessionLocal()
    try:
        assert db.query(ChallengeEntry).count() == 0
    finally:
        db.close()
