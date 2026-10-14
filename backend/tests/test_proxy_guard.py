"""Requests that bypass the Netlify proxy are refused once PROXY_SIGNATURE_SECRET is set."""

import time

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.proxy_guard import ProxyGuardMiddleware

SECRET = "netlify-signature-test-secret-0123456789"


def _app(secret=SECRET):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/public/config")
    def config():
        return {"ok": True}

    @app.post("/api/billing/webhook")
    def webhook():
        return {"ok": True}

    app.add_middleware(ProxyGuardMiddleware, secret=secret)
    return TestClient(app)


def _sign(secret=SECRET, iss="netlify", exp_in=60):
    return jwt.encode({"iss": iss, "exp": int(time.time()) + exp_in, "site_url": "https://x.netlify.app"}, secret,
                      algorithm="HS256")


def test_without_a_secret_everything_passes():
    assert _app(secret="").get("/api/public/config").status_code == 200


def test_unsigned_direct_requests_are_refused():
    client = _app()
    assert client.get("/api/public/config").status_code == 403
    assert client.get("/api/public/config", headers={"x-nf-sign": "garbage"}).status_code == 403


def test_signed_requests_pass():
    assert _app().get("/api/public/config", headers={"x-nf-sign": _sign()}).status_code == 200


def test_wrong_secret_issuer_or_expired_signature_is_refused():
    client = _app()
    for token in (_sign(secret="another-secret-of-sufficient-length-xx"), _sign(iss="evil"), _sign(exp_in=-120)):
        assert client.get("/api/public/config", headers={"x-nf-sign": token}).status_code == 403


def test_health_and_stripe_webhook_stay_reachable_directly():
    client = _app()
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/billing/webhook").status_code == 200
