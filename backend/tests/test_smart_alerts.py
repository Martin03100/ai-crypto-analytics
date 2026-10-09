"""Smart alerts (24h move, RSI, Fear & Greed) and Telegram delivery."""

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import PriceAlert, User
from app.services import alerts, telegram
from tests.conftest import csrf_headers, set_app_settings


def _premium(username):
    set_app_settings(premium_mode=True, free_alerts=5)
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update(
            {"premium_until": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)})
        db.commit()
    finally:
        db.close()


def _create(client, **body):
    base = {"kind": "price", "coin": "BTC", "direction": "above", "target_price": 100}
    return client.post("/api/alerts", json={**base, **body}, headers=csrf_headers(client))


def test_alert_kinds_validation_and_premium_kinds(registered):
    client, username, _p = registered
    set_app_settings(premium_mode=True)          # the limits and gates below exist only while Premium is on
    assert _create(client, kind="move", target_price=0.1).status_code == 400          # below 0.5 %
    assert _create(client, kind="rsi", target_price=150).status_code == 400
    assert _create(client, kind="fear_greed", target_price=20, direction="below").status_code == 403
    assert _create(client, kind="volume").status_code == 422
    set_app_settings(free_alerts=3)
    assert _create(client, kind="move", target_price=5).status_code == 201
    assert _create(client, kind="rsi", target_price=70).status_code == 201
    _premium(username)
    res = _create(client, kind="fear_greed", coin="BTC", target_price=20, direction="below")
    assert res.status_code == 201 and res.json()["coin"] == "ALL"
    assert client.get("/api/alerts").json()["premium_kinds"] == ["fear_greed"]


def _add(user_id, kind, coin, direction, target):
    db = SessionLocal()
    try:
        db.add(PriceAlert(user_id=user_id, kind=kind, coin=coin, direction=direction, target_price=target))
        db.commit()
    finally:
        db.close()


def test_smart_alerts_fire_on_their_own_signal(registered, monkeypatch):
    client, username, _p = registered
    _premium(username)
    uid = SessionLocal().query(User).filter(User.username == username).first().id
    _add(uid, "move", "BTC", "below", 5)        # fires on a 24h drop of 5 % or more
    _add(uid, "move", "ETH", "above", 5)        # +5 % or more: not reached
    _add(uid, "rsi", "SOL", "above", 70)
    _add(uid, "fear_greed", "ALL", "below", 20)
    monkeypatch.setattr(alerts.market_data, "get_live_prices", lambda ids: (True, {
        "bitcoin": {"usd": 60000.0, "usd_24h_change": -6.2}, "ethereum": {"usd": 3000.0, "usd_24h_change": 3.0}}, None))
    day = 86_400_000
    monkeypatch.setattr(alerts.market_data, "get_market_history",
                        lambda coin_id, days: (True, {"prices": [[i * day, 100 + i] for i in range(20)]}, None))
    monkeypatch.setattr(alerts.market_data, "get_fear_greed_index", lambda: (True, {"value": 15}, None))
    sent = []
    monkeypatch.setattr(alerts.telegram, "send", lambda chat, text: sent.append(text) or True)
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == uid).update({"telegram_chat_id": "123"})
        db.commit()
        assert alerts.check_alerts(db) == 3
        assert {(a.kind, a.coin) for a in db.query(PriceAlert).filter(PriceAlert.active.is_(True)).all()} == {("move", "ETH")}
    finally:
        db.close()
    assert "🔔 Alert: BTC moved -6.2% in 24 hours" in sent and "🔔 Alert: Fear & Greed index is 15" in sent
    kinds = {n["data"]["alert_kind"] for n in client.get("/api/account/notifications").json()["items"]}
    assert kinds == {"move", "rsi", "fear_greed"}


def test_premium_kind_waits_when_premium_ends(registered, monkeypatch):
    _client, username, _p = registered
    set_app_settings(premium_mode=True)          # the limits and gates below exist only while Premium is on
    uid = SessionLocal().query(User).filter(User.username == username).first().id
    _add(uid, "fear_greed", "ALL", "below", 20)
    monkeypatch.setattr(alerts.market_data, "get_fear_greed_index", lambda: (True, {"value": 10}, None))
    db = SessionLocal()
    try:
        assert alerts.check_alerts(db) == 0 and db.query(PriceAlert).first().active is True
    finally:
        db.close()


def test_telegram_linking_flow(registered, monkeypatch):
    client, username, _p = registered
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_USERNAME", "AcaBot")
    set_app_settings(premium_mode=True)          # the limits and gates below exist only while Premium is on
    assert client.post("/api/account/telegram/link", headers=csrf_headers(client)).status_code == 403   # not Premium
    _premium(username)
    url = client.post("/api/account/telegram/link", headers=csrf_headers(client)).json()["url"]
    assert url.startswith("https://t.me/AcaBot?start=")
    code = url.split("=")[1]
    replies = []
    monkeypatch.setattr(telegram, "_api", lambda method, payload: replies.append((method, payload)) or (
        {"ok": True, "result": [{"update_id": 7, "message": {"chat": {"id": 555}, "text": f"/start {code}"}},
                                {"update_id": 8, "message": {"chat": {"id": 556}, "text": "/start wrongcode"}}]}
        if method == "getUpdates" else {"ok": True}))
    db = SessionLocal()
    try:
        assert telegram.poll_updates(db) == 2
        user = db.query(User).filter(User.username == username).first()
        assert user.telegram_chat_id == "555" and user.telegram_link_code is None
        assert telegram.handle_message(db, "555", "/stop") == "stopped"
        db.refresh(user)
        assert user.telegram_chat_id is None
    finally:
        db.close()
    sends = [p["text"] for m, p in replies if m == "sendMessage"]
    assert sends[0].startswith("✅ Connected") and "expired" in sends[1]
    assert client.get("/api/account/membership").json()["telegram"] == {"available": True, "linked": False}
    assert telegram.poll_updates.__doc__


def test_telegram_offset_is_remembered(client, monkeypatch):
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_USERNAME", "AcaBot")
    offsets = []
    monkeypatch.setattr(telegram, "_api", lambda method, payload: offsets.append(payload.get("offset")) or (
        {"ok": True, "result": [{"update_id": 41, "message": {}}]} if method == "getUpdates" else {"ok": True}))
    db = SessionLocal()
    try:
        telegram.poll_updates(db)
        telegram.poll_updates(db)
    finally:
        db.close()
    assert offsets == [0, 42]


def test_telegram_errors_never_log_the_bot_token(monkeypatch, caplog):
    import requests
    from app.services import telegram
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "123:SECRET")
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_USERNAME", "acabot")

    def boom(url, **kwargs):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")
    monkeypatch.setattr(telegram.requests, "post", boom)
    assert telegram.send("42", "hi") is False
    assert "SECRET" not in caplog.text
