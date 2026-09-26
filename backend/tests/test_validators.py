"""Testy pre app/services/validators.py — cisto funkcionalne, bez DB/siete."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.validators import (  # noqa: E402
    GLOBAL_CONTEXT_INSTRUCTION, build_daily_digest_prompt, build_forecast_prompt,
    build_news_prompt, build_portfolio_prompt, safe_json_loads,
    validate_digest_payload, validate_forecast_payload, validate_news_payload,
    validate_portfolio_payload,
)


def test_safe_json_loads_valid():
    ok, data, err = safe_json_loads('{"a": 1}')
    assert ok is True
    assert data == {"a": 1}
    assert err is None


def test_safe_json_loads_strips_markdown_fence():
    ok, data, err = safe_json_loads('```json\n{"a": 1}\n```')
    assert ok is True
    assert data == {"a": 1}


def test_safe_json_loads_invalid_returns_error():
    ok, data, err = safe_json_loads("not json at all")
    assert ok is False
    assert data is None
    assert err


def test_forecast_prompt_includes_global_context():
    prompt = build_forecast_prompt("BTC", "1T", 7)
    assert "BTC" in prompt
    assert GLOBAL_CONTEXT_INSTRUCTION in prompt
    assert "confidence_score" in prompt
    assert "risk_level" in prompt


def test_forecast_prompt_includes_real_market_data_when_provided():
    """Bez realnej ceny/trendu model nemal ziadnu kotvu a predikcie posobili
    systematicky prilis optimisticky - musi byt jasne vlozena do promptu."""
    ctx = "Aktualna cena: $64,280.00 USD | Zmena za 24h: -2.15% | Zmena za poslednych 7 dni: -5.30%"
    prompt = build_forecast_prompt("BTC", "1T", 7, market_context=ctx)
    assert ctx in prompt


def test_forecast_prompt_instructs_against_default_optimism():
    prompt = build_forecast_prompt("BTC", "1T", 7)
    assert "pokles" in prompt.lower()
    assert "optimizmus" in prompt.lower()


def test_portfolio_prompt_includes_global_context():
    prompt = build_portfolio_prompt([{"minca": "BTC", "mnozstvo": 1}])
    assert GLOBAL_CONTEXT_INSTRUCTION in prompt


def test_portfolio_prompt_instructs_against_always_buy():
    prompt = build_portfolio_prompt([{"minca": "BTC", "mnozstvo": 1}])
    assert "SELL" in prompt and "HOLD" in prompt


def test_news_prompt_includes_global_context():
    prompt = build_news_prompt(["Bitcoin rastie"])
    assert GLOBAL_CONTEXT_INSTRUCTION in prompt


def test_daily_digest_prompt_includes_global_context():
    prompt = build_daily_digest_prompt(71, "Greed", ["Nejaka sprava"])
    assert GLOBAL_CONTEXT_INSTRUCTION in prompt
    assert "71" in prompt


def test_validate_forecast_payload_valid():
    payload = json.dumps({
        "ceny": [1.0, 2.0], "casove_body": ["deň 1", "deň 2"],
        "odovodnenie": "test", "confidence_score": 80, "risk_level": "Low",
    })
    ok, data, err = validate_forecast_payload(payload)
    assert ok is True
    assert data["risk_level"] == "Low"


def test_validate_forecast_payload_rejects_bad_risk_level():
    payload = json.dumps({
        "ceny": [1.0], "casove_body": ["deň 1"],
        "odovodnenie": "test", "confidence_score": 80, "risk_level": "Extreme",
    })
    ok, data, err = validate_forecast_payload(payload)
    assert ok is False
    assert err


def test_validate_forecast_payload_rejects_missing_keys():
    ok, data, err = validate_forecast_payload(json.dumps({"ceny": [1.0]}))
    assert ok is False


def test_validate_portfolio_payload_valid():
    payload = json.dumps({
        "odporucania": [{"minca": "BTC", "akcia": "HOLD", "dovod": "test"}],
        "odborna_analyza": "test",
        "sektorova_alokacia": {"DeFi": 10, "L1/L2": 90, "AI": 0, "Memes": 0, "Other": 0},
        "rebalancing_checklist": ["krok 1"],
    })
    ok, data, err = validate_portfolio_payload(payload)
    assert ok is True


def test_validate_news_payload_valid():
    payload = json.dumps({
        "spravy": [{"titulok": "test", "sentiment": "Bullish"}],
        "trendy": ["trend 1"],
    })
    ok, data, err = validate_news_payload(payload)
    assert ok is True


def test_validate_digest_payload_valid():
    payload = json.dumps({"zhrnutie": "test summary", "kluceve_body": ["bod 1"]})
    ok, data, err = validate_digest_payload(payload)
    assert ok is True


def test_validate_digest_payload_rejects_empty_summary():
    payload = json.dumps({"zhrnutie": "", "kluceve_body": ["bod 1"]})
    ok, data, err = validate_digest_payload(payload)
    assert ok is False



def test_forecast_prompt_defines_real_timing():
    assert "bod c. 1 je cena o 1 hodinu od TERAZ" in build_forecast_prompt("BTC", "24h", 24)


def test_history_timestamps_are_serialized_as_utc():
    from datetime import datetime
    from app.schemas import ForecastHistoryOut
    out = ForecastHistoryOut(id=1, crypto_symbol="BTC", timeframe="24h", model_used="x",
                             forecast_data={}, created_at=datetime(2026, 9, 26, 7, 0))
    assert "2026-09-26T07:00:00+00:00" in out.model_dump_json()
