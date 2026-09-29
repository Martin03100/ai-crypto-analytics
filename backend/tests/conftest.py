"""Test fixtures."""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "aca_test.db")
if os.path.exists(_TEST_DB_PATH):
    os.remove(_TEST_DB_PATH)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("PASSWORD_HASH_ROUNDS", "1000")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-do-not-use-in-production")
os.environ.setdefault("API_KEY_ENCRYPTION_SECRET", "test-only-fernet-secret-do-not-use-in-prod")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.rate_limit import _hits as _rate_limit_hits  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    _rate_limit_hits.clear()
    yield
    _rate_limit_hits.clear()


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def registered(client):
    username = "testuser1"
    password = "TestPass123"
    email = "testuser1@example.com"
    res = client.post("/api/auth/register", json={"username": username, "password": password, "email": email})
    assert res.status_code == 201, res.text
    return client, username, password


def csrf_headers(client) -> dict:
    token = client.cookies.get("aca_csrf")
    return {"X-CSRF-Token": token} if token else {}


def anon_csrf_headers(client) -> dict:
    client.get("/api/health")
    return csrf_headers(client)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app import rate_limit
    rate_limit._hits.clear()
    yield
    rate_limit._hits.clear()


def signed_forecast_payload(client, prices=(100.0, 110.0), provider="gemini", coin="BTC", horizon="1T", created=None):
    from datetime import datetime, timezone
    from app.security import sign_forecast
    user_id = client.get("/api/auth/me").json()["user_id"]
    created = created or datetime.now(timezone.utc).isoformat()
    prices = [float(p) for p in prices]
    return {
        "provider": provider, "coin": coin, "horizon": horizon, "is_mock": False,
        "forecast_data": {
            "ceny": prices, "casove_body": [f"b{i}" for i in range(len(prices))], "odovodnenie": "test",
            "vytvorene": created, "podpis": sign_forecast(user_id, provider, coin, horizon, prices, created),
        },
    }
