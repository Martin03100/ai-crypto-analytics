"""Account takeover and lock-out protections: recovery codes, captcha instead of lock-outs, security notices."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from app import config, security
from app.database import SessionLocal
from app.models import User
from app.routers import auth as auth_router
from app.services import email_service
from tests.conftest import anon_csrf_headers, csrf_headers


def _enable_2fa(client):
    secret = client.post("/api/account/2fa/setup", headers=csrf_headers(client)).json()["secret"]
    res = client.post("/api/account/2fa/enable", json={"code": security.totp_now(secret)}, headers=csrf_headers(client))
    assert res.status_code == 200
    return secret, res.json()["recovery_codes"]


def _login(client, username, password, **extra):
    return client.post("/api/auth/login", json={"username": username, "password": password, **extra},
                       headers=anon_csrf_headers(client))


def _capture_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(email_service, "is_email_configured", lambda: True)
    monkeypatch.setattr(email_service, "send_email", lambda to, subject, text, html=None: sent.append((to, subject, text)))
    return sent


def test_recovery_codes_sign_in_once_and_can_be_renewed(registered):
    client, username, password = registered
    secret, codes = _enable_2fa(client)
    assert len(codes) == 10 and all(len(c) == 9 and c[4] == "-" for c in codes)
    assert client.get("/api/account/2fa/recovery-codes").json() == {"left": 10, "total": 10}
    client.post("/api/auth/logout", headers=csrf_headers(client))

    assert _login(client, username, password, totp_code=codes[0].upper().replace("-", " ")).status_code == 200
    assert client.get("/api/account/2fa/recovery-codes").json()["left"] == 9
    client.post("/api/auth/logout", headers=csrf_headers(client))
    assert _login(client, username, password, totp_code=codes[0]).status_code == 401      # spent

    assert _login(client, username, password, totp_code=codes[1]).status_code == 200
    renewed = client.post("/api/account/2fa/recovery-codes", json={"password": password,
                          "code": security.totp_now(secret, at=time.time() + 30)}, headers=csrf_headers(client))
    assert renewed.status_code == 200 and len(renewed.json()["recovery_codes"]) == 10
    new_codes = renewed.json()["recovery_codes"]
    client.post("/api/auth/logout", headers=csrf_headers(client))
    assert _login(client, username, password, totp_code=codes[2]).status_code == 401      # old codes stop working
    assert _login(client, username, password, totp_code=new_codes[0]).status_code == 200
    # A lost phone: 2FA can be turned off with a recovery code too.
    res = client.post("/api/account/2fa/disable", json={"password": password, "code": new_codes[1]}, headers=csrf_headers(client))
    assert res.status_code == 200 and res.json()["totp_enabled"] is False


def test_failed_attempts_ask_for_a_captcha_instead_of_locking_the_owner_out(registered, monkeypatch):
    client, username, password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    monkeypatch.setattr(auth_router, "is_captcha_enabled", lambda: True)
    monkeypatch.setattr(auth_router, "verify_captcha", lambda token, ip=None: token == "solved")
    for _ in range(5):
        assert _login(client, username, "WrongPass999").status_code == 401
    res = _login(client, username, password)
    assert res.status_code == 401 and res.headers.get("X-Error-Code") == "captcha_required"
    assert _login(client, username, password, captcha_token="solved").status_code == 200


def test_lock_warning_email_is_sent_at_most_every_six_hours(registered, monkeypatch):
    client, username, _password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    sent = []
    monkeypatch.setattr(auth_router, "is_email_configured", lambda: True)
    monkeypatch.setattr(auth_router, "send_email", lambda *a, **k: sent.append(a))

    def unlock():
        db = SessionLocal()
        try:
            db.query(User).filter(User.username == username).update({"locked_until": datetime.utcnow() - timedelta(minutes=1)})
            db.commit()
        finally:
            db.close()

    for _round in range(2):
        for _ in range(5):
            _login(client, username, "WrongPass999")
        unlock()
    deadline = time.monotonic() + 3
    while not sent and time.monotonic() < deadline:     # sent from a background thread
        time.sleep(0.02)
    time.sleep(0.1)
    assert len(sent) == 1


def test_email_change_warns_the_previous_address(registered, monkeypatch):
    client, username, password = registered
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update({"email_verified": True})
        db.commit()
    finally:
        db.close()
    sent = _capture_emails(monkeypatch)
    res = client.put("/api/account/email", json={"email": "new.address@example.com", "password": password},
                     headers=csrf_headers(client))
    assert res.status_code == 200
    to, subject, text = sent[0]
    assert to == "testuser1@example.com" and "n***@example.com" in text and "new.address" not in text


def test_password_change_and_2fa_send_notices(registered, monkeypatch):
    client, _username, password = registered
    sent = _capture_emails(monkeypatch)
    res = client.post("/api/account/change-password", json={"current_password": password, "new_password": "NewPass12345"},
                      headers=csrf_headers(client))
    assert res.status_code == 200
    _enable_2fa(client)
    assert [s[0] for s in sent] == ["testuser1@example.com"] * 2
    assert "changed" in sent[0][2] and "2FA" in sent[1][2]


def test_an_admin_account_cannot_be_deleted(registered, monkeypatch):
    client, username, password = registered
    monkeypatch.setattr(config, "ADMIN_USERNAMES", frozenset({username.lower()}))
    res = client.post("/api/account/delete", json={"password": password}, headers=csrf_headers(client))
    assert res.status_code == 400 and "ADMIN_USERNAMES" in res.json()["detail"]
