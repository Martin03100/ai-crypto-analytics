"""Statistical model tests."""

import math
import random

from tests.conftest import csrf_headers


def _series(n=720, sigma=0.01, seed=1, drift=0.0):
    rng = random.Random(seed)
    price, out = 100.0, []
    for i in range(n):
        price *= math.exp(drift + sigma * rng.gauss(0, 1))
        out.append([i * 3_600_000, price])
    return out


def _patch_history(monkeypatch, prices):
    from app.services import market_data
    monkeypatch.setattr(market_data, "get_market_history",
                        lambda *a, **k: (True, {"prices": prices, "volumes": []}, None))


def test_quant_forecast_shape_and_band(monkeypatch):
    from app.services import quant_engine
    _patch_history(monkeypatch, _series())
    ok, data, err = quant_engine.build_quant_forecast("BTC", "1T", "en")
    assert ok and err is None
    assert len(data["ceny"]) == len(data["casove_body"]) == 7
    assert all(lo < p < hi for lo, p, hi in zip(data["pasmo"]["dolne"], data["ceny"], data["pasmo"]["horne"]))
    widths = [hi - lo for lo, hi in zip(data["pasmo"]["dolne"], data["pasmo"]["horne"])]
    assert widths == sorted(widths)
    assert data["risk_level"] in ("Low", "Medium", "High") and 0 <= data["confidence_score"] <= 100
    assert "quant_model" in data["zdroje_dat"]


def test_quant_drift_is_capped(monkeypatch):
    from app.services import quant_engine
    _patch_history(monkeypatch, _series(drift=0.01))
    ok, data, _ = quant_engine.build_quant_forecast("BTC", "1M", "en")
    spot = data["aktualna_cena"]
    sigma_h = quant_engine.estimate_sigma_per_hour(_series(drift=0.01))
    h = 24 * 30
    sigma_t = math.sqrt(sigma_h ** 2 * h + quant_engine._JUMP_VARIANCE_FLOOR)
    cap = 0.35 * sigma_t
    assert data["ceny"][-1] <= spot * math.exp(cap) * 1.0001


def test_quant_needs_enough_data_and_supported_coin(monkeypatch):
    from app.services import quant_engine
    _patch_history(monkeypatch, _series(n=10))
    assert quant_engine.build_quant_forecast("BTC", "1T", "en")[0] is False
    _patch_history(monkeypatch, _series())
    assert quant_engine.build_quant_forecast("NOTACOIN", "1T", "en")[0] is False
    assert quant_engine.build_quant_forecast("BTC", "5y", "en")[0] is False


def test_quant_ignores_garbage_points(monkeypatch):
    from app.services import quant_engine
    dirty = _series() + [[1, "x"], [None, 5], [10**12, -3], [10**12, float("nan")]]
    _patch_history(monkeypatch, dirty)
    assert quant_engine.build_quant_forecast("ETH", "24h", "sk")[0] is True


def test_quant_endpoint_works_without_api_key_and_is_signed_and_savable(registered, monkeypatch):
    client, _u, _p = registered
    _patch_history(monkeypatch, _series())
    res = client.post("/api/forecast", json={"provider": "quant", "coin": "BTC", "horizon": "1T", "lang": "sk"},
                      headers=csrf_headers(client))
    body = res.json()
    assert res.status_code == 200 and body["success"] and body["is_mock"] is False
    assert body["data"]["podpis"]
    assert "Bezplatný" in body["data"]["odovodnenie"]
    saved = client.post("/api/forecast/save", json={"provider": "quant", "coin": "BTC", "horizon": "1T",
                                                    "forecast_data": body["data"], "is_mock": False},
                        headers=csrf_headers(client))
    assert saved.status_code == 201
    assert saved.json()["model_used"] == "Quant (free model)"


def test_quant_result_cannot_be_saved_as_another_provider(registered, monkeypatch):
    client, _u, _p = registered
    _patch_history(monkeypatch, _series())
    body = client.post("/api/forecast", json={"provider": "quant", "coin": "BTC", "horizon": "1T"},
                       headers=csrf_headers(client)).json()
    res = client.post("/api/forecast/save", json={"provider": "gemini", "coin": "BTC", "horizon": "1T",
                                                  "forecast_data": body["data"], "is_mock": False},
                      headers=csrf_headers(client))
    assert res.status_code == 400


def test_quant_endpoint_returns_error_not_500_when_data_unavailable(registered, monkeypatch):
    from app.services import market_data
    client, _u, _p = registered
    monkeypatch.setattr(market_data, "get_market_history", lambda *a, **k: (False, {}, "siet nedostupna"))
    res = client.post("/api/forecast", json={"provider": "quant", "coin": "BTC", "horizon": "1T"},
                      headers=csrf_headers(client))
    assert res.status_code == 200 and res.json()["success"] is False


def test_unknown_provider_is_rejected_by_forecast_endpoint(registered):
    client, _u, _p = registered
    res = client.post("/api/forecast", json={"provider": "hackerAI", "coin": "BTC", "horizon": "1T"},
                      headers=csrf_headers(client))
    assert res.status_code == 400


def test_attach_uncertainty_band_to_ai_forecast():
    from app.services import quant_engine
    parsed = {"ceny": [100.0] * 24}
    quant_engine.attach_uncertainty_band(parsed, _series(), "24h")
    assert len(parsed["pasmo"]["dolne"]) == 24 and parsed["denna_volatilita_pct"] > 0
    empty = {"ceny": [1.0]}
    quant_engine.attach_uncertainty_band(empty, [], "24h")
    assert "pasmo" not in empty
