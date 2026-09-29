"""Public service status."""

import pytest


@pytest.fixture(autouse=True)
def _clear_status_cache():
    from app.services import status_check
    status_check._cache._store.clear()
    yield
    status_check._cache._store.clear()


def test_classify_http():
    from app.services.status_check import _classify_http
    assert _classify_http(200, 100) == "up"
    assert _classify_http(401, 100) == "up"  # AI API without a key: reachable
    assert _classify_http(429, 100) == "degraded"
    assert _classify_http(200, 5000) == "degraded"
    assert _classify_http(503, 100) == "down"


def test_overall_status_rules():
    from app.services.status_check import overall_status
    up = lambda sid, group: {"id": sid, "group": group, "status": "up"}  # noqa: E731
    assert overall_status([up("backend", "core"), up("coingecko", "data")]) == "up"
    assert overall_status([up("backend", "core"), {"id": "gemini", "group": "ai", "status": "down"}]) == "up"
    assert overall_status([up("backend", "core"), {"id": "coingecko", "group": "data", "status": "down"}]) == "degraded"
    assert overall_status([{"id": "database", "group": "core", "status": "down"}]) == "down"


def test_collect_status_survives_a_crashing_check():
    from app.services.status_check import collect_status

    def boom():
        raise RuntimeError("x")
    result = collect_status([("backend", "core", lambda: ("up", 1)), ("coingecko", "data", boom)])
    assert [s["status"] for s in result["services"]] == ["up", "down"]
    assert result["overall"] == "degraded"


def test_status_endpoint_is_public_and_cached(client, monkeypatch):
    from app.services import status_check
    calls = []

    def fake_http(url):
        calls.append(url)
        return "up", 12
    monkeypatch.setattr(status_check, "_check_http", fake_http)
    first = client.get("/api/public/status")
    assert first.status_code == 200
    body = first.json()
    assert body["overall"] == "up"
    ids = [s["id"] for s in body["services"]]
    assert ids[:2] == ["backend", "database"] and "coingecko" in ids and "gemini" in ids
    client.get("/api/public/status")
    assert len(calls) == len(status_check.HTTP_CHECKS)  # second call served from cache
