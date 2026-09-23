"""Testy pre app/routers/auth.py — registracia, prihlasenie, session, CSRF."""

from tests.conftest import anon_csrf_headers, csrf_headers


def test_register_success(client):
    res = client.post("/api/auth/register", json={"username": "alice", "password": "GoodPass123"})
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "alice"
    assert "access_token" in body and body["access_token"]


def test_register_duplicate_username_rejected(registered):
    client, username, password = registered
    res = client.post("/api/auth/register", json={"username": username, "password": "AnotherPass123"})
    assert res.status_code == 400


def test_register_password_too_short_is_validation_error(client):
    res = client.post("/api/auth/register", json={"username": "bob", "password": "short"})
    assert res.status_code == 422
    # Pydantic validacne chyby vracaju POLE objektov (viz frontend api.js extractDetailMessage)
    assert isinstance(res.json()["detail"], list)


def test_login_success(registered):
    client, username, password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    assert res.json()["username"] == username


def test_login_wrong_password_rejected(registered):
    client, username, _password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    res = client.post("/api/auth/login", json={"username": username, "password": "TotallyWrongPass1"})
    assert res.status_code == 401


def test_login_nonexistent_user_rejected(client):
    res = client.post("/api/auth/login", json={"username": "ghost", "password": "WhateverPass123"})
    assert res.status_code == 401


def test_me_requires_authentication(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_returns_current_user_after_login(registered):
    client, username, _password = registered
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["username"] == username


def test_logout_invalidates_session(registered):
    client, _username, _password = registered
    res = client.post("/api/auth/logout", headers=csrf_headers(client))
    assert res.status_code == 200
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_forgot_password_always_returns_generic_success(client):
    """Anti-enumeration: aj pre neexistujuceho pouzivatela musi vratit
    rovnaku uspesnu odpoved, aby sa cez tento endpoint nedalo zistit,
    ktore ucty existuju."""
    res = client.post("/api/auth/forgot-password", json={"username": "nobody-here"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_forgot_password_never_leaks_reset_link_in_production(client, monkeypatch):
    """Bezpecnostna regresia: dev_reset_link sa v produkcii NIKDY nesmie
    vratit v API odpovedi, aj ked SMTP nie je nakonfigurovane - inak by
    ktokolvek, kto pozna existujuce pouzivatelske meno so zadanym emailom,
    mohol cez tento endpoint ziskat funkcny reset odkaz bez pristupu k
    tomu emailu."""
    monkeypatch.setattr("app.routers.auth.APP_ENV", "production")
    client.post("/api/auth/register", json={"username": "prodtest", "password": "GoodPass123"})
    client.put("/api/account/email", json={"email": "prodtest@example.com"}, headers=csrf_headers(client))
    client.post("/api/auth/logout", headers=csrf_headers(client))

    res = client.post("/api/auth/forgot-password", json={"username": "prodtest"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 200
    assert "dev_reset_link" not in res.json()


def test_mutating_request_without_csrf_token_rejected(registered):
    client, _username, _password = registered
    res = client.put("/api/account/email", json={"email": "test@example.com"})
    assert res.status_code == 403


def test_mutating_request_with_csrf_token_succeeds(registered):
    client, _username, _password = registered
    res = client.put("/api/account/email", json={"email": "test@example.com"}, headers=csrf_headers(client))
    assert res.status_code == 200
