"""Tipster profiles, accuracy timeline, weekly recap, calendar + reminders, direction flips, Web Push,
"what if", CSV export, beginner view and feedback."""

import csv
import io
import json
import math
from datetime import datetime, timedelta

import pytest
from PIL import Image

from app import config
from app.database import SessionLocal
from app.models import (Challenge, ChallengeEntry, CoinSignalState, EventReminder, Feedback, ForecastEvaluation,
                        ForecastHistory, Notification, PriceTip, PushSubscription, User)
from app.routers import extras
from app.services import event_calendar, flips, profiles, push, whatif
from tests.conftest import anon_csrf_headers, csrf_headers

NOW = datetime(2026, 10, 8, 12, 0)
FCM = "https://fcm.googleapis.com/fcm/send/abcdefghijklmnopqrstuvwxyz"
KEYS = {"p256dh": "BElongpublickeyvalue1234567890abcdefghij", "auth": "authsecret123456"}


def _db():
    return SessionLocal()


def _user(username):
    db = _db()
    try:
        return db.query(User).filter(User.username == username).one()
    finally:
        db.close()


def _set(username, **values):
    db = _db()
    try:
        db.query(User).filter(User.username == username).update(values)
        db.commit()
    finally:
        db.close()


# ---------- calendar ----------

def test_calendar_macro_and_options_without_network():
    data = event_calendar.upcoming(60, NOW, network=False)
    kinds = [e["kind"] for e in data["events"]]
    assert kinds[:3] == ["cpi", "fomc", "options_monthly"]
    cpi = data["events"][0]
    assert cpi["id"] == "cpi-20261014" and cpi["at"] == "2026-10-14T12:30:00Z"      # 08:30 New York, summer time
    nov = next(e for e in data["events"] if e["id"] == "cpi-20261110")
    assert nov["at"] == "2026-11-10T13:30:00Z"                                        # winter time
    assert event_calendar.last_friday(2026, 12).isoformat() == "2026-12-25"
    q = event_calendar.option_expiries(NOW.date(), months=4)
    assert [e["kind"] for e in q] == ["options_monthly", "options_monthly", "options_quarterly", "options_monthly"]


def test_halving_and_unlock_detection(monkeypatch):
    event_calendar._cache.clear()
    monkeypatch.setattr(event_calendar, "block_height", lambda: 1_049_856)        # 144 blocks = one day
    halving = event_calendar.halving_event(NOW)
    assert halving["estimated"] and halving["at"].startswith("2026-10-09") and halving["blocks_left"] == 144
    day = (NOW.date() - datetime(1970, 1, 1).date()).days

    def pts(values):
        return [{"timestamp": (day + i) * 86400, "unlocked": v} for i, v in enumerate(values)]
    data = {"documentedData": {"data": [{"label": "Team", "data": pts([1000, 1000, 1000, 1030, 1030])},
                                        {"label": "Ecosystem", "data": pts([500, 501, 502, 503, 504])}]}}
    events = event_calendar.unlocks_from_series("SUI", data, NOW.date())
    assert len(events) == 1 and events[0]["coin"] == "SUI" and events[0]["amount"] == 31
    assert events[0]["id"].endswith("-sui") and events[0]["share_pct"] == pytest.approx(2.07, abs=0.01)
    assert event_calendar.unlocks_from_series("SUI", {"bad": 1}, NOW.date()) == []


def test_calendar_endpoint_and_reminders(registered, monkeypatch):
    client, username, _p = registered
    monkeypatch.setattr(event_calendar, "token_unlocks", lambda today: [])
    monkeypatch.setattr(event_calendar, "halving_event", lambda now: None)
    data = client.get("/api/public/calendar?days=120").json()
    assert data["events"] and all(e["category"] in ("macro", "crypto", "unlock") for e in data["events"])
    event = data["events"][0]
    h = csrf_headers(client)
    assert client.post("/api/calendar/reminders", json={"event_id": "fomc-19990101"}, headers=h).status_code == 404
    assert client.post("/api/calendar/reminders", json={"event_id": "x;drop"}, headers=h).status_code == 422
    assert client.post("/api/calendar/reminders", json={"event_id": event["id"]}, headers=h).status_code == 201
    assert client.post("/api/calendar/reminders", json={"event_id": event["id"]}, headers=h).status_code == 201
    assert client.get("/api/calendar/reminders").json()["event_ids"] == [event["id"]]

    at = event_calendar.event_at(event)
    db = _db()
    try:
        assert flips.send_event_reminders(db, now=at - timedelta(hours=3)) == 0
        assert flips.send_event_reminders(db, now=at - timedelta(minutes=30)) == 1
        assert flips.send_event_reminders(db, now=at - timedelta(minutes=20)) == 0          # only once
        note = db.query(Notification).filter(Notification.kind == "event_reminder").one()
        assert json.loads(note.data_json)["title_key"] == event["kind"]
    finally:
        db.close()
    assert client.get("/api/calendar/reminders").json()["event_ids"] == []
    assert client.delete(f"/api/calendar/reminders/{event['id']}", headers=h).status_code == 200


# ---------- direction flips ----------

def test_direction_flips_notify_watchers_once(registered):
    _client, username, _p = registered
    _set(username, watchlist_json=json.dumps(["BTC", "ETH"]))
    changes = {"BTC": 1.2, "ETH": 0.1}
    db = _db()
    try:
        assert flips.check_flips(db, change_for=changes.get, now=NOW) == 0               # first look: no history
        changes["BTC"] = 0.1                                                             # flat: no change of mind
        assert flips.check_flips(db, change_for=changes.get, now=NOW + timedelta(hours=3)) == 0
        changes["BTC"] = -1.5                                                            # up -> down
        assert flips.check_flips(db, change_for=changes.get, now=NOW + timedelta(hours=6)) == 1
        changes["BTC"] = 2.0                                                             # back up within cooldown
        assert flips.check_flips(db, change_for=changes.get, now=NOW + timedelta(hours=9)) == 0
        assert flips.check_flips(db, change_for=changes.get, now=NOW + timedelta(hours=18)) == 1   # it lasted
        changes["BTC"] = 2.5                                                             # same view: nothing new
        assert flips.check_flips(db, change_for=changes.get, now=NOW + timedelta(hours=21)) == 0
        state = db.get(CoinSignalState, "BTC")
        assert state.direction == "up" and state.last_trend == "up"
        notes = db.query(Notification).filter(Notification.kind == "direction_flip").all()
        assert [json.loads(n.data_json)["direction"] for n in notes] == ["down", "up"]
        changes["BTC"] = -3.0                                                            # unwatched for days: re-seed
        assert flips.check_flips(db, change_for=changes.get, now=NOW + timedelta(days=5)) == 0
    finally:
        db.close()
    _set(username, notify_prefs_json=json.dumps({"flips": False}))
    changes["BTC"] = 3.0
    db = _db()
    try:
        assert flips.check_flips(db, change_for=changes.get, now=NOW + timedelta(days=5, hours=13)) == 0
        assert db.query(Notification).filter(Notification.kind == "direction_flip").count() == 2
    finally:
        db.close()


# ---------- web push ----------

def test_push_subscribe_validation_prefs_and_delivery(registered, monkeypatch):
    client, username, _p = registered
    key = client.get("/api/push/key").json()["key"]
    assert len(key) > 80 and key == push.public_key()
    h = csrf_headers(client)
    for bad in ("http://fcm.googleapis.com/x/abcdefghijklmnop", "https://evil.example.com/fcm.googleapis.com/abc",
                "https://fcm.googleapis.com.evil.com/abcdefghijk", "https://169.254.169.254/latest/meta-data/xx"):
        assert client.post("/api/push/subscribe", json={"endpoint": bad, "keys": KEYS}, headers=h).status_code == 400
    assert extras.valid_push_endpoint("https://wns2-par02p.notify.windows.com/w/?token=abc")
    assert extras.valid_push_endpoint("https://web.push.apple.com/QWERTY")
    res = client.post("/api/push/subscribe", json={"endpoint": FCM, "keys": KEYS}, headers=h)
    assert res.status_code == 201 and res.json()["devices"] == 1
    assert client.get("/api/account/notify-prefs").json() == {"prefs": {c: True for c in push.CATEGORIES}, "devices": 1}

    sent = []
    monkeypatch.setattr(push, "send", lambda sub, payload: sent.append(payload) or 201)
    uid = _user(username).id
    db = _db()
    try:
        from app.services.notifications import notify
        notify(db, uid, "direction_flip", coin="SOL", direction="up", change_pct=1.0)
        notify(db, uid, "referral_reward", days=30)                    # not a push category
        db.commit()
    finally:
        db.close()
    assert len(sent) == 1 and sent[0]["title"] == "The AI turned bullish on SOL" and sent[0]["url"] == "/forecast?coin=SOL"

    assert client.put("/api/account/notify-prefs", json={"flips": False}, headers=h).json()["prefs"]["flips"] is False
    db = _db()
    try:
        notify(db, uid, "direction_flip", coin="SOL", direction="down", change_pct=-1.0)
        db.rollback()                                                  # rolled back: nothing is sent
        notify(db, uid, "direction_flip", coin="SOL", direction="down", change_pct=-1.0)
        db.commit()                                                    # category switched off
    finally:
        db.close()
    assert len(sent) == 1

    monkeypatch.setattr(push, "send", lambda sub, payload: 410)        # browser dropped the subscription
    db = _db()
    try:
        notify(db, uid, "price_alert", coin="BTC", direction="above", price=1)
        db.commit()
        assert db.query(PushSubscription).count() == 0
    finally:
        db.close()
    assert client.post("/api/push/test", headers=h).status_code == 400


def test_push_message_languages():
    msg = push.message("event_reminder", {"title_key": "unlock", "coin": "SUI"}, "de")
    assert msg["title"] == "Beginnt in weniger als einer Stunde: Token-Unlock SUI" and msg["url"] == "/calendar"
    assert push.message("price_alert", {"coin": "BTC"}, "pl")["title"].startswith("BTC")
    assert push.message("premium_started", {}, "en") is None


# ---------- profiles, timeline, weekly recap ----------

def _seed_tips(username):
    uid = _user(username).id
    db = _db()
    try:
        for i, outcome in enumerate(["win", "win", "loss", "win"]):
            f = ForecastHistory(user_id=uid, crypto_symbol="ETH", timeframe="24h", model_used="Gemini",
                                forecast_json="{}", created_at=NOW - timedelta(days=4 - i))
            db.add(f)
            db.flush()
            db.add(PriceTip(user_id=uid, forecast_id=f.id, tip_price=100 + i, ai_price=99, outcome=outcome,
                            created_at=NOW - timedelta(days=4 - i)))
            db.add(ForecastEvaluation(forecast_id=f.id, user_id=uid, provider="Gemini", coin="ETH", timeframe="24h",
                                      accuracy_pct=90 + i, direction_correct=outcome == "win", actual_final_price=101,
                                      evaluated_at=NOW - timedelta(days=4 - i)))
        db.add(Challenge(week="2026-W40", coin="SOL", start_price=100, ai_price=103, end_price=110, winner_user_id=uid))
        db.add(ChallengeEntry(week="2026-W40", user_id=uid, price=109, week_user=f"2026-W40:{uid}"))
        db.commit()
    finally:
        db.close()


def test_tipster_profile(registered):
    client, username, _p = registered
    _seed_tips(username)
    assert client.get("/api/public/tipsters/nobody").status_code == 404
    assert client.get(f"/api/public/tipsters/{username}").status_code == 404           # no public nickname yet
    _set(username, nickname="CryptoMaster")
    p = client.get("/api/public/tipsters/cryptomaster").json()
    assert p["nickname"] == "CryptoMaster" and p["duels"]["total"] == 4 and p["duels"]["win"] == 3
    assert p["duels"]["win_pct"] == 75 and p["duels"]["streak"] == 1
    assert p["recent"][0]["coin"] == "ETH" and p["recent"][0]["actual"] == 101
    assert p["challenge"]["wins"] == 1 and p["challenge"]["rounds"][0]["error_pct"] == pytest.approx(0.91, abs=0.01)
    assert "email" not in json.dumps(p) and "username" not in p
    _set(username, disabled=True)
    assert client.get("/api/public/tipsters/cryptomaster").status_code == 404


def test_timeline_weekly_summary_and_card(registered):
    client, username, _p = registered
    _seed_tips(username)
    _set(username, nickname="Ace")
    db = _db()
    try:
        tl = profiles.timeline(db, now=NOW)
        assert len(tl["weeks"]) == 12 and tl["weeks"][-1] == "2026-W41"
        gem = tl["providers"][0]
        assert gem["provider"] == "Gemini" and gem["n"] == 4
        summary = profiles.weekly_summary(db, now=NOW)
    finally:
        db.close()
    assert summary["forecasts"] == 4 and summary["hit_pct"] == 75.0
    assert summary["humans_vs_ai"]["wins"] == 3 and summary["challenge"]["winner"] == "Ace"
    assert summary["best"]["accuracy_pct"] == 93.0
    assert client.get("/api/public/accuracy-timeline").status_code == 200
    for fmt, size in (("square", (1080, 1080)), ("story", (1080, 1920))):
        res = client.get(f"/api/public/weekly-summary/card.png?fmt={fmt}")
        assert res.status_code == 200 and Image.open(io.BytesIO(res.content)).size == size
    assert client.get("/api/public/weekly-summary/card.png?fmt=huge").status_code == 422


# ---------- what if ----------

def _series(days, daily_return):
    start = datetime(2026, 1, 1)
    return [[(start + timedelta(days=i)).timestamp() * 1000, 100 * math.exp(daily_return * i)] for i in range(days)]


def test_what_if_follows_trend_and_counts_fees():
    up = whatif.simulate(_series(120, 0.01), 30, 1000)
    assert up["signal_today"] == "up" and up["strategy"]["trades"] == 1 and up["strategy"]["exposure_pct"] == 100
    assert up["hold"]["return_pct"] == pytest.approx((math.exp(0.3) - 1) * 100, abs=0.1)
    assert up["strategy"]["final"] == pytest.approx(up["hold"]["final"] * 0.999, rel=1e-3)
    down = whatif.simulate(_series(120, -0.01), 30, 1000)
    assert down["strategy"]["final"] == 1000 and down["hold"]["return_pct"] < -20 and down["strategy"]["trades"] == 0
    assert down["hold"]["max_drawdown_pct"] < -20 and len(down["curve"]) == 31
    assert whatif.simulate(_series(40, 0.01), 30, 1000) is None


def test_what_if_endpoint(registered, monkeypatch):
    client, _u, _p = registered
    monkeypatch.setattr(whatif.market_data, "get_market_chart", lambda *a, **k: (True, _series(200, 0.002), None))
    whatif._cache.clear()
    res = client.get("/api/tools/what-if?coin=btc&days=90&amount=500")
    assert res.status_code == 200 and res.json()["coin"] == "BTC" and res.json()["amount"] == 500
    assert client.get("/api/tools/what-if?coin=XYZ&days=30").status_code == 400
    assert client.get("/api/tools/what-if?coin=BTC&days=45").status_code == 400


# ---------- CSV export ----------

def test_csv_export_is_spreadsheet_safe(registered):
    client, username, _p = registered
    _seed_tips(username)
    h = csrf_headers(client)
    client.post("/api/alerts", json={"coin": "BTC", "direction": "above", "target_price": 1000000, "kind": "price"}, headers=h)
    res = client.get("/api/account/export/tips.csv")
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(res.content.decode("utf-8-sig"))))
    assert rows[0][:3] == ["forecast_id", "created_at", "coin"] and len(rows) == 5
    for kind in extras.EXPORT_KINDS:
        assert client.get(f"/api/account/export/{kind}.csv").status_code == 200
    assert client.get("/api/account/export/users.csv").status_code == 422
    assert extras._cell("=HYPERLINK(1)") == "'=HYPERLINK(1)" and extras._cell(-5) == -5 and extras._cell(None) == ""


# ---------- beginner view ----------

def test_simple_mode_is_part_of_the_session(registered):
    client, _u, _p = registered
    assert client.get("/api/auth/me").json()["simple_mode"] is None
    assert client.put("/api/account/ui-mode", json={"simple_mode": True}, headers=csrf_headers(client)).status_code == 200
    assert client.get("/api/auth/me").json()["simple_mode"] is True


# ---------- feedback ----------

def test_feedback_anonymous_honeypot_and_admin(client, monkeypatch):
    h = anon_csrf_headers(client)
    assert client.post("/api/feedback", json={"kind": "bug", "message": "Chart is blank on iPhone",
                                              "page": "/dashboard?x=1"}, headers=h).status_code == 201
    assert client.post("/api/feedback", json={"kind": "idea", "message": "buy cheap pills", "website": "spam.example"},
                       headers=h).status_code == 201
    assert client.post("/api/feedback", json={"kind": "bug", "message": "x"}, headers=h).status_code == 422
    db = _db()
    try:
        rows = db.query(Feedback).all()
        assert len(rows) == 1 and rows[0].page == "/dashboard" and rows[0].user_id is None
    finally:
        db.close()
    res = client.post("/api/auth/register", json={"username": "boss1", "password": "TestPass123", "email": "b@example.com"})
    assert res.status_code == 201
    assert client.get("/api/admin/feedback").status_code == 403
    monkeypatch.setattr(config, "ADMIN_USERNAMES", frozenset({"boss1"}))
    _set("boss1", totp_enabled=True)
    items = client.get("/api/admin/feedback").json()
    assert items["new"] == 1 and items["items"][0]["message"] == "Chart is blank on iPhone"
    fid = items["items"][0]["id"]
    h = csrf_headers(client)
    assert client.patch(f"/api/admin/feedback/{fid}", json={"status": "done"}, headers=h).json()["status"] == "done"
    assert client.get("/api/admin/feedback").json()["new"] == 0
    assert client.delete(f"/api/admin/feedback/{fid}", headers=h).status_code == 200


def test_account_delete_removes_new_data(registered):
    client, username, password = registered
    uid = _user(username).id
    db = _db()
    try:
        db.add(EventReminder(user_id=uid, event_id="fomc-20261028", event_at=NOW, title_key="fomc"))
        db.add(PushSubscription(user_id=uid, endpoint=FCM, p256dh=KEYS["p256dh"], auth=KEYS["auth"]))
        db.add(Feedback(user_id=uid, kind="idea", message="More coins please"))
        db.commit()
    finally:
        db.close()
    export = client.get("/api/account/export").json()
    assert export["calendar_reminders"] and export["browser_notification_devices"] and export["feedback_sent"]
    res = client.post("/api/account/delete", json={"password": password}, headers=csrf_headers(client))
    assert res.status_code in (200, 204), res.text
    db = _db()
    try:
        assert db.query(EventReminder).count() == 0 and db.query(PushSubscription).count() == 0
        assert db.query(Feedback).one().user_id is None
    finally:
        db.close()
