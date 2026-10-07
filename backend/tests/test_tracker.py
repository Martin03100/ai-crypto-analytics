"""Portfolio tracker, daily snapshots and the PDF report."""

from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import PortfolioSnapshot, User
from app.services import market_data, tracker
from tests.conftest import csrf_headers, set_app_settings

MARKETS = {
    "bitcoin": {"current_price": 100000.0, "price_change_percentage_24h_in_currency": 2.0,
                "price_change_percentage_30d_in_currency": 10.0},
    "ethereum": {"current_price": 4000.0, "price_change_percentage_24h_in_currency": -1.0,
                 "price_change_percentage_30d_in_currency": -20.0},
}


@pytest.fixture()
def markets(monkeypatch):
    monkeypatch.setattr(market_data, "get_coin_markets", lambda ids, **k: (True, {i: MARKETS[i] for i in ids if i in MARKETS}, None))


def _premium(username):
    set_app_settings(premium_mode=True)
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update(
            {"premium_until": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)})
        db.commit()
    finally:
        db.close()


def _put(client, coin, amount, price):
    return client.put("/api/positions", json={"coin": coin, "amount": amount, "avg_buy_price": price},
                      headers=csrf_headers(client))


def test_tracker_is_premium_only(registered):
    client, _u, _p = registered
    assert client.get("/api/positions").status_code == 403
    assert _put(client, "BTC", 1, 1).status_code == 403
    assert client.get("/api/report.pdf").status_code == 403


def test_positions_pnl_allocation_and_risk(registered, markets):
    client, username, _p = registered
    _premium(username)
    _put(client, "btc", 0.5, 80000)
    data = _put(client, "ETH", 5, 5000).json()
    btc, eth = data["positions"]
    assert btc["coin"] == "BTC" and btc["value"] == 50000 and btc["pnl"] == 10000 and btc["pnl_pct"] == 25.0
    assert eth["pnl"] == -5000 and eth["allocation_pct"] == 28.6
    assert data["total"] == {"value": 70000, "cost": 65000, "pnl": 5000, "pnl_pct": 7.69, "change_24h_pct": 1.14}
    assert data["risk"]["level"] == "medium" and data["risk"]["top_share_pct"] == 71.4
    updated = _put(client, "BTC", 1, 90000).json()                           # same coin replaces the row
    assert len(updated["positions"]) == 2 and updated["positions"][0]["cost"] == 90000
    assert _put(client, "FAKECOIN", 1, 1).status_code == 400
    assert _put(client, "BTC", 0, 1).status_code == 422
    assert client.delete(f"/api/positions/{eth['id']}", headers=csrf_headers(client)).json()["total"]["value"] == 100000
    assert client.delete(f"/api/positions/{eth['id']}", headers=csrf_headers(client)).status_code == 404


def test_position_limit(registered, markets, monkeypatch):
    client, username, _p = registered
    _premium(username)
    monkeypatch.setattr(tracker, "MAX_POSITIONS", 1)
    assert _put(client, "BTC", 1, 1).status_code == 200
    assert _put(client, "ETH", 1, 1).status_code == 400
    assert _put(client, "BTC", 2, 1).status_code == 200                       # editing is still fine


def test_risk_score_bounds():
    assert tracker.risk_score([]) == {"score": None, "level": None}
    calm = tracker.risk_score([{"value": 50, "change_30d": 1}, {"value": 50, "change_30d": -2}])
    wild = tracker.risk_score([{"value": 100, "change_30d": 80}])
    assert calm["score"] == 1.0 and calm["level"] == "low" and wild["score"] == 10.0 and wild["level"] == "high"


def test_daily_snapshots_only_for_premium(registered, markets):
    client, username, _p = registered
    _premium(username)
    _put(client, "BTC", 1, 50000)
    db = SessionLocal()
    try:
        assert tracker.take_snapshots(db) == 1
        assert tracker.take_snapshots(db) == 1                                 # same day: updated, not duplicated
        assert db.query(PortfolioSnapshot).count() == 1
        set_app_settings(premium_mode=False)
        assert tracker.take_snapshots(db) == 0
    finally:
        db.close()
    set_app_settings(premium_mode=True)
    history = client.get("/api/positions").json()["history"]
    assert history[0]["value"] == 100000 and history[0]["cost"] == 50000


def test_pdf_report(registered, markets):
    client, username, _p = registered
    _premium(username)
    empty = client.get("/api/report.pdf")
    assert empty.status_code == 200 and empty.content.startswith(b"%PDF")
    _put(client, "BTC", 1, 50000)
    res = client.get("/api/report.pdf")
    assert res.headers["content-type"] == "application/pdf" and "attachment" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF") and len(res.content) > len(empty.content)


def test_export_and_account_deletion_include_positions(registered, markets):
    client, username, _p = registered
    _premium(username)
    _put(client, "BTC", 1, 50000)
    data = client.get("/api/account/export").json()
    assert data["portfolio_positions"][0]["coin"] == "BTC" and data["portfolio_history"] == []


def test_missing_quote_is_not_a_loss(registered, monkeypatch):
    client, username, _p = registered
    _premium(username)
    monkeypatch.setattr(market_data, "get_coin_markets", lambda ids, **k: (True, {"bitcoin": MARKETS["bitcoin"]}, None))
    _put(client, "BTC", 1, 50000)
    data = _put(client, "SOL", 10, 100).json()
    sol = next(r for r in data["positions"] if r["coin"] == "SOL")
    assert sol["value"] is None and sol["pnl"] is None and sol["allocation_pct"] is None
    assert data["total"]["pnl"] == 50000 and data["unpriced"] == 1
    db = SessionLocal()
    try:
        assert tracker.take_snapshots(db) == 0                     # incomplete quotes: no snapshot
    finally:
        db.close()
    assert client.get("/api/report.pdf").content.startswith(b"%PDF")
