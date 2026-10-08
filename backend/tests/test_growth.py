"""Public track record and the Premium waitlist."""

from app.database import SessionLocal
from app.models import ForecastEvaluation, WaitlistEntry
from tests.conftest import anon_csrf_headers


def _add_evaluations(rows):
    db = SessionLocal()
    try:
        for i, (provider, correct, accuracy, demo) in enumerate(rows):
            db.add(ForecastEvaluation(forecast_id=i + 1, user_id=1, provider=provider, coin="BTC", timeframe="1T",
                                      accuracy_pct=accuracy, baseline_accuracy_pct=95.0, direction_correct=correct,
                                      actual_final_price=1.0, is_demo=True if demo else None))
        db.commit()
    finally:
        db.close()


def _waitlist():
    db = SessionLocal()
    try:
        return db.query(WaitlistEntry).all()
    finally:
        db.close()


def test_track_record_is_public_and_empty_at_start(client):
    res = client.get("/api/public/track-record")
    assert res.status_code == 200
    body = res.json()
    assert body["providers"] == [] and body["recent"] == []
    assert body["totals"] == {"evaluated": 0, "direction_hit_pct": None, "direction_ci": None, "beats_baseline_pct": None}


def test_track_record_aggregates_real_forecasts_and_hides_demo_and_users(client):
    _add_evaluations([("Gemini", True, 97.0, False), ("Gemini", False, 90.0, False), ("Gemini", True, 96.0, False),
                      ("Claude", True, 99.0, False), ("Gemini test", True, 99.0, True)])
    body = client.get("/api/public/track-record").json()
    assert body["totals"]["evaluated"] == 4
    assert body["totals"]["direction_hit_pct"] == 75.0
    assert body["totals"]["beats_baseline_pct"] == 75.0
    names = [p["provider"] for p in body["providers"]]
    assert "Gemini test" not in names and set(names) == {"Gemini", "Claude"}
    gemini = next(p for p in body["providers"] if p["provider"] == "Gemini")
    assert gemini["evaluated"] == 3 and gemini["direction_hit_pct"] == 66.7 and gemini["low_sample"] is True
    assert len(body["recent"]) == 4
    assert set(body["recent"][0]) == {"coin", "horizon", "provider", "direction_correct", "accuracy_pct", "error_pct",
                                      "evaluated_at"}
    assert "user" not in str(body).lower()


def test_track_record_lists_at_most_ten_recent(client):
    _add_evaluations([("Gemini", True, 97.0, False)] * 14)
    assert len(client.get("/api/public/track-record").json()["recent"]) == 10


def test_waitlist_signup_works_without_login(client):
    res = client.post("/api/public/waitlist", json={"email": " Fan@Example.com ", "lang": "sk", "source": "TikTok"},
                      headers=anon_csrf_headers(client))
    assert res.status_code == 200 and res.json() == {"success": True}
    [entry] = _waitlist()
    assert entry.email == "fan@example.com" and entry.lang == "sk" and entry.source == "tiktok"


def test_waitlist_duplicate_gives_same_answer_and_is_stored_once(client):
    headers = anon_csrf_headers(client)
    first = client.post("/api/public/waitlist", json={"email": "fan@example.com"}, headers=headers)
    second = client.post("/api/public/waitlist", json={"email": "FAN@example.com"}, headers=headers)
    assert first.json() == second.json() == {"success": True}
    assert len(_waitlist()) == 1


def test_waitlist_rejects_invalid_input(client):
    headers = anon_csrf_headers(client)
    assert client.post("/api/public/waitlist", json={"email": "not-an-email"}, headers=headers).status_code == 400
    assert client.post("/api/public/waitlist", json={"email": "a@b.co", "lang": "fr"}, headers=headers).status_code == 422
    assert client.post("/api/public/waitlist", json={"email": "a@b.co", "source": "<script>"},
                       headers=headers).status_code == 422
    assert _waitlist() == []


def test_waitlist_requires_csrf_token(client):
    assert client.post("/api/public/waitlist", json={"email": "fan@example.com"}).status_code == 403


def test_waitlist_is_rate_limited(client):
    headers = anon_csrf_headers(client)
    codes = [client.post("/api/public/waitlist", json={"email": f"fan{i}@example.com"}, headers=headers).status_code
             for i in range(7)]
    assert codes[:5] == [200] * 5 and codes[-1] == 429
