"""Self-ping that keeps the free Render instance awake."""

from __future__ import annotations

from app.services import keep_awake


def test_only_active_on_render_with_https(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    assert keep_awake.ping_url() is None
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "http://insecure.example")
    assert keep_awake.ping_url() is None
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://ai-crypto-analytics.onrender.com/")
    assert keep_awake.ping_url() == "https://ai-crypto-analytics.onrender.com/api/health"
    monkeypatch.setenv("KEEP_AWAKE", "0")
    assert keep_awake.ping_url() is None


def test_ping_reports_failures_without_raising(monkeypatch):
    import requests

    class Resp:
        status_code = 200

    monkeypatch.setattr(keep_awake.requests, "get", lambda url, timeout: Resp())
    assert keep_awake.ping("https://x/api/health") is True

    def boom(url, timeout):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(keep_awake.requests, "get", boom)
    assert keep_awake.ping("https://x/api/health") is False
