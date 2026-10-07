"""Stripe connected from the admin panel: one key creates the product, prices, webhook and portal."""

import pytest

from app import config
from app.database import SessionLocal
from app.models import AppSetting, User
from app.services import billing, stripe_connect
from tests.conftest import csrf_headers


class FakeStripe:
    def __init__(self):
        self.calls = []
        self.hooks = [{"id": "we_old", "url": stripe_connect.webhook_url()}, {"id": "we_other", "url": "https://x/y"}]

    def request(self, method, url, data=None, auth=None, timeout=None):
        path = url.replace(stripe_connect.STRIPE_API, "")
        self.calls.append((method, path, data, auth[0]))
        if auth[0] == "sk_test_bad":
            return _Res(401, {"error": {"message": "Invalid API Key"}})
        bodies = {
            ("GET", "/account"): {"charges_enabled": True, "payouts_enabled": False, "details_submitted": True, "country": "CZ"},
            ("POST", "/products"): {"id": "prod_1"},
            ("GET", "/webhook_endpoints?limit=100"): {"data": self.hooks},
            ("POST", "/webhook_endpoints"): {"id": "we_new", "secret": "whsec_new"},
            ("POST", "/billing_portal/configurations"): {"id": "bpc_1"},
        }
        if (method, path) == ("POST", "/prices"):
            return _Res(200, {"id": f"price_{data['recurring[interval]']}"})
        if method == "DELETE":
            return _Res(200, {"deleted": True})
        return _Res(200, bodies[(method, path)])


class _Res:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._body


def _update(username, **fields):
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == username).update(fields)
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def admin(registered, monkeypatch):
    client, username, _p = registered
    monkeypatch.setattr(config, "ADMIN_USERNAMES", frozenset({username.lower()}))
    _update(username, totp_enabled=True)
    fake = FakeStripe()
    monkeypatch.setattr(stripe_connect.requests, "request", fake.request)
    return client, fake


def _connect(client, **body):
    return client.put("/api/admin/payments", json={"currency": "eur", "monthly_cents": 499, "yearly_cents": 3900, **body},
                      headers=csrf_headers(client))


def test_regular_users_cannot_see_or_set_payments(registered):
    client, _u, _p = registered
    assert client.get("/api/admin/payments").status_code == 403
    assert _connect(client, secret_key="sk_test_x").status_code == 403


def test_one_key_sets_up_everything_and_is_stored_encrypted(admin):
    client, fake = admin
    before = client.get("/api/admin/payments").json()
    assert before["connected"] is False and before["checklist"] == {
        "seller": False, "stripe": False, "payouts": False, "live": False, "premium_mode": False}
    assert _connect(client, secret_key="pk_test_wrong").status_code == 400
    res = _connect(client, secret_key="sk_test_abcdefghijklmnop1234")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["connected"] and data["key_hint"] == "sk_test_…1234" and data["account"]["mode"] == "test"
    assert data["checklist"]["stripe"] and not data["checklist"]["payouts"]           # bank account not finished
    assert "sk_test_abcdefghijklmnop1234" not in res.text
    hooks = [c for c in fake.calls if c[1].startswith("/webhook_endpoints/")]
    assert hooks == [("DELETE", "/webhook_endpoints/we_old", None, "sk_test_abcdefghijklmnop1234")]
    created = next(c for c in fake.calls if c[:2] == ("POST", "/webhook_endpoints"))[2]
    assert created["url"].endswith("/api/billing/webhook") and "invoice.paid" in created.values()

    db = SessionLocal()
    try:
        raw = db.get(AppSetting, "stripe_credentials").value_json
    finally:
        db.close()
    assert "sk_test" not in raw and "whsec" not in raw
    creds = billing.credentials()
    assert creds["price_monthly"] == "price_month" and creds["price_yearly"] == "price_year"
    assert creds["webhook_secret"] == "whsec_new" and billing.billing_enabled() and billing.yearly_available()
    labels = client.get("/api/admin/settings").json()["values"]
    assert labels["premium_price_label"] == "€4.99 / month" and labels["premium_price_label_yearly"] == "€39 / year"


def test_changing_prices_keeps_the_saved_key_and_product(admin):
    client, fake = admin
    _connect(client, secret_key="sk_test_abcdefghijklmnop1234")
    fake.calls.clear()
    res = _connect(client, secret_key="", currency="czk", monthly_cents=12900, yearly_cents=None)
    assert res.status_code == 200 and res.json()["yearly"] is False
    assert not any(c[1] == "/products" for c in fake.calls) and not any(c[1] == "/billing_portal/configurations" for c in fake.calls)
    assert client.get("/api/admin/settings").json()["values"]["premium_price_label"] == "129 Kč / month"


def test_bad_key_and_disconnect(admin):
    client, _fake = admin
    res = _connect(client, secret_key="sk_test_bad")
    assert res.status_code == 400 and res.json()["detail"] == "Stripe kľúč je neplatný."
    _connect(client, secret_key="sk_test_abcdefghijklmnop1234")
    assert client.delete("/api/admin/payments", headers=csrf_headers(client)).json()["connected"] is False
    assert billing.credentials() == {} and not billing.billing_enabled()
    actions = [e["action"] for e in client.get("/api/account/activity").json()["events"]]
    assert "admin_payments_connected" in actions and "admin_payments_disconnected" in actions


def test_environment_keys_take_precedence(admin, monkeypatch):
    client, _fake = admin
    monkeypatch.setattr(billing, "STRIPE_SECRET_KEY", "sk_live_env")
    assert _connect(client, secret_key="sk_test_abcdefghijklmnop1234").status_code == 409
    assert billing.credentials()["source"] == "env"


def test_checkout_and_portal_use_admin_connected_stripe(admin, monkeypatch):
    client, _fake = admin
    _connect(client, secret_key="sk_test_abcdefghijklmnop1234")
    client.put("/api/admin/settings", json={"values": {"premium_mode": True, "operator_name": "M", "operator_address": "Prague"}},
               headers=csrf_headers(client))
    sent = []
    monkeypatch.setattr(billing, "_post", lambda path, data: sent.append((path, data)) or {"url": "https://checkout.stripe.test/s"})
    res = client.post("/api/billing/checkout", json={"accept_terms": True, "start_immediately": True, "plan": "yearly"},
                      headers=csrf_headers(client))
    assert res.status_code == 200 and sent[-1][1]["line_items[0][price]"] == "price_year"
    assert client.get("/api/admin/payments").json()["selling"] is True
