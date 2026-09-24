"""Testy pre app/routers/auth.py — registracia, prihlasenie, session, CSRF."""

from tests.conftest import anon_csrf_headers, csrf_headers


def test_register_success(client):
    res = client.post("/api/auth/register", json={"username": "alice", "password": "GoodPass123", "email": "alice@example.com"})
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "alice"
    assert "access_token" in body and body["access_token"]


def test_register_duplicate_username_rejected(registered):
    client, username, password = registered
    res = client.post("/api/auth/register", json={"username": username, "password": "AnotherPass123", "email": "someone-else@example.com"})
    assert res.status_code == 400


def test_register_password_too_short_is_validation_error(client):
    res = client.post("/api/auth/register", json={"username": "bob", "password": "short", "email": "bob@example.com"})
    assert res.status_code == 422
    # Pydantic validacne chyby vracaju POLE objektov (viz frontend api.js extractDetailMessage)
    assert isinstance(res.json()["detail"], list)


def test_register_without_email_is_validation_error(client):
    res = client.post("/api/auth/register", json={"username": "noemail", "password": "GoodPass123"})
    assert res.status_code == 422


def test_register_invalid_email_rejected(client):
    res = client.post("/api/auth/register", json={"username": "bademail", "password": "GoodPass123", "email": "not-an-email"})
    assert res.status_code == 400


def test_register_duplicate_email_rejected(registered):
    client, _username, _password = registered
    res = client.post("/api/auth/register", json={"username": "differentuser", "password": "GoodPass123", "email": "testuser1@example.com"})
    assert res.status_code == 400


def test_register_stores_email_and_returns_it(client):
    res = client.post("/api/auth/register", json={"username": "withemail", "password": "GoodPass123", "email": "withemail@example.com"})
    assert res.status_code == 201
    assert res.json()["email"] == "withemail@example.com"


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
    res = client.post("/api/auth/forgot-password", json={"email": "nobody-here@example.com"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_forgot_password_looks_up_by_email_not_username(registered):
    """Zabudnute heslo teraz pyta EMAIL (nie pouzivatelske meno) - over, ze
    lookup podla emailu (nastaveneho pri registracii) realne funguje."""
    client, username, _password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    res = client.post("/api/auth/forgot-password", json={"email": "testuser1@example.com"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert "dev_reset_code" in res.json()
    assert len(res.json()["dev_reset_code"]) == 6
    assert res.json()["dev_reset_code"].isdigit()


def test_full_reset_flow_request_verify_reset(registered):
    """End-to-end: poziadaj o kod -> over kod -> nastav nove heslo -> priihlas
    sa uz NOVYM heslom (stare uz nema fungovat)."""
    client, username, old_password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))

    res = client.post("/api/auth/forgot-password", json={"email": "testuser1@example.com"},
                       headers=anon_csrf_headers(client))
    code = res.json()["dev_reset_code"]

    res = client.post("/api/auth/verify-reset-code", json={"email": "testuser1@example.com", "code": code},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["valid"] is True

    res = client.post("/api/auth/reset-password",
                       json={"email": "testuser1@example.com", "code": code, "new_password": "BrandNewPass123"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["success"] is True

    res = client.post("/api/auth/login", json={"username": username, "password": old_password})
    assert res.status_code == 401  # stare heslo uz nefunguje

    res = client.post("/api/auth/login", json={"username": username, "password": "BrandNewPass123"})
    assert res.status_code == 200


def test_verify_reset_code_rejects_wrong_code(registered):
    client, _username, _password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    client.post("/api/auth/forgot-password", json={"email": "testuser1@example.com"},
                headers=anon_csrf_headers(client))

    res = client.post("/api/auth/verify-reset-code", json={"email": "testuser1@example.com", "code": "000000"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 400


def test_reset_password_rejects_wrong_code(registered):
    client, _username, _password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    client.post("/api/auth/forgot-password", json={"email": "testuser1@example.com"},
                headers=anon_csrf_headers(client))

    res = client.post("/api/auth/reset-password",
                       json={"email": "testuser1@example.com", "code": "000000", "new_password": "WhateverPass123"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 400


def test_requesting_new_code_invalidates_the_previous_one(registered):
    """Ak si pouzivatel vypyta kod dvakrat po sebe, ten PRVY uz nesmie
    fungovat - platny je vzdy len ten najnovsi."""
    client, _username, _password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))

    res1 = client.post("/api/auth/forgot-password", json={"email": "testuser1@example.com"},
                        headers=anon_csrf_headers(client))
    first_code = res1.json()["dev_reset_code"]

    client.post("/api/auth/forgot-password", json={"email": "testuser1@example.com"},
                headers=anon_csrf_headers(client))

    res = client.post("/api/auth/verify-reset-code", json={"email": "testuser1@example.com", "code": first_code},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 400


def test_forgot_password_never_leaks_reset_code_in_production(client, monkeypatch):
    """Bezpecnostna regresia: dev_reset_code sa v produkcii NIKDY nesmie
    vratit v API odpovedi, aj ked SMTP nie je nakonfigurovane - inak by
    ktokolvek, kto pozna existujuci email, mohol cez tento endpoint ziskat
    funkcny reset kod bez pristupu k tomu emailu."""
    monkeypatch.setattr("app.routers.auth.APP_ENV", "production")
    client.post("/api/auth/register", json={"username": "prodtest", "password": "GoodPass123", "email": "prodtest@example.com"})
    client.post("/api/auth/logout", headers=csrf_headers(client))

    res = client.post("/api/auth/forgot-password", json={"email": "prodtest@example.com"},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 200
    assert "dev_reset_code" not in res.json()


def test_mutating_request_without_csrf_token_rejected(registered):
    client, _username, _password = registered
    res = client.put("/api/account/email", json={"email": "test@example.com"})
    assert res.status_code == 403


def test_mutating_request_with_csrf_token_succeeds(registered):
    client, _username, _password = registered
    res = client.put("/api/account/email", json={"email": "test@example.com"}, headers=csrf_headers(client))
    assert res.status_code == 200
