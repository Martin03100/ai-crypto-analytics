"""Optional Sentry monitoring: off by default, never leaks secrets."""

from app import monitoring


def test_disabled_without_dsn(monkeypatch):
    monkeypatch.setattr(monitoring, "SENTRY_DSN", "")
    assert monitoring.init_monitoring() is False
    monitoring.capture_exception(RuntimeError("x"))  # no-op, must not raise


def test_scrub_removes_api_keys_and_tokens():
    text = "Gemini call failed key=AIzaSyA1234567890abcdef, auth Bearer abc.def.ghi, sk-proj-ABCDEFGHIJKLMNOP"
    cleaned = monitoring.scrub(text)
    assert "AIzaSyA1234567890abcdef" not in cleaned and "abc.def.ghi" not in cleaned
    assert "ABCDEFGHIJKLMNOP" not in cleaned and "[redacted]" in cleaned


def test_before_send_strips_body_cookies_and_auth_headers():
    event = {
        "request": {"headers": {"Cookie": "aca_session=x", "User-Agent": "ua", "X-CSRF-Token": "t"},
                    "data": {"password": "hunter2"}, "cookies": {"a": "b"}},
        "exception": {"values": [{"value": "token=supersecret123 failed"}]},
    }
    out = monitoring._before_send(event, {})
    assert out["request"]["headers"]["Cookie"] == "[redacted]" and out["request"]["headers"]["User-Agent"] == "ua"
    assert "data" not in out["request"] and "cookies" not in out["request"]
    assert "supersecret123" not in out["exception"]["values"][0]["value"]


def test_unhandled_errors_are_reported(client, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import market
    reported = []
    monkeypatch.setattr("app.main.capture_exception", reported.append)
    monkeypatch.setattr(market, "get_upcoming_market_events", lambda lang: 1 / 0)
    res = TestClient(app, raise_server_exceptions=False).get("/api/market/events")
    assert res.status_code == 500 and "ZeroDivisionError" not in res.text
    assert len(reported) == 1 and isinstance(reported[0], ZeroDivisionError)
