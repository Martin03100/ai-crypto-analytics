"""Sign in with Google: new accounts, linking only through a confirmed e-mail, 2FA and accounts without a password."""

import pytest

from app.database import SessionLocal
from app.models import AuditEvent, User
from app.security import totp_now
from app.services import google_auth
from tests.conftest import anon_csrf_headers, csrf_headers

CLIENT_ID = "1234567890-test.apps.googleusercontent.com"


@pytest.fixture()
def google(monkeypatch):
    """Google turned on; `tokens` maps a fake credential to the claims Google would confirm for it."""
    tokens = {}
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(google_auth, "verify_credential", lambda credential: tokens.get(credential))
    return tokens


def _sign_in(client, credential, **extra):
    return client.post("/api/auth/google", json={"credential": credential, **extra}, headers=anon_csrf_headers(client))


def _user(email):
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).one()


def test_turned_off_without_a_client_id(client):
    assert _sign_in(client, "x" * 40).status_code == 404


def test_a_bad_token_is_refused(client, google):
    assert _sign_in(client, "not-a-real-google-token-xxxxxxxx").status_code == 401


def test_first_sign_in_creates_a_confirmed_account_without_a_password(client, google):
    google["t" * 40] = {"sub": "g-1", "email": "Jan.Novak@Gmail.com"}
    res = _sign_in(client, "t" * 40, lang="sk")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["username"] == "jan.novak" and body["email_verified"] is True
    assert body["has_password"] is False and body["google"] is True
    user = _user("jan.novak@gmail.com")
    assert user.google_sub == "g-1" and user.lang == "sk"
    assert client.get("/api/auth/me").json()["user_id"] == user.id
    # The same Google account signs in to the same account again, also when the name is taken by someone else.
    client.cookies.clear()
    assert _sign_in(client, "t" * 40).json()["user_id"] == user.id


def test_links_an_account_only_through_a_confirmed_email(registered, google):
    client, username, _password = registered
    google["u" * 40] = {"sub": "g-2", "email": "testuser1@example.com"}
    client.cookies.clear()
    # testuser1 never confirmed the address (e-mail is not configured in tests): no takeover through Google.
    assert _sign_in(client, "u" * 40).status_code == 409
    with SessionLocal() as db:
        db.query(User).filter(User.username == username).update({"email_verified": True})
        db.commit()
    res = _sign_in(client, "u" * 40)
    assert res.status_code == 200 and res.json()["username"] == username and res.json()["has_password"] is True
    with SessionLocal() as db:
        actions = [a for (a,) in db.query(AuditEvent.action).all()]
    assert "google_linked" in actions


def test_two_factor_is_still_required(registered, google, monkeypatch):
    client, username, _password = registered
    from app.security import encrypt_secret, generate_totp_secret
    secret = generate_totp_secret()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        user.email_verified, user.totp_enabled, user.totp_secret = True, True, encrypt_secret(secret, user.id)
        db.commit()
    google["v" * 40] = {"sub": "g-3", "email": "testuser1@example.com"}
    client.cookies.clear()
    res = _sign_in(client, "v" * 40)
    assert res.status_code == 401 and res.headers.get("x-error-code") == "totp_required"
    assert _sign_in(client, "v" * 40, totp_code="000000").status_code == 401
    assert _user("testuser1@example.com").google_sub is None      # a failed second factor links nothing
    assert _sign_in(client, "v" * 40, totp_code=totp_now(secret)).status_code == 200
    assert _user("testuser1@example.com").google_sub == "g-3"


def test_account_without_a_password_can_set_one_and_delete_itself(client, google):
    google["w" * 40] = {"sub": "g-4", "email": "anna@example.com"}
    assert _sign_in(client, "w" * 40).status_code == 200
    h = csrf_headers(client)
    res = client.post("/api/account/change-password", json={"current_password": "", "new_password": "AnnaPass123"}, headers=h)
    assert res.status_code == 200
    assert client.get("/api/auth/me").json()["has_password"] is True
    # Once a password exists it is required again.
    assert client.post("/api/account/delete", json={"password": ""}, headers=csrf_headers(client)).status_code == 400
    assert client.post("/api/account/delete", json={"password": "AnnaPass123"}, headers=csrf_headers(client)).status_code == 200


def test_blocked_account_cannot_sign_in_with_google(client, google):
    google["z" * 40] = {"sub": "g-5", "email": "bob@example.com"}
    assert _sign_in(client, "z" * 40).status_code == 200
    with SessionLocal() as db:
        db.query(User).filter(User.email == "bob@example.com").update({"disabled": True})
        db.commit()
    client.cookies.clear()
    assert _sign_in(client, "z" * 40).status_code == 403


def test_verify_credential_checks_audience_issuer_and_email(monkeypatch):
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_ID", CLIENT_ID)
    good = {"aud": CLIENT_ID, "iss": "https://accounts.google.com", "email_verified": "true", "sub": "1", "email": "a@b.cz"}

    class Res:
        def __init__(self, claims):
            self.status_code, self._claims = 200, claims

        def json(self):
            return self._claims

    for claims, ok in ((good, True), ({**good, "aud": "someone-else"}, False), ({**good, "iss": "evil.com"}, False),
                       ({**good, "email_verified": "false"}, False)):
        monkeypatch.setattr(google_auth.requests, "get", lambda *_a, c=claims, **_k: Res(c))
        assert (google_auth.verify_credential("x" * 40) is not None) is ok


def test_public_config_shares_the_client_id(client, monkeypatch):
    from app.routers import public
    monkeypatch.setattr(public, "GOOGLE_CLIENT_ID", CLIENT_ID)
    assert client.get("/api/public/config").json()["google_client_id"] == CLIENT_ID
