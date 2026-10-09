"""Premium features: price alerts, morning briefing, personal stats, data export, checkout rules."""

from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import ForecastEvaluation, PriceAlert, User
from tests.conftest import csrf_headers, set_app_settings


def _user(username):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


def _make_premium(username, days=10):
    set_app_settings(premium_mode=True)
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update(
            {"premium_until": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)})
        db.commit()
    finally:
        db.close()


def _alert(client, coin="BTC", direction="above", price=100000.0):
    return client.post("/api/alerts", json={"coin": coin, "direction": direction, "target_price": price},
                       headers=csrf_headers(client))


def test_free_user_gets_one_alert_premium_gets_more(registered):
    client, username, _p = registered
    set_app_settings(premium_mode=True)          # the limits and gates below exist only while Premium is on
    assert _alert(client).status_code == 201
    res = _alert(client, price=90000)
    assert res.status_code == 400 and "najviac 1" in res.json()["detail"]
    _make_premium(username)
    assert _alert(client, price=90000).status_code == 201
    listed = client.get("/api/alerts").json()
    assert listed["active"] == 2 and listed["max"] == 25 and "PEPE" in listed["coins"]


def test_alert_validation_and_ownership(registered):
    client, _u, _p = registered
    assert _alert(client, coin="FAKECOIN").status_code == 400
    assert _alert(client, direction="sideways").status_code == 422
    assert _alert(client, price=-5).status_code == 422
    alert_id = _alert(client).json()["id"]
    client.cookies.clear()
    client.post("/api/auth/register", json={"username": "other1", "password": "TestPass123", "email": "other1@example.com"})
    assert client.delete(f"/api/alerts/{alert_id}", headers=csrf_headers(client)).status_code == 404


def test_alert_fires_once_with_notification_and_email(registered, monkeypatch):
    from app.services import alerts
    client, username, _p = registered
    _alert(client, direction="above", price=100000)
    sent = []
    monkeypatch.setattr(alerts, "is_email_configured", lambda: True)
    monkeypatch.setattr(alerts, "send_email", lambda to, subject, *a: sent.append(subject) or True)
    monkeypatch.setattr(alerts.market_data, "get_live_prices", lambda ids: (True, {"bitcoin": {"usd": 99000.0}}, None))
    db = SessionLocal()
    try:
        assert alerts.check_alerts(db) == 0
        monkeypatch.setattr(alerts.market_data, "get_live_prices", lambda ids: (True, {"bitcoin": {"usd": 101500.0}}, None))
        assert alerts.check_alerts(db) == 1
        assert alerts.check_alerts(db) == 0          # one-shot
        row = db.query(PriceAlert).first()
        assert row.active is False and row.triggered_price == 101500.0
    finally:
        db.close()
    assert sent == ["Alert: BTC is above $100,000"]
    note = client.get("/api/account/notifications").json()["items"][0]
    assert note["kind"] == "price_alert" and note["data"]["price"] == 101500.0


def test_premium_only_endpoints_are_gated(registered):
    client, username, _p = registered
    assert client.get("/api/account/stats").status_code == 200        # Premium off: the paid features are free
    set_app_settings(premium_mode=True)
    res = client.get("/api/account/stats")
    assert res.status_code == 403 and res.json()["detail"] == "Táto funkcia je dostupná v Premium."
    res = client.put("/api/account/preferences", json={"briefing_opt_in": True}, headers=csrf_headers(client))
    assert res.status_code == 403
    _make_premium(username)
    assert client.put("/api/account/preferences", json={"briefing_opt_in": True}, headers=csrf_headers(client)).status_code == 200
    assert client.get("/api/account/membership").json()["briefing_opt_in"] is True


def test_personal_stats(registered):
    client, username, _p = registered
    _make_premium(username)
    uid = _user(username).id
    db = SessionLocal()
    try:
        for i, (provider, coin, ok) in enumerate([("Gemini", "BTC", True), ("Gemini", "ETH", False), ("Claude", "BTC", True)]):
            db.add(ForecastEvaluation(forecast_id=i + 1, user_id=uid, provider=provider, coin=coin, timeframe="24h",
                                      accuracy_pct=96.0, baseline_accuracy_pct=95.0, direction_correct=ok, actual_final_price=1.0))
        db.add(ForecastEvaluation(forecast_id=99, user_id=uid + 1, provider="Gemini", coin="BTC", timeframe="24h",
                                  accuracy_pct=50.0, direction_correct=False, actual_final_price=1.0))
        db.commit()
    finally:
        db.close()
    stats = client.get("/api/account/stats").json()
    assert stats["total_evaluated"] == 3 and stats["direction_hit_pct"] == 66.7
    assert stats["by_provider"][0] == {"key": "Gemini", "evaluated": 2, "direction_hit_pct": 50.0,
                                       "avg_accuracy_pct": 96.0, "beats_baseline_pct": 100.0}
    assert {r["key"] for r in stats["by_coin"]} == {"BTC", "ETH"}


def test_data_export_contains_everything_but_secrets(registered):
    client, _u, _p = registered
    _alert(client)
    res = client.get("/api/account/export")
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    data = res.json()
    assert data["account"]["email"].endswith("@example.com") and len(data["price_alerts"]) == 1
    assert data["account_activity"][0]["action"] == "register"
    text = res.text.lower()
    assert "password" not in text and "totp_secret" not in text and "encrypted_key" not in text


def test_morning_briefing_only_for_premium_subscribers(registered, monkeypatch):
    from app.services import briefing
    client, username, _p = registered
    sent = []
    monkeypatch.setattr(briefing, "is_email_configured", lambda: True)
    monkeypatch.setattr(briefing, "send_email", lambda to, subject, text, html: sent.append((subject, text)) or True)
    monkeypatch.setattr(briefing.quant_engine, "build_quant_forecast", lambda coin, h, lang: (True, {
        "ceny": [101.0, 103.0], "aktualna_cena": 100.0, "pasmo": {"dolne": [98.0, 97.0], "horne": [104.0, 108.0]}}, None))
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update({"briefing_opt_in": True})
        db.commit()
        set_app_settings(premium_mode=True)
        assert briefing.send_morning_briefings(db) == 0          # not Premium
        db.query(User).filter(User.username == username).update(
            {"premium_until": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3)})
        db.commit()
        assert briefing.send_morning_briefings(db) == 1
    finally:
        db.close()
    subject, text = sent[0]
    assert subject == "Your morning crypto briefing" and "BTC: $100.00 → $103.00 (+3.0%)" in text and "ETH" in text


@pytest.fixture()
def stripe_on(monkeypatch):
    from app.services import billing
    monkeypatch.setattr(billing, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID", "price_test")
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    calls = []
    monkeypatch.setattr(billing, "_post", lambda path, data: calls.append((path, data)) or {"url": "https://checkout.stripe.test/s"})
    return calls


def _set(**values):
    set_app_settings(premium_mode=True, **values)


def test_checkout_needs_operator_details_and_consent(registered, stripe_on):
    client, _u, _p = registered
    buy = lambda body: client.post("/api/billing/checkout", json=body, headers=csrf_headers(client))  # noqa: E731
    consent = {"accept_terms": True, "start_immediately": True}
    assert buy(consent).status_code == 503                       # Premium mode off
    _set()
    assert buy(consent).status_code == 503                       # seller identity missing on the Terms page
    assert client.get("/api/public/premium").json()["billing_enabled"] is False
    _set(operator_name="Martin Masaryk", operator_address="Prague, Czech Republic")
    assert client.get("/api/public/premium").json()["billing_enabled"] is True
    assert buy({"accept_terms": True}).status_code == 400
    res = buy(consent)
    assert res.status_code == 200 and res.json()["url"].startswith("https://checkout.stripe.test")
    path, data = stripe_on[-1]
    assert path == "/checkout/sessions" and data["subscription_data[trial_period_days]"] == "7"
    assert data["line_items[0][price]"] == "price_test"
    actions = [e["action"] for e in client.get("/api/account/activity").json()["events"]]
    assert "premium_checkout_consent" in actions


def test_trial_is_given_only_once(registered, stripe_on):
    client, username, _p = registered
    _set(operator_name="M", operator_address="Prague")
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update({"stripe_customer_id": "cus_old"})
        db.commit()
    finally:
        db.close()
    client.post("/api/billing/checkout", json={"accept_terms": True, "start_immediately": True}, headers=csrf_headers(client))
    _path, data = stripe_on[-1]
    assert "subscription_data[trial_period_days]" not in data and data["customer"] == "cus_old"


def test_yearly_plan_uses_yearly_price(registered, stripe_on, monkeypatch):
    from app.services import billing
    client, _u, _p = registered
    _set(operator_name="M", operator_address="Prague")
    body = {"accept_terms": True, "start_immediately": True, "plan": "yearly"}
    client.post("/api/billing/checkout", json=body, headers=csrf_headers(client))
    assert stripe_on[-1][1]["line_items[0][price]"] == "price_test"      # no yearly price configured: monthly
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID_YEARLY", "price_year")
    assert client.get("/api/public/premium").json()["yearly"] is True
    client.post("/api/billing/checkout", json=body, headers=csrf_headers(client))
    assert stripe_on[-1][1]["line_items[0][price]"] == "price_year"
    body["plan"] = "lifetime"
    assert client.post("/api/billing/checkout", json=body, headers=csrf_headers(client)).status_code == 422


def test_webhook_events_apply_once(registered, stripe_on, monkeypatch):
    import json as _json
    import time as _time
    import hashlib
    import hmac
    from app.models import Notification
    client, username, _p = registered
    uid = _user(username).id
    event = {"id": "evt_1", "type": "checkout.session.completed",
             "data": {"object": {"client_reference_id": str(uid), "customer": "cus_1"}}}
    body = _json.dumps(event).encode()
    ts = str(int(_time.time()))
    sig = hmac.new(b"whsec_test", ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    headers = {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}
    assert client.post("/api/billing/webhook", content=body, headers=headers).json() == {"received": True}
    assert client.post("/api/billing/webhook", content=body, headers=headers).json()["duplicate"] is True
    db = SessionLocal()
    try:
        assert db.query(Notification).filter(Notification.user_id == uid, Notification.kind == "premium_started").count() == 1
    finally:
        db.close()


def test_account_deletion_cancels_the_subscription(registered, stripe_on, monkeypatch):
    from app.services import billing
    client, username, password = registered
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update({"stripe_customer_id": "cus_9"})
        db.commit()
    finally:
        db.close()
    calls = []

    def fake_call(method, path, data=None):
        calls.append((method, path))
        if method == "GET":
            return {"data": [{"id": "sub_1", "status": "active"}, {"id": "sub_old", "status": "canceled"}]}
        if fake_call.fail:
            raise billing.BillingError("down")
        return {}
    fake_call.fail = True
    monkeypatch.setattr(billing, "_call", fake_call)
    res = client.post("/api/account/delete", json={"password": password}, headers=csrf_headers(client))
    assert res.status_code == 409 and _user(username) is not None                  # never delete while billing runs
    fake_call.fail = False
    assert client.post("/api/account/delete", json={"password": password}, headers=csrf_headers(client)).status_code == 200
    assert ("DELETE", "/subscriptions/sub_1") in calls and ("DELETE", "/subscriptions/sub_old") not in calls
    assert _user(username) is None


def test_limits_apply_when_premium_ends(registered, monkeypatch):
    from app.services import alerts
    client, username, _p = registered
    _make_premium(username)
    _alert(client, price=1000)
    _alert(client, price=2000)
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update({"premium_until": None})
        db.commit()
        kept = alerts._within_limits(db, db.query(PriceAlert).all())
        assert [a.target_price for a in kept] == [1000.0]                         # free plan: only the oldest one
    finally:
        db.close()


def test_while_premium_is_off_everyone_gets_the_paid_features(registered):
    client, _username, _p = registered
    assert client.get("/api/account/stats").status_code == 200
    assert client.get("/api/positions").status_code == 200
    assert client.get("/api/tools/model-ranking?coin=BTC&horizon=24h").status_code == 200
    res = client.post("/api/alerts", json={"kind": "fear_greed", "coin": "BTC", "direction": "below", "target_price": 20},
                      headers=csrf_headers(client))
    assert res.status_code == 201
    listed = client.get("/api/alerts").json()
    assert listed["max"] == 25
    assert client.get("/api/schedules").json()["max"] == 20
    membership = client.get("/api/account/membership").json()
    assert membership["features"] is True and membership["premium"] is False and membership["enabled"] is False
    # Still nothing about Premium in the session: no crown or "member" flag.
    assert client.get("/api/auth/session").json()["premium"] is False
