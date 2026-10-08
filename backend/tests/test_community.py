"""Notifications, referrals, Premium, tipster board, weekly digest, share cards and the 4h horizon."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import ForecastHistory, JobRun, PriceTip, User
from tests.conftest import anon_csrf_headers, csrf_headers, set_app_settings, signed_forecast_payload

_COMPLETED = {"status": "completed", "accuracy_pct": 97.0, "predicted_prices": [100.0, 110.0],
              "actual_prices": [101.0, 107.0], "time_labels": ["a", "b"], "matures_at": "x",
              "baseline_accuracy_pct": 95.0, "direction_correct": True}


def _db_user(username):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


def _update_user(username, **fields):
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update(fields)
        db.commit()
    finally:
        db.close()


def _register(client, username, ref=None, lang=None):
    client.cookies.clear()
    body = {"username": username, "password": "TestPass123", "email": f"{username}@example.com"}
    if ref:
        body["referral_code"] = ref
    if lang:
        body["lang"] = lang
    res = client.post("/api/auth/register", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _save(client, **kwargs):
    res = client.post("/api/forecast/save", json=signed_forecast_payload(client, **kwargs), headers=csrf_headers(client))
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_evaluation_and_duel_create_notifications(registered, monkeypatch):
    from app.routers import forecast as forecast_router
    client, _u, _p = registered
    entry_id = _save(client, horizon="24h")
    client.post(f"/api/forecast/history/{entry_id}/tip", json={"price": 108}, headers=csrf_headers(client))
    monkeypatch.setattr(forecast_router, "compute_forecast_accuracy", lambda *a, **k: _COMPLETED)
    client.get(f"/api/forecast/history/{entry_id}/accuracy")
    body = client.get("/api/account/notifications").json()
    kinds = {n["kind"]: n["data"] for n in body["items"]}
    assert body["unread"] == 2
    assert kinds["forecast_evaluated"]["coin"] == "BTC" and kinds["forecast_evaluated"]["direction_correct"] is True
    assert kinds["duel_settled"]["outcome"] == "win"
    assert client.post("/api/account/notifications/read", headers=csrf_headers(client)).status_code == 200
    assert client.get("/api/account/notifications").json()["unread"] == 0


def test_notifications_are_private(registered):
    client, _u, _p = registered
    client.cookies.clear()
    assert client.get("/api/account/notifications").status_code == 401


def _paid_invoice(customer, amount, period_end):
    return {"type": "invoice.paid", "data": {"object": {"customer": customer, "amount_paid": amount,
                                                        "lines": {"data": [{"period": {"end": period_end}}]}}}}


def test_invite_link_records_friend_and_badge(client):
    _register(client, "inviter1")
    code = client.get("/api/account/membership").json()["referral_code"]
    assert len(code) == 8
    me = _register(client, "invited1", ref=code)
    assert me["premium"] is False                         # signing up alone gives no Premium
    _register(client, "inviter1b")
    inviter = _db_user("inviter1")
    assert _db_user("invited1").referred_by_id == inviter.id and inviter.premium_until is None
    from app.services.premium import ambassador_badge
    assert [ambassador_badge(n) for n in (0, 1, 4, 5, 10)] == [None, "bronze", "bronze", "silver", "gold"]


def test_unknown_referral_code_is_ignored(client):
    _register(client, "loner1", ref="NOPE1234")
    assert _db_user("loner1").referred_by_id is None


def test_inviter_gets_premium_when_friend_pays(premium_on, monkeypatch):
    from app.services import billing
    client = premium_on
    _register(client, "inviter2")
    code = client.get("/api/account/membership").json()["referral_code"]
    _register(client, "buyer2", ref=code)
    _update_user("buyer2", stripe_customer_id="cus_buyer")
    end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    db = SessionLocal()
    try:
        billing.handle_event(db, _paid_invoice("cus_buyer", 0, end))      # free trial invoice: no reward yet
        assert _db_user("inviter2").premium_until is None
        billing.handle_event(db, _paid_invoice("cus_buyer", 499, end))
        billing.handle_event(db, _paid_invoice("cus_buyer", 499, end))    # second month: rewarded only once
    finally:
        db.close()
    inviter = _db_user("inviter2")
    assert inviter.premium_until > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=29)
    assert inviter.premium_until < datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=31)
    assert _db_user("buyer2").referral_rewarded is True


def test_invited_friend_gets_longer_trial(premium_on):
    from app.services.premium import trial_days_for
    client = premium_on
    _register(client, "host3")
    code = client.get("/api/account/membership").json()["referral_code"]
    _register(client, "guest3", ref=code)
    assert trial_days_for(_db_user("guest3")) == 14 and trial_days_for(_db_user("host3")) == 7
    _update_user("guest3", stripe_customer_id="cus_x")
    assert trial_days_for(_db_user("guest3")) == 0


def test_premium_raises_schedule_limit(registered):
    from app.services.premium import FREE_SCHEDULES, PREMIUM_SCHEDULES
    client, username, _p = registered
    assert client.get("/api/schedules").json()["max"] == FREE_SCHEDULES
    _update_user(username, premium_until=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3))
    assert client.get("/api/schedules").json()["max"] == FREE_SCHEDULES      # Premium mode is off
    set_app_settings(premium_mode=True)
    assert client.get("/api/schedules").json()["max"] == PREMIUM_SCHEDULES


def test_nickname_rules(registered, client):
    c, _u, _p = registered
    put = lambda name: c.put("/api/account/nickname", json={"nickname": name}, headers=csrf_headers(c))  # noqa: E731
    assert put("ab").status_code == 400
    assert put("bad name!").status_code == 400
    assert put("CryptoKing").json() == {"nickname": "CryptoKing"}
    assert put("").json() == {"nickname": None}
    put("CryptoKing")
    _register(c, "second1")
    assert c.put("/api/account/nickname", json={"nickname": "cryptoking"}, headers=csrf_headers(c)).status_code == 400


def test_preferences_and_unsubscribe_link(registered):
    from app.services.digest import unsubscribe_token
    client, username, _p = registered
    res = client.put("/api/account/preferences", json={"digest_opt_in": True, "lang": "sk"}, headers=csrf_headers(client))
    assert res.json() == {"digest_opt_in": True, "lang": "sk", "briefing_opt_in": False}
    uid = _db_user(username).id
    client.cookies.clear()
    headers = anon_csrf_headers(client)
    assert client.post("/api/public/digest/unsubscribe", json={"user_id": uid, "token": "x" * 32}, headers=headers).status_code == 400
    assert client.post("/api/public/digest/unsubscribe", json={"user_id": uid, "token": unsubscribe_token(uid)},
                       headers=headers).status_code == 200
    assert _db_user(username).digest_opt_in is False


def _add_tip(user_id, outcome, forecast_id, days_ago=0, demo=False):
    db = SessionLocal()
    try:
        db.add(PriceTip(user_id=user_id, forecast_id=forecast_id, tip_price=1.0, ai_price=1.0, outcome=outcome,
                        created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago),
                        is_demo=True if demo else None))
        db.commit()
    finally:
        db.close()


def test_tipster_board_shows_only_public_nicknames(client):
    _register(client, "tipper1")
    client.put("/api/account/nickname", json={"nickname": "Ace"}, headers=csrf_headers(client))
    _register(client, "tipper2")
    a, b = _db_user("tipper1").id, _db_user("tipper2").id
    _add_tip(a, "win", 1)
    _add_tip(a, "loss", 2)
    _add_tip(a, "win", 3, days_ago=30)
    _add_tip(a, "win", 4, demo=True)
    _add_tip(b, "win", 5)
    week = client.get("/api/public/tipsters").json()
    assert week["leaders"] == [{"nickname": "Ace", "duels": 2, "wins": 1, "win_pct": 50, "premium": False, "badge": None, "challenge_wins": 0}]
    assert week["humans_vs_ai"]["wins"] == 2 and week["humans_vs_ai"]["losses"] == 1
    assert client.get("/api/public/tipsters?period=all").json()["leaders"][0]["wins"] == 2
    assert client.get("/api/public/tipsters?period=year").status_code == 422


def test_premium_mode_hides_everything_paid(registered):
    client, _u, _p = registered
    set_app_settings(operator_name="Test firm", operator_business_id="TestIČO", operator_address="Test street")
    assert client.get("/api/public/premium").json() == {"enabled": False}
    config = client.get("/api/public/config").json()
    assert config["premium_mode"] is False and config["premium"] == {"enabled": False}
    assert config["operator_name"] == "" and config["operator_business_id"] == "" and config["waitlist_enabled"] is False
    assert client.post("/api/billing/checkout", json={}, headers=csrf_headers(client)).status_code == 503
    set_app_settings(premium_mode=True)
    info = client.get("/api/public/premium").json()
    assert info["enabled"] is True and info["billing_enabled"] is False
    assert info["limits"]["premium"]["schedules"] > info["limits"]["free"]["schedules"]
    assert client.get("/api/public/config").json()["operator_business_id"] == "TestIČO"


def _signed(payload: bytes, secret: str, ts=None):
    ts = str(ts or int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_stripe_signature_verification():
    from app.services.billing import verify_signature
    body = b'{"id": "evt_1"}'
    assert verify_signature(body, _signed(body, "whsec_test"), "whsec_test")
    assert not verify_signature(body, _signed(body, "other"), "whsec_test")
    assert not verify_signature(body + b" ", _signed(body, "whsec_test"), "whsec_test")
    assert not verify_signature(body, _signed(body, "whsec_test", ts=int(time.time()) - 3600), "whsec_test")
    assert not verify_signature(body, None, "whsec_test")


def test_stripe_webhook_activates_premium(registered, monkeypatch):
    from app.services import billing
    client, username, _p = registered
    uid = _db_user(username).id
    monkeypatch.setattr(billing, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(billing, "STRIPE_PRICE_ID", "price_test")
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    events = [
        {"type": "invoice.paid", "data": {"object": {"customer": "cus_1", "parent": {"subscription_details": {
            "metadata": {"user_id": str(uid)}}}, "lines": {"data": [{"period": {"end": period_end}}]}}}},
        {"type": "checkout.session.completed", "data": {"object": {"client_reference_id": str(uid), "customer": "cus_1"}}},
    ]
    for event in events:   # Stripe does not guarantee the order
        body = json.dumps(event).encode()
        res = client.post("/api/billing/webhook", content=body, headers={"stripe-signature": _signed(body, "whsec_test")})
        assert res.status_code == 200, res.text
    user = _db_user(username)
    assert user.stripe_customer_id == "cus_1" and user.premium_until > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=29)
    body = b'{"type": "invoice.paid"}'
    assert client.post("/api/billing/webhook", content=body, headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400


def test_weekly_digest_content_and_language():
    from app.services.digest import render_digest
    user = User(id=7, username="x", lang="sk")
    week = {"total": 12, "hit": 58, "best": {"model": "Gemini", "n": 5, "hit": 80}, "tips_won": 3, "tips_total": 5}
    subject, text, html = render_digest(user, week, {"n": 2, "hits": 1, "won": 1, "lost": 0})
    assert "Tento týždeň" in subject and "12" in text and "Gemini" in html and "unsubscribe?u=7&t=" in text
    assert render_digest(user, {**week, "total": 0, "best": None, "tips_total": 0}, {"n": 0, "hits": 0, "won": 0, "lost": 0}) is None


def test_weekly_digest_sends_only_to_opted_in(registered, monkeypatch):
    from app.services import digest
    client, username, _p = registered
    sent = []
    monkeypatch.setattr(digest, "is_email_configured", lambda: True)
    monkeypatch.setattr(digest, "send_email", lambda to, *a: sent.append(to) or True)
    monkeypatch.setattr(digest, "_week_stats", lambda db, since: {"total": 3, "hit": 66, "best": None, "tips_won": 0, "tips_total": 0})
    db = SessionLocal()
    try:
        assert digest.send_weekly_digests(db) == 0
        db.query(User).filter(User.username == username).update({"digest_opt_in": True})
        db.commit()
        assert digest.send_weekly_digests(db) == 1 and sent == [f"{username}@example.com"]
    finally:
        db.close()


def test_periodic_jobs_run_once_per_slot(client, monkeypatch):
    from app.routers import forecast as forecast_router
    from app.services import alerts, background, briefing, challenge, digest, flips, status_check, tracker
    calls = []
    monkeypatch.setattr(flips, "check_flips", lambda db: calls.append("flips"))
    monkeypatch.setattr(flips, "send_event_reminders", lambda db: calls.append("reminders"))
    monkeypatch.setattr(status_check, "record_sample", lambda db: calls.append("status"))
    monkeypatch.setattr(challenge, "settle_due", lambda db: calls.append("challenge"))
    monkeypatch.setattr(tracker, "take_snapshots", lambda db: calls.append("snap"))
    monkeypatch.setattr(forecast_router, "_evaluate_pending", lambda db, **k: calls.append("eval"))
    monkeypatch.setattr(alerts, "check_alerts", lambda db: calls.append("alerts"))
    monkeypatch.setattr(briefing, "send_morning_briefings", lambda db: calls.append("briefing"))
    monkeypatch.setattr(digest, "send_weekly_digests", lambda db: calls.append("digest"))
    monkeypatch.setattr(background, "_warm_in_background", lambda: calls.append("warm"))
    monday = datetime(2026, 10, 12, 8, 30)
    assert background.run_periodic_jobs(monday) == ["evaluate_forecasts", "price_alerts", "morning_briefing",
                                                 "portfolio_snapshots", "status_history", "direction_flips",
                                                 "event_reminders", "weekly_challenge", "weekly_digest", "warm_signals"]
    assert background.run_periodic_jobs(monday + timedelta(minutes=4)) == []
    assert background.run_periodic_jobs(monday + timedelta(minutes=11)) == ["evaluate_forecasts", "price_alerts",
                                                                            "event_reminders", "warm_signals"]
    wednesday = datetime(2026, 10, 14, 9, 0)
    assert background.run_periodic_jobs(wednesday) == ["evaluate_forecasts", "price_alerts", "morning_briefing",
                                                       "portfolio_snapshots", "status_history", "direction_flips",
                                                       "event_reminders", "warm_signals"]
    assert background.run_periodic_jobs(datetime(2026, 10, 14, 15, 0)) == ["evaluate_forecasts", "price_alerts",
                                                                           "status_history", "direction_flips",
                                                                           "event_reminders", "warm_signals"]
    assert calls.count("digest") == 1 and calls.count("briefing") == 2 and calls.count("snap") == 2
    assert calls.count("challenge") == 1 and calls.count("status") == 3 and calls.count("warm") == 4
    db = SessionLocal()
    try:
        assert {r.name for r in db.query(JobRun).all()} == {"evaluate_forecasts", "price_alerts", "morning_briefing",
                                                  "portfolio_snapshots", "status_history", "weekly_challenge",
                                                  "weekly_digest", "direction_flips", "event_reminders", "warm_signals"}
    finally:
        db.close()


def test_share_and_track_record_cards_are_png(registered):
    client, _u, _p = registered
    entry_id = _save(client)
    token = client.post(f"/api/forecast/history/{entry_id}/share", headers=csrf_headers(client)).json()["share_token"]
    client.cookies.clear()
    for url in (f"/api/public/forecasts/{token}/card.png", "/api/public/track-record/card.png"):
        res = client.get(url)
        assert res.status_code == 200 and res.headers["content-type"] == "image/png" and res.content[:4] == b"\x89PNG"
    assert client.get("/api/public/forecasts/" + "x" * 20 + "/card.png").status_code == 404


def test_four_hour_horizon_and_new_coins(registered):
    from app.config import DEFAULT_COIN_IDS, HORIZON_HOURS, MOCK_BASE_PRICES, SUPPORTED_COINS, TIME_HORIZONS
    assert set(SUPPORTED_COINS) == set(DEFAULT_COIN_IDS) == set(MOCK_BASE_PRICES)
    assert set(TIME_HORIZONS) == set(HORIZON_HOURS) and HORIZON_HOURS["4h"] == 4
    client, _u, _p = registered
    entry_id = _save(client, coin="PEPE", horizon="4h", prices=(0.0000101, 0.0000099))
    db = SessionLocal()
    try:
        row = db.get(ForecastHistory, entry_id)
        assert row.timeframe == "4h" and row.crypto_symbol == "PEPE"
    finally:
        db.close()


def test_mock_forecast_keeps_micro_prices():
    from app.services.ai_engine import _generate_mock_forecast
    data = _generate_mock_forecast("PEPE", "4h", "en")
    assert len(data["ceny"]) == 4 and all(p > 0 for p in data["ceny"])


def test_emails_follow_user_language(client, monkeypatch):
    from app.services import verification
    from app.routers import auth
    sent = []
    monkeypatch.setattr(auth, "is_email_configured", lambda: True)
    monkeypatch.setattr(verification, "send_email", lambda to, subject, *a: sent.append(subject) or True)
    _register(client, "czech1", lang="cs")
    _register(client, "english1")
    assert sent == ["Ověř si e-mail — AI Crypto Analytics", "Verify your email — AI Crypto Analytics"]
