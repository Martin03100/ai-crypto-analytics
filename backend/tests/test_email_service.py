"""Testy pre app/services/email_service.py — Brevo HTTPS API (prioritne,
funguje aj na Render free tier) a SMTP fallback."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import email_service  # noqa: E402


def test_is_email_configured_true_with_brevo_key_alone(monkeypatch):
    monkeypatch.setattr(email_service, "BREVO_API_KEY", "fake-brevo-key")
    monkeypatch.setattr(email_service, "SMTP_HOST", "")
    assert email_service.is_email_configured() is True


def test_is_email_configured_false_with_nothing_set(monkeypatch):
    monkeypatch.setattr(email_service, "BREVO_API_KEY", "")
    monkeypatch.setattr(email_service, "SMTP_HOST", "")
    monkeypatch.setattr(email_service, "SMTP_USER", "")
    monkeypatch.setattr(email_service, "SMTP_PASSWORD", "")
    assert email_service.is_email_configured() is False


def test_send_email_prefers_brevo_over_smtp_when_both_configured(monkeypatch):
    """Ak su nastavene OBE (Brevo aj SMTP), Brevo (HTTPS, funguje aj na
    Render free tier) musi mat prednost pred SMTP (tam casto zablokovane)."""
    monkeypatch.setattr(email_service, "BREVO_API_KEY", "fake-brevo-key")
    monkeypatch.setattr(email_service, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_service, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(email_service, "SMTP_PASSWORD", "secret")

    called = {"brevo": False, "smtp": False}
    monkeypatch.setattr(email_service, "_send_via_brevo", lambda *a, **k: called.__setitem__("brevo", True) or True)
    monkeypatch.setattr(email_service, "_send_via_smtp", lambda *a, **k: called.__setitem__("smtp", True) or True)

    result = email_service.send_email("someone@example.com", "Subject", "Body")
    assert result is True
    assert called["brevo"] is True
    assert called["smtp"] is False


def test_send_via_brevo_posts_expected_payload(monkeypatch):
    monkeypatch.setattr(email_service, "BREVO_API_KEY", "fake-brevo-key")
    monkeypatch.setattr(email_service, "EMAIL_FROM", "no-reply@example.com")

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(email_service.requests, "post", fake_post)

    result = email_service._send_via_brevo("someone@example.com", "Kód na reset", "text verzia", "<p>html</p>")
    assert result is True
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"]["api-key"] == "fake-brevo-key"
    assert captured["json"]["to"] == [{"email": "someone@example.com"}]
    assert captured["json"]["sender"] == {"email": "no-reply@example.com"}
    assert captured["json"]["htmlContent"] == "<p>html</p>"


def test_send_via_brevo_returns_false_on_http_error(monkeypatch):
    monkeypatch.setattr(email_service, "BREVO_API_KEY", "fake-brevo-key")

    def fake_post(*a, **k):
        raise Exception("connection refused")

    monkeypatch.setattr(email_service.requests, "post", fake_post)

    result = email_service._send_via_brevo("someone@example.com", "Subject", "Body", None)
    assert result is False
