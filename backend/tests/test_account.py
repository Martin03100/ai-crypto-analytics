"""Testy pre app/routers/account.py — API kluce, email, zmena hesla."""

from tests.conftest import csrf_headers


def test_list_api_keys_requires_auth(client):
    res = client.get("/api/account/api-keys")
    assert res.status_code == 401


def test_list_api_keys_returns_all_providers_disconnected(registered):
    client, _username, _password = registered
    res = client.get("/api/account/api-keys")
    assert res.status_code == 200
    providers = res.json()
    assert len(providers) == 5
    assert all(p["connected"] is False for p in providers)


def test_save_and_delete_api_key(registered):
    client, _username, _password = registered
    res = client.put("/api/account/api-keys", json={"provider": "gemini", "api_key": "fake-test-key-123"},
                      headers=csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["connected"] is True
    assert "fake-test-key-123" not in res.text  # nikdy nesmie vratit plny kluc naspat

    res = client.delete("/api/account/api-keys/gemini", headers=csrf_headers(client))
    assert res.status_code == 200

    res = client.get("/api/account/api-keys")
    gemini = next(p for p in res.json() if p["provider"] == "gemini")
    assert gemini["connected"] is False


def test_save_api_key_unknown_provider_rejected(registered):
    client, _username, _password = registered
    res = client.put("/api/account/api-keys", json={"provider": "not-a-real-provider", "api_key": "x"},
                      headers=csrf_headers(client))
    assert res.status_code == 400


def test_update_email_invalid_rejected(registered):
    client, _username, _password = registered
    res = client.put("/api/account/email", json={"email": "not-an-email"}, headers=csrf_headers(client))
    assert res.status_code == 400


def test_update_email_valid_accepted(registered):
    client, _username, _password = registered
    res = client.put("/api/account/email", json={"email": "user@example.com"}, headers=csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["email"] == "user@example.com"


def test_update_email_rejects_duplicate_from_another_account(client):
    """Ak si pouzivatel B zmeni email v Nastaveniach na taky, ktory uz ma
    pouzivatel A, musi to zlyhat - inak by "zabudnute heslo" nevedelo
    spolahlivo urcit spravny ucet pre dany email."""
    client.post("/api/auth/register", json={"username": "userA", "password": "GoodPass123", "email": "shared@example.com"})
    client.post("/api/auth/logout", headers=csrf_headers(client))
    client.post("/api/auth/register", json={"username": "userB", "password": "GoodPass123", "email": "userb@example.com"})

    res = client.put("/api/account/email", json={"email": "shared@example.com"}, headers=csrf_headers(client))
    assert res.status_code == 400


def test_change_password_wrong_current_rejected(registered):
    client, _username, password = registered
    res = client.post("/api/account/change-password",
                       json={"current_password": "WrongCurrentPass1", "new_password": "NewGoodPass123"},
                       headers=csrf_headers(client))
    assert res.status_code == 400


def test_change_password_success_and_can_login_with_new_password(registered):
    client, username, password = registered
    res = client.post("/api/account/change-password",
                       json={"current_password": password, "new_password": "NewGoodPass123"},
                       headers=csrf_headers(client))
    assert res.status_code == 200

    client.post("/api/auth/logout", headers=csrf_headers(client))
    res = client.post("/api/auth/login", json={"username": username, "password": "NewGoodPass123"})
    assert res.status_code == 200


def test_logout_all_devices_invalidates_old_token(registered):
    client, _username, _password = registered
    res = client.post("/api/account/logout-all-devices", headers=csrf_headers(client))
    assert res.status_code == 200
    # Klient dostal novy cookie hned v tejto odpovedi, takze este je prihlaseny.
    res = client.get("/api/auth/me")
    assert res.status_code == 200
