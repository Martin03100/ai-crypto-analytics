"""Testy bezpecnostnych funkcii: 2FA (TOTP), overenie emailu, CAPTCHA,
sifrovanie viazane na pouzivatela, upozornenie pri uzamknuti uctu."""

import base64

from app import security
from tests.conftest import anon_csrf_headers, csrf_headers


def test_totp_matches_rfc6238_test_vector():
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert security.totp_now(secret, at=59) == "287082"
    assert security.verify_totp(secret, "287082", at=59) is True
    assert security.verify_totp(secret, "123456", at=59) is False
    assert security.verify_totp(secret, "abc", at=59) is False


def test_per_user_encryption_is_bound_to_user_and_reads_legacy():
    cipher = security.encrypt_secret("sk-tajny", 1)
    assert cipher.startswith("v2:")
    assert security.decrypt_secret(cipher, 1) == "sk-tajny"
    assert security.decrypt_secret(cipher, 2) is None  # cudzi ucet ho nedesifruje
    legacy = security.encrypt_secret("sk-stary")
    assert security.is_legacy_ciphertext(legacy) and security.decrypt_secret(legacy, 5) == "sk-stary"


def test_two_factor_login_flow(registered):
    client, username, password = registered
    secret = client.post("/api/account/2fa/setup", headers=csrf_headers(client)).json()["secret"]
    assert client.post("/api/account/2fa/enable", json={"code": "000000"}, headers=csrf_headers(client)).status_code == 400
    assert client.post("/api/account/2fa/enable", json={"code": security.totp_now(secret)},
                       headers=csrf_headers(client)).status_code == 200
    client.post("/api/auth/logout", headers=csrf_headers(client))
    creds = {"username": username, "password": password}
    res = client.post("/api/auth/login", json=creds, headers=anon_csrf_headers(client))
    assert res.status_code == 401 and "6-miestny" in res.json()["detail"]
    res = client.post("/api/auth/login", json={**creds, "totp_code": "000000"}, headers=anon_csrf_headers(client))
    assert res.status_code == 401
    res = client.post("/api/auth/login", json={**creds, "totp_code": security.totp_now(secret)}, headers=anon_csrf_headers(client))
    assert res.status_code == 200 and res.json()["totp_enabled"] is True


def test_email_verification_gate(client, monkeypatch):
    from app.routers import auth as auth_router
    from app.services import verification
    monkeypatch.setattr(auth_router, "is_email_configured", lambda: True)
    monkeypatch.setattr(verification, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(verification, "generate_reset_code", lambda: ("123456", security.hash_reset_token("123456")))
    res = client.post("/api/auth/register", json={"username": "overovac", "password": "heslo12345", "email": "over@example.com"},
                      headers=anon_csrf_headers(client))
    assert res.status_code == 201 and res.json()["email_verified"] is False
    assert client.get("/api/forecast/history").status_code == 403
    assert client.post("/api/auth/verify-email", json={"code": "000000"}, headers=csrf_headers(client)).status_code == 400
    assert client.post("/api/auth/verify-email", json={"code": "123456"}, headers=csrf_headers(client)).status_code == 200
    assert client.get("/api/forecast/history").status_code == 200


def test_captcha_required_when_configured(client, monkeypatch):
    from app.services import captcha
    monkeypatch.setattr(captcha, "TURNSTILE_SECRET_KEY", "test-secret")
    body = {"username": "robot1", "password": "heslo12345", "email": "robot@example.com"}
    assert client.post("/api/auth/register", json=body, headers=anon_csrf_headers(client)).status_code == 400

    class Ok:
        def json(self):
            return {"success": True}
    monkeypatch.setattr(captcha.requests, "post", lambda *a, **k: Ok())
    assert client.post("/api/auth/register", json={**body, "captcha_token": "tok"}, headers=anon_csrf_headers(client)).status_code == 201


def test_lockout_sends_warning_email(registered, monkeypatch):
    from app.routers import auth as auth_router
    client, username, _password = registered
    sent = []
    monkeypatch.setattr(auth_router, "is_email_configured", lambda: True)
    monkeypatch.setattr(auth_router, "send_email", lambda to, subject, *a, **k: sent.append((to, subject)))
    client.post("/api/auth/logout", headers=csrf_headers(client))
    for _ in range(5):
        client.post("/api/auth/login", json={"username": username, "password": "zle-heslo"}, headers=anon_csrf_headers(client))
    import time
    for _ in range(100):  # email sa posiela v samostatnom vlakne
        if sent:
            break
        time.sleep(0.02)
    assert len(sent) == 1 and "prihlásenie" in sent[0][1]
