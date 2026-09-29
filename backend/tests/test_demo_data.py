"""Generated demo data: test models, synthetic prices, leaderboard, tips and portfolios."""

import statistics
from datetime import datetime, timezone

import pytest

from tests.conftest import anon_csrf_headers, csrf_headers, signed_forecast_payload

LABELS = {"Claude test", "Gemini test", "OpenAI test", "DeepSeek test", "Custom model test", "Grok test"}


def _load(client):
    res = client.post("/api/account/demo-data?lang=sk", headers=csrf_headers(client))
    assert res.status_code == 200, res.text
    return res.json()


def _all_history(client):
    return client.get("/api/forecast/history?page_size=100").json()["items"]


# --------------------------------------------------------------------------- synthetic prices

def test_synthetic_series_is_deterministic_positive_and_anchored():
    from app.services import demo_data as d
    a, b = d.synthetic_series("SOL"), d.synthetic_series("SOL")
    assert a == b and len(a) == d.SERIES_LEN
    assert a[d.PAST_HOURS] == pytest.approx(d.COINS["SOL"][0])
    assert min(a) > 0
    assert d.synthetic_series("ETH") != d.synthetic_series("SOL")


def test_synthetic_prices_stay_in_a_realistic_range():
    from app.services import demo_data as d
    for coin in ("BTC", "DOGE"):
        series = d.synthetic_series(coin)
        base = d.COINS[coin][0]
        assert base / 6 < min(series) and max(series) < base * 6


# ------------------------------------------------------------------------- forecast generation

def _all_forecasts(now):
    from app.services import demo_data as d
    for model, coin, horizon, hours_ago in d._forecast_plan():
        yield model, coin, horizon, hours_ago, d.build_forecast(
            model, coin, horizon, hours_ago, d.synthetic_series(coin), d._floor_hour(now), "en")


def test_forecasts_have_real_shape_band_and_are_not_flat_lines():
    from app.services import demo_data as d
    now = datetime.now(timezone.utc)
    spreads, count = [], 0
    for model, coin, horizon, _ago, data in _all_forecasts(now):
        count += 1
        n = int(d.TIME_HORIZONS[horizon]["points"])
        assert len(data["ceny"]) == len(data["casove_body"]) == len(data["demo_actual"]) == n
        assert all(lo < p < hi for lo, p, hi in zip(data["pasmo"]["dolne"], data["ceny"], data["pasmo"]["horne"]))
        assert data["demo"] is True and data["zdroje_dat"] == ["demo_data"] and model.label in data["odovodnenie"]
        spreads.append((max(data["ceny"]) - min(data["ceny"])) / data["aktualna_cena"])
    assert count == len(d._forecast_plan())
    assert statistics.median(spreads) > 0.03      # the path really moves: not a straight line
    assert min(spreads) > 0.005


def test_forecast_generation_is_reproducible():
    from app.services import demo_data as d
    now = datetime(2026, 9, 29, 12, 34, tzinfo=timezone.utc)
    first = [(m.key, c, h, data["ceny"]) for m, c, h, _a, data in _all_forecasts(now)]
    again = [(m.key, c, h, data["ceny"]) for m, c, h, _a, data in _all_forecasts(now)]
    assert first == again


def test_reasoning_is_localized():
    from app.services import demo_data as d
    series = d.synthetic_series("BTC")
    model = d.DEMO_MODELS[0]
    base = d._floor_hour(datetime.now(timezone.utc))
    assert "Testovacia analýza modelu Claude test" in d.build_forecast(model, "BTC", "1T", 300, series, base, "sk")["odovodnenie"]
    assert "Testovací analýza modelu Claude test" in d.build_forecast(model, "BTC", "1T", 300, series, base, "cs")["odovodnenie"]
    assert "Test analysis by Claude test" in d.build_forecast(model, "BTC", "1T", 300, series, base, "en")["odovodnenie"]


def test_build_forecast_rejects_too_old_creation_time():
    from app.services import demo_data as d
    with pytest.raises(ValueError):
        d.build_forecast(d.DEMO_MODELS[0], "BTC", "1T", d.MAX_HOURS_AGO + 1, d.synthetic_series("BTC"),
                         d._floor_hour(datetime.now(timezone.utc)), "en")


def test_score_forecast_matches_real_accuracy_maths():
    from app.services.ai_engine import score_forecast
    scored = score_forecast([101.0, 102.0], [100.0, 100.0], 100.0)
    assert scored == {"accuracy_pct": 98.5, "baseline_accuracy_pct": 100.0, "direction_correct": True}
    assert score_forecast([1.0], [0.0], 1.0) is None


# ------------------------------------------------------------------------------- the endpoint

def test_load_creates_forecasts_portfolios_evaluations_and_tips(registered):
    from app.services import demo_data as d
    client, _u, _p = registered
    body = _load(client)
    assert body["created"] == len(d._forecast_plan()) and body["portfolios"] == len(d.PORTFOLIO_DAYS_AGO)
    assert body["evaluations"] == 36 and 0 < body["tips"] < 36

    items = _all_history(client)
    assert {i["model_used"] for i in items} == LABELS
    assert all(i["forecast_data"]["demo"] for i in items)
    assert any(i["crypto_symbol"] == "SOL" and i["timeframe"] == "1T" for i in items)

    portfolios = client.get("/api/portfolio/history?page_size=100").json()["items"]
    assert len(portfolios) == 8 and {p["model_used"] for p in portfolios} <= LABELS
    for p in portfolios:
        assert 3 <= len(p["holdings"]) <= 6 and p["analysis_data"]["demo"] is True
        assert {r["akcia"] for r in p["analysis_data"]["odporucania"]} <= {"BUY", "SELL", "HOLD"}
        assert sum(p["analysis_data"]["sektorova_alokacia"].values()) == pytest.approx(100, abs=0.6)


def test_leaderboard_shows_every_test_model_only_to_the_demo_user(registered):
    client, _u, _p = registered
    _load(client)
    board = client.get("/api/forecast/leaderboard").json()
    assert {p["provider"] for p in board["providers"]} == LABELS
    assert all(p["evaluated"] == 6 and p["low_sample"] is False for p in board["providers"])
    assert all(0 <= p["direction_hit_pct"] <= 100 and 0 < p["avg_accuracy_pct"] <= 100 for p in board["providers"])
    you = board["challenge"]["you"]
    assert you["total"] > 0 and you["wins"] + you["losses"] + you["ties"] == you["total"]
    assert board["challenge"]["everyone"]["total"] == 0    # community figures never include demo tips

    client.post("/api/auth/logout", headers=csrf_headers(client))
    client.cookies.clear()
    client.post("/api/auth/register", json={"username": "otheruser", "password": "OtherPass123",
                                             "email": "other@example.com"}, headers=anon_csrf_headers(client))
    other = client.get("/api/forecast/leaderboard").json()
    assert other["providers"] == [] and other["challenge"]["you"]["total"] == 0


def test_demo_never_mixes_into_real_provider_rows(registered):
    client, _u, _p = registered
    client.post("/api/forecast/save", json=signed_forecast_payload(client), headers=csrf_headers(client))
    _load(client)
    providers = {p["provider"] for p in client.get("/api/forecast/leaderboard").json()["providers"]}
    assert providers == LABELS       # the real "Gemini" is not evaluated yet, and never merges with "Gemini test"


def test_matured_demo_forecast_is_scored_and_pending_one_is_not(registered):
    client, _u, _p = registered
    _load(client)
    by_state = {}
    items = _all_history(client)
    # one matured and one pending forecast are enough (the accuracy endpoint is rate limited per user)
    for item in (items[-1], items[0]):      # oldest = matured, newest = still pending
        accuracy = client.get(f"/api/forecast/history/{item['id']}/accuracy").json()
        by_state.setdefault(accuracy["status"], []).append((item, accuracy))
    assert set(by_state) == {"completed", "pending"}
    item, done = by_state["completed"][0]
    n = len(item["forecast_data"]["ceny"])
    assert len(done["actual_prices"]) == n and 0 < done["accuracy_pct"] <= 100 and done["can_tip"] is False
    _item, waiting = by_state["pending"][0]
    assert waiting["actual_prices"] == [] and waiting["can_tip"] is False


def test_opening_history_does_not_change_the_leaderboard(registered):
    client, _u, _p = registered
    _load(client)
    before = client.get("/api/forecast/leaderboard").json()["providers"]
    for item in _all_history(client)[:15]:
        assert client.get(f"/api/forecast/history/{item['id']}/accuracy").status_code == 200
    assert client.get("/api/forecast/leaderboard").json()["providers"] == before


def test_reload_replaces_demo_data_and_delete_keeps_real_data(registered):
    client, _u, _p = registered
    client.post("/api/forecast/save", json=signed_forecast_payload(client), headers=csrf_headers(client))
    first = _load(client)
    total = client.get("/api/forecast/history").json()["total"]
    _load(client)
    assert client.get("/api/forecast/history").json()["total"] == total == first["created"] + 1

    removed = client.delete("/api/account/demo-data", headers=csrf_headers(client)).json()
    assert removed["forecasts"] == first["created"] and removed["portfolios"] == 8
    items = _all_history(client)
    assert len(items) == 1 and items[0]["model_used"] == "Gemini"
    assert client.get("/api/portfolio/history").json()["total"] == 0
    board = client.get("/api/forecast/leaderboard").json()
    assert board["providers"] == [] and board["challenge"]["you"]["total"] == 0


def test_demo_forecasts_cannot_be_shared_or_tipped_into_community_stats(registered):
    client, _u, _p = registered
    _load(client)
    entry = _all_history(client)[0]
    assert client.post(f"/api/forecast/history/{entry['id']}/share", headers=csrf_headers(client)).status_code == 400


def test_demo_tip_submitted_by_the_user_is_flagged_and_excluded_from_community(registered):
    """A tip on a demo forecast (only possible right after creation) must not reach the community stats."""
    from app.database import SessionLocal
    from app.models import ForecastHistory, PriceTip
    client, _u, _p = registered
    _load(client)
    with SessionLocal() as db:
        row = db.query(ForecastHistory).filter(ForecastHistory.model_used == "Grok test").first()
        db.add(PriceTip(user_id=row.user_id, forecast_id=row.id, tip_price=1.0, ai_price=2.0, outcome="win", is_demo=True))
        db.commit()
    assert client.get("/api/forecast/leaderboard").json()["challenge"]["everyone"]["total"] == 0


def test_demo_data_requires_login_and_is_logged(client, registered):
    assert client.post("/api/account/demo-data", headers=csrf_headers(client)).status_code in (200, 401)
    _client, _u, _p = registered
    _load(client)
    events = client.get("/api/account/activity").json()["events"]
    assert events[0]["action"] == "demo_data_loaded" and "56 forecasts" in events[0]["details"]


def test_anonymous_cannot_load_demo_data(client):
    res = client.post("/api/account/demo-data", headers=anon_csrf_headers(client))
    assert res.status_code == 401


def test_new_columns_are_added_to_an_existing_database(tmp_path, monkeypatch):
    """Existing installs must gain the is_demo columns automatically (auto_migrate)."""
    import sqlalchemy as sa
    from app import database
    engine = sa.create_engine(f"sqlite:///{tmp_path/'old.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE forecast_evaluations (id INTEGER PRIMARY KEY, forecast_id INTEGER, user_id INTEGER,"
                             " provider VARCHAR(32), coin VARCHAR(16), timeframe VARCHAR(8), accuracy_pct FLOAT,"
                             " baseline_accuracy_pct FLOAT, direction_correct BOOLEAN, actual_final_price FLOAT, evaluated_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE price_tips (id INTEGER PRIMARY KEY, user_id INTEGER, forecast_id INTEGER,"
                             " tip_price FLOAT, ai_price FLOAT, outcome VARCHAR(8), created_at DATETIME)"))
        conn.execute(sa.text("INSERT INTO price_tips (user_id, forecast_id, tip_price, ai_price) VALUES (1, 1, 1.0, 2.0)"))
    monkeypatch.setattr(database, "engine", engine)
    database.auto_migrate()
    cols = {t: {c["name"] for c in sa.inspect(engine).get_columns(t)} for t in ("forecast_evaluations", "price_tips")}
    assert "is_demo" in cols["forecast_evaluations"] and "is_demo" in cols["price_tips"]
    with engine.connect() as conn:       # old rows stay NULL = "not demo" and keep counting in community stats
        assert conn.execute(sa.text("SELECT is_demo FROM price_tips")).scalar() is None


def test_portfolio_demo_is_believable():
    from app.services import demo_data as d
    for index in range(len(d.PORTFOLIO_DAYS_AGO)):
        holdings, analysis = d.build_portfolio(index, d.DEMO_MODELS[index % 6], "en")
        actions = [r["akcia"] for r in analysis["odporucania"]]
        assert not (len(actions) > 2 and set(actions) == {"SELL"})
        for rec in analysis["odporucania"]:      # wording must match the size of the position
            share = int(rec["dovod"].split("%")[0].split("(")[-1].split(" ")[-1]) if "%" in rec["dovod"] else None
            if rec["akcia"] == "SELL" and share is not None and share < 15:
                assert "small position" in rec["dovod"]
            assert "has run hot" not in rec["dovod"] or (share or 100) >= 15
        assert 3 <= len(holdings) <= 6 and all(h["mnozstvo"] > 0 for h in holdings)


def test_demo_tips_are_a_close_contest_not_a_walkover(registered):
    client, _u, _p = registered
    body = _load(client)
    you = client.get("/api/forecast/leaderboard").json()["challenge"]["you"]
    assert you["total"] == body["tips"] and you["wins"] >= 1 and you["losses"] >= 1
    assert 0.2 <= you["wins"] / you["total"] <= 0.8
