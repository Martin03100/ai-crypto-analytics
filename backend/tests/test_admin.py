"""Admin role, admin API, feature switches and blocked accounts."""

from datetime import datetime, timedelta, timezone

import pytest

from app import config
from app.database import SessionLocal
from app.models import User, WaitlistEntry
from tests.conftest import anon_csrf_headers, csrf_headers


def _update(username, **fields):
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update(fields)
        db.commit()
    finally:
        db.close()


def _get(username):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


@pytest.fixture()
def admin(registered, monkeypatch):
    client, username, password = registered
    monkeypatch.setattr(config, "ADMIN_USERNAMES", frozenset({username.lower()}))
    _update(username, totp_enabled=True)
    return client, username


@pytest.fixture()
def other():
    """A second browser, so the admin session (with 2FA) stays signed in."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def _register(client, username):
    client.cookies.clear()
    res = client.post("/api/auth/register", json={"username": username, "password": "TestPass123",
                                                   "email": f"{username}@example.com"})
    assert res.status_code == 201, res.text
    return res


def test_regular_user_cannot_use_admin_api(registered):
    client, _u, _p = registered
    assert client.get("/api/auth/me").json()["admin"] is False
    for method, url in (("get", "/api/admin/stats"), ("get", "/api/admin/users"), ("get", "/api/admin/settings"),
                        ("get", "/api/admin/waitlist.csv")):
        assert getattr(client, method)(url).status_code == 403
    assert client.put("/api/admin/settings", json={"values": {"chat_enabled": False}},
                      headers=csrf_headers(client)).status_code == 403


def test_admin_needs_two_factor(registered, monkeypatch):
    client, username, _p = registered
    monkeypatch.setattr(config, "ADMIN_USERNAMES", frozenset({username.lower()}))
    assert client.get("/api/auth/me").json()["admin"] is True
    res = client.get("/api/admin/stats")
    assert res.status_code == 403 and "2FA" in res.json()["detail"]


def test_admin_stats_and_user_search(admin):
    client, username = admin
    stats = client.get("/api/admin/stats").json()
    assert stats["users"] == 1 and stats["premium"] == 0 and stats["billing_enabled"] is False
    found = client.get(f"/api/admin/users?q={username[:5].upper()}").json()
    assert found["total"] == 1 and found["items"][0]["admin"] is True and found["items"][0]["totp"] is True
    assert client.get("/api/admin/users?q=nobody").json()["total"] == 0


def test_admin_grants_and_removes_premium(admin, other):
    c, _username = admin
    _switch(c, premium_mode=True)
    _register(other, "member1")
    member = _get("member1")
    res = c.patch(f"/api/admin/users/{member.id}", json={"add_premium_days": 14}, headers=csrf_headers(c))
    assert res.status_code == 200 and res.json()["premium"] is True
    assert _get("member1").premium_until > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=13)
    assert other.get("/api/auth/me").json()["premium"] is True
    assert c.patch(f"/api/admin/users/{member.id}", json={"remove_premium": True}, headers=csrf_headers(c)).json()["premium"] is False
    assert c.patch("/api/admin/users/99999", json={"remove_premium": True}, headers=csrf_headers(c)).status_code == 404
    assert c.patch(f"/api/admin/users/{member.id}", json={"add_premium_days": 0}, headers=csrf_headers(c)).status_code == 422


def _login(client, username, password="TestPass123"):
    client.cookies.clear()
    return client.post("/api/auth/login", json={"username": username, "password": password},
                       headers=anon_csrf_headers(client))


def test_blocked_user_is_signed_out_and_cannot_sign_in(admin, other):
    c, admin_name = admin
    _register(other, "spammer1")
    sid = _get("spammer1").id
    assert c.patch(f"/api/admin/users/{sid}", json={"disabled": True}, headers=csrf_headers(c)).json()["disabled"] is True
    assert c.patch(f"/api/admin/users/{_get(admin_name).id}", json={"disabled": True},
                   headers=csrf_headers(c)).status_code == 400
    assert other.get("/api/auth/me").status_code == 401           # old session revoked
    res = _login(other, "spammer1")
    assert res.status_code == 403 and "zablokovaný" in res.json()["detail"]
    c.patch(f"/api/admin/users/{sid}", json={"disabled": False}, headers=csrf_headers(c))
    assert _login(other, "spammer1").status_code == 200


def test_settings_validation_and_audit(admin):
    client, _u = admin
    current = client.get("/api/admin/settings").json()
    assert current["values"]["chat_enabled"] is True and current["schema"]["free_schedules"]["kind"] == "int"
    bad = [{"chat_enabled": "yes"}, {"free_schedules": 999}, {"unknown_key": 1}, {"announcement": "x" * 300},
           {"announcement_level": "panic"}, {"free_schedules": True}]
    for values in bad:
        assert client.put("/api/admin/settings", json={"values": values}, headers=csrf_headers(client)).status_code == 400
    res = client.put("/api/admin/settings", json={"values": {"free_schedules": 3, "announcement": " Launch week! ",
                                                             "premium_price_label": "€2.99 / month", "premium_mode": True}},
                     headers=csrf_headers(client))
    assert res.status_code == 200 and res.json()["values"]["announcement"] == "Launch week!"
    assert client.get("/api/schedules").json()["max"] == 3
    public = client.get("/api/public/config").json()
    assert public["announcement"] == "Launch week!" and public["premium"]["price_label"] == "€2.99 / month"
    assert "free_schedules" not in public
    actions = [e["action"] for e in client.get("/api/account/activity").json()["events"]]
    assert "admin_settings_changed" in actions


def _switch(client, **values):
    assert client.put("/api/admin/settings", json={"values": values}, headers=csrf_headers(client)).status_code == 200


def test_feature_switches_are_enforced(admin, other):
    client, _u = admin
    _switch(client, chat_enabled=False, backtest_enabled=False, tipsters_enabled=False, waitlist_enabled=False,
            signups_enabled=False)
    off = "Táto funkcia je momentálne vypnutá."
    chat = client.post("/api/chat", json={"provider": "gemini", "messages": [{"role": "user", "content": "hi"}]},
                       headers=csrf_headers(client))
    assert chat.status_code == 403 and chat.json()["detail"] == off
    assert client.get("/api/forecast/backtest?coin=BTC&horizon=24h").status_code == 403
    assert client.get("/api/public/tipsters").status_code == 403
    assert client.post("/api/public/waitlist", json={"email": "a@b.co"}, headers=csrf_headers(client)).status_code == 403
    res = other.post("/api/auth/register", json={"username": "late1", "password": "TestPass123", "email": "late1@example.com"})
    assert res.status_code == 403


def test_referral_switch_controls_the_longer_trial(admin, other):
    from app.services.premium import trial_days_for
    client, _admin_name = admin
    _switch(client, premium_mode=True, referral_trial_days=21)
    code = client.get("/api/account/membership").json()["referral_code"]
    other.post("/api/auth/register", json={"username": "friend2", "password": "TestPass123",
                                           "email": "friend2@example.com", "referral_code": code})
    assert trial_days_for(_get("friend2")) == 21
    _switch(client, referrals_enabled=False)
    assert trial_days_for(_get("friend2")) == 7


def test_waitlist_export(admin):
    client, _u = admin
    db = SessionLocal()
    try:
        db.add(WaitlistEntry(email="fan@example.com", lang="sk", source="tiktok"))
        db.commit()
    finally:
        db.close()
    assert client.get("/api/admin/waitlist").json()["items"][0]["source"] == "tiktok"
    res = client.get("/api/admin/waitlist.csv")
    assert res.headers["content-type"].startswith("text/csv")
    assert res.text.splitlines() == ["email,lang,source,created_at", res.text.splitlines()[1]]
    assert res.text.splitlines()[1].startswith("fan@example.com,sk,tiktok,")


def test_disabled_admin_loses_admin_role(admin):
    from app.services.roles import is_admin
    _client, username = admin
    user = _get(username)
    assert is_admin(user)
    user.disabled = True
    assert not is_admin(user)
