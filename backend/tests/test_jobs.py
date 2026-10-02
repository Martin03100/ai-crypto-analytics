"""Background AI jobs: async clients get a job id and poll for the result."""

from __future__ import annotations

import time

from app.services import jobs
from tests.conftest import csrf_headers

ASYNC = {"Prefer": "respond-async"}


def _poll(client, job_id, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] == "done":
            return body["result"]
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_forecast_runs_as_a_job_and_stays_signed(registered, monkeypatch):
    from app.routers import forecast as forecast_router
    from app.services.ai_engine import AIEngineResult
    client, _u, _p = registered
    data = {"ceny": [1.0, 2.0], "casove_body": ["a", "b"], "odovodnenie": "x", "vytvorene": "2026-10-01T00:00:00+00:00"}
    monkeypatch.setattr(forecast_router, "get_coin_forecast", lambda *a: AIEngineResult(True, dict(data), False))
    res = client.post("/api/forecast", json={"provider": "quant", "coin": "BTC", "horizon": "1T"},
                      headers={**csrf_headers(client), **ASYNC})
    assert res.status_code == 202
    result = _poll(client, res.json()["job_id"])
    assert result["success"] is True and result["data"]["podpis"]
    saved = client.post("/api/forecast/save", json={"provider": "quant", "coin": "BTC", "horizon": "1T",
                                                     "forecast_data": result["data"]}, headers=csrf_headers(client))
    assert saved.status_code == 201


def test_without_prefer_header_the_response_is_inline(registered, monkeypatch):
    from app.routers import forecast as forecast_router
    from app.services.ai_engine import AIEngineResult
    client, _u, _p = registered
    monkeypatch.setattr(forecast_router, "get_coin_forecast",
                        lambda *a: AIEngineResult(True, {"ceny": [1.0], "vytvorene": "x"}, False))
    res = client.post("/api/forecast", json={"provider": "quant", "coin": "BTC", "horizon": "1T"}, headers=csrf_headers(client))
    assert res.status_code == 200 and res.json()["success"] is True


def test_jobs_are_private_and_failures_still_answer(registered, client):
    c, _u, _p = registered
    owner_job = jobs.submit(999_999, lambda: {"secret": True})
    assert c.get(f"/api/jobs/{owner_job}").status_code == 404          # someone else's job
    me = c.get("/api/auth/me").json()["user_id"]
    failing = jobs.submit(me, lambda: 1 / 0)
    result = _poll(c, failing)
    assert result["success"] is False and "neočakávaná" in result["error_message"]
    assert c.get("/api/jobs/" + "x" * 22).status_code == 404


def test_running_jobs_are_capped_per_user(monkeypatch):
    import threading
    gate = threading.Event()
    ids = [jobs.submit(4242, lambda: gate.wait(5) or {}) for _ in range(jobs.MAX_RUNNING_PER_USER)]
    try:
        try:
            jobs.submit(4242, lambda: {})
            raise AssertionError("expected 429")
        except Exception as exc:  # noqa: BLE001
            assert getattr(exc, "status_code", None) == 429
    finally:
        gate.set()
    assert len(ids) == jobs.MAX_RUNNING_PER_USER
