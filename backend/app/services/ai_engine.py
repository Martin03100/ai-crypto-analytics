"""AI engine: forecasts, portfolio analysis, news, digest and chat on top of the providers (ai_providers),
the market data for the prompts (ai_context) and the free statistical model, with honest fallbacks."""

from __future__ import annotations

import json
import logging
import math
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import (
    DEFAULT_COIN_IDS, HORIZON_HOURS, QUANT_PROVIDER,
    MOCK_BASE_PRICES, PROVIDER_TOKEN_PRICE_USD_PER_1K,
    SECTOR_CATEGORIES, TIME_HORIZONS,
)
from app.services import free_digest, market_data, quant_engine, signals
from app.services.validators import (
    language_instruction,
    build_daily_digest_prompt, build_forecast_prompt, build_news_prompt, build_portfolio_prompt,
    validate_digest_payload, validate_forecast_payload, validate_news_payload, validate_portfolio_payload,
)
from app.i18n_content import (
    missing_api_key_message, mock_chat_reply, mock_forecast_reasoning, sample_portfolio_reason, unit_label,
    MOCK_PORTFOLIO_ANALYSIS_TEXT, MOCK_REBALANCING_CHECKLIST, normalize_lang,
)

from app.services.ai_context import (
    _MARKET_CONTEXT_TIMEOUT, _build_market_context, _build_portfolio_context, market_signals_block,
)
from app.services.ai_providers import _call_ai_provider_raw, validate_custom_base_url  # noqa: F401 - public API

logger = logging.getLogger("aca.ai")


class AIEngineResult:
    def __init__(self, success: bool, data: Optional[Dict[str, Any]], is_mock: bool,
                 error_message: Optional[str] = None, provider_used: Optional[str] = None) -> None:
        self.success = success
        self.data = data
        self.is_mock = is_mock
        self.error_message = error_message
        # Set when a different provider than the requested one produced the data (e.g. quant fallback).
        self.provider_used = provider_used

    def as_dict(self) -> Dict[str, Any]:
        from app.error_codes import lookup
        found = lookup(self.error_message)
        return {
            "success": self.success, "data": self.data,
            "is_mock": self.is_mock, "error_message": self.error_message,
            "provider_used": self.provider_used,
            "error_code": found[0] if found else None, "error_params": found[1] if found else None,
        }


def _generate_mock_forecast(coin: str, horizon: str, lang: str = "en") -> Dict[str, Any]:
    horizon_config = TIME_HORIZONS.get(horizon, {"points": 7, "unit": "den"})
    points = int(horizon_config["points"])
    unit_key = str(horizon_config["unit"])
    unit = unit_label(unit_key, lang)
    base_price = MOCK_BASE_PRICES.get(coin, 100.0)

    rng = random.Random(f"{coin}-{horizon}")
    prices: List[float] = []
    current = base_price
    for _ in range(points):
        current = max(0.0001, current * (1 + rng.uniform(-0.04, 0.045)))
        prices.append(float(f"{current:.8g}"))

    time_labels = [f"{unit} {i + 1}" for i in range(points)]
    trend_direction = "up" if prices[-1] >= prices[0] else "down"
    volatility = abs(prices[-1] - prices[0]) / max(prices[0], 0.0001)
    risk_level = "High" if volatility > 0.25 else "Medium" if volatility > 0.1 else "Low"
    confidence_score = round(max(35.0, min(92.0, 90 - volatility * 100)), 1)

    return {
        "ceny": prices,
        "casove_body": time_labels,
        "odovodnenie": mock_forecast_reasoning(coin, horizon, trend_direction, lang),
        "confidence_score": confidence_score,
        "risk_level": risk_level,
    }


# Sector of the supported coins, for the sample analysis (no AI key): real composition instead of invented weights.
_COIN_SECTORS = {
    "UNI": "DeFi", "LINK": "DeFi", "DOGE": "Memes", "SHIB": "Memes", "PEPE": "Memes",
    **{c: "L1/L2" for c in ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOT", "TON", "TRX", "LTC", "BCH", "SUI",
                            "NEAR", "APT")},
}


def _generate_mock_portfolio_analysis(holdings: List[Dict[str, Any]], lang: str = "en") -> Dict[str, Any]:
    """Sample shown without an AI key. It must not look like advice: every position is a neutral HOLD with a note
    that no analysis was done, and the sector split is the real one (by number of coins)."""
    recommendations = [{"minca": item.get("minca", "N/A"), "akcia": "HOLD",
                        "dovod": sample_portfolio_reason(str(item.get("minca", "N/A")), lang)} for item in holdings]
    counts = {s: 0 for s in SECTOR_CATEGORIES}
    for item in holdings:
        counts[_COIN_SECTORS.get(str(item.get("minca", "")).upper(), "Other")] += 1
    total = sum(counts.values()) or 1
    lang = normalize_lang(lang)
    return {
        "odporucania": recommendations,
        "odborna_analyza": MOCK_PORTFOLIO_ANALYSIS_TEXT[lang],
        "sektorova_alokacia": {s: round(n / total * 100, 1) for s, n in counts.items()},
        "rebalancing_checklist": MOCK_REBALANCING_CHECKLIST[lang],
    }


def compute_forecast_accuracy(coin: str, timeframe: str, predicted_prices: List[float],
                               time_labels: List[str], created_at: datetime) -> Dict[str, Any]:
    horizon_hours = HORIZON_HOURS.get(timeframe, 7 * 24)
    if (not isinstance(predicted_prices, list)
            or not all(isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) for p in predicted_prices)):
        predicted_prices = []
    created_at_utc = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    target_end = created_at_utc + timedelta(hours=horizon_hours)
    now = datetime.now(timezone.utc)

    base = {"predicted_prices": predicted_prices, "time_labels": time_labels, "matures_at": target_end.isoformat()}

    if now < target_end:
        return {**base, "status": "pending", "accuracy_pct": None, "actual_prices": []}

    coin_id = DEFAULT_COIN_IDS.get(coin.upper())
    if not coin_id:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": []}

    try:
        ok, chart, _ = market_data.get_market_chart_range(
            coin_id, "usd", int(created_at_utc.timestamp()), int(target_end.timestamp())
        )
    except Exception:  # noqa: BLE001
        ok, chart = False, []

    if not ok or len(chart) < 2:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": []}

    n = len(predicted_prices)
    if n == 0:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": []}
    start_ms, end_ms = created_at_utc.timestamp() * 1000, target_end.timestamp() * 1000
    actual_prices: List[float] = []
    for i in range(n):
        target_ts = start_ms + (end_ms - start_ms) * (i + 1) / n
        closest = min(chart, key=lambda p: abs(p[0] - target_ts))
        actual_prices.append(closest[1])

    scored = score_forecast(predicted_prices, actual_prices, chart[0][1])
    if scored is None:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": actual_prices}
    return {**base, "status": "completed", "actual_prices": actual_prices, "start_price": chart[0][1], **scored}


def score_forecast(predicted_prices: List[float], actual_prices: List[float],
                   start_price: float) -> Optional[Dict[str, Any]]:
    """Accuracy of a forecast against the real prices at the same points.

    accuracy = 100 - mean absolute percentage error; the baseline is the naive forecast "the price stays
    at the start price". Returns None when nothing can be compared."""
    n = min(len(predicted_prices), len(actual_prices))
    errors = [abs(predicted_prices[i] - actual_prices[i]) / actual_prices[i] for i in range(n) if actual_prices[i]]
    if not errors:
        return None
    accuracy_pct = round(max(0.0, 100.0 - (sum(errors) / len(errors)) * 100), 1)
    baseline_errors = [abs(start_price - a) / a for a in actual_prices[:n] if a]
    baseline_pct = round(max(0.0, 100.0 - sum(baseline_errors) / len(baseline_errors) * 100), 1) if baseline_errors else None
    direction_correct = (predicted_prices[n - 1] >= start_price) == (actual_prices[n - 1] >= start_price)
    return {"accuracy_pct": accuracy_pct, "baseline_accuracy_pct": baseline_pct, "direction_correct": direction_correct}


def _forecast_fallback(coin: str, horizon: str, lang: str, reason: Optional[str]) -> AIEngineResult:
    """AI provider failed (quota, outage, unusable output): prefer the free statistical model,
    which works on real market data, over sample data. Sample data stays the last resort."""
    ok, data, _quant_error = quant_engine.build_quant_forecast(coin, horizon, lang)
    if ok and data:
        return AIEngineResult(True, data, False, reason, provider_used=QUANT_PROVIDER)
    return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True, reason)


def get_coin_forecast(provider: str, coin: str, horizon: str, api_key: Optional[str], lang: str = "en") -> AIEngineResult:
    if provider == QUANT_PROVIDER:
        ok, data, error = quant_engine.build_quant_forecast(coin, horizon, lang)
        if not ok:
            return AIEngineResult(False, None, False, error)
        return AIEngineResult(True, data, False)

    if not api_key:
        return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True,
                               missing_api_key_message(lang))

    points = int(TIME_HORIZONS.get(horizon, {"points": 7})["points"])
    market_context, sources_used = _build_market_context(coin)
    prompt = build_forecast_prompt(coin, horizon, points, market_context) + language_instruction(lang)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return _forecast_fallback(coin, horizon, lang, call_error)

    is_valid, parsed, validation_error = validate_forecast_payload(raw_text, expected_points=points)
    if not is_valid or parsed is None:
        return _forecast_fallback(coin, horizon, lang, validation_error)

    parsed["zdroje_dat"] = sources_used
    parsed["signaly"] = _used_signals(coin)
    parsed["vytvorene"] = datetime.now(timezone.utc).isoformat()
    if market_context:
        ok, history, _ = market_data.get_market_history(DEFAULT_COIN_IDS[coin.upper()], 30, _MARKET_CONTEXT_TIMEOUT)
        if ok and history.get("prices"):
            parsed["aktualna_cena"] = history["prices"][-1][1]
            quant_engine.attach_uncertainty_band(parsed, history["prices"], horizon)
    return AIEngineResult(True, parsed, False)


def get_portfolio_analysis(provider: str, holdings: List[Dict[str, Any]], api_key: Optional[str],
                            lang: str = "en") -> AIEngineResult:
    if not holdings:
        return AIEngineResult(False, None, False, "Portfolio je prazdne - pridaj aspon jednu mincu.")

    if not api_key:
        return AIEngineResult(True, _generate_mock_portfolio_analysis(holdings, lang), True,
                               missing_api_key_message(lang))

    portfolio_context, sources_used = _build_portfolio_context(holdings)
    prompt = build_portfolio_prompt(holdings, portfolio_context) + language_instruction(lang)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    # A failed AI call is reported as such: invented BUY/SELL ratings for someone's real holdings are never shown.
    if not success:
        return AIEngineResult(False, None, False, call_error)

    is_valid, parsed, validation_error = validate_portfolio_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(False, None, False, validation_error)

    parsed["zdroje_dat"] = sources_used
    parsed["signaly"] = _used_signals("BTC")
    return AIEngineResult(True, parsed, False)


def _used_signals(symbol: str) -> List[Dict[str, Any]]:
    """The exact signal values the model saw, kept with the result so users can check them."""
    try:
        bundle = signals.latest(symbol) or signals.collect(symbol)
        return [{k: s[k] for k in ("group", "key", "display", "tone", "source", "meta") if k in s} for s in bundle["items"]]
    except Exception:  # noqa: BLE001
        return []


def get_news_sentiment_summary(provider: str, headlines: List[str], api_key: Optional[str],
                                lang: str = "en") -> AIEngineResult:
    if not headlines:
        return AIEngineResult(False, None, False, "Ziadne titulky na analyzu.")

    # Without a working AI there is no sentiment: random labels on real headlines would mislead.
    if not api_key:
        return AIEngineResult(False, None, False, missing_api_key_message(lang))

    block = market_signals_block("BTC")
    prompt = build_news_prompt(headlines) + (f"\n\n{block}" if block else "") + language_instruction(lang)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(False, None, False, call_error)

    is_valid, parsed, validation_error = validate_news_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(False, None, False, validation_error)

    return AIEngineResult(True, parsed, False)


FREE_DIGEST_PROVIDER = "free"


def get_daily_digest(provider: str, fg_value: int, fg_classification: str,
                      headlines: List[str], api_key: Optional[str], lang: str = "en") -> AIEngineResult:
    """The AI morning overview; without a key (or when the AI fails) a plain overview built from live data."""
    if not api_key:
        return AIEngineResult(True, free_digest.build(fg_value, fg_classification, lang), False, None,
                              provider_used=FREE_DIGEST_PROVIDER)

    block = market_signals_block("BTC")
    prompt = (build_daily_digest_prompt(fg_value, fg_classification, headlines) + (f"\n\n{block}" if block else "")
              + language_instruction(lang))
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(True, free_digest.build(fg_value, fg_classification, lang), False, call_error,
                              provider_used=FREE_DIGEST_PROVIDER)

    is_valid, parsed, validation_error = validate_digest_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(True, free_digest.build(fg_value, fg_classification, lang), False, validation_error,
                              provider_used=FREE_DIGEST_PROVIDER)

    return AIEngineResult(True, parsed, False)


def test_api_key(provider: str, api_key: str) -> tuple[bool, Optional[str]]:
    if not api_key or not api_key.strip():
        return False, "API kluc je prazdny."
    success, _text, error = call_ai_provider(provider, "Odpovedz jednym slovom: OK", api_key.strip())
    if not success:
        return False, error or "Kluc sa nepodarilo overit."
    return True, None


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def _estimate_cost_usd(provider: str, total_tokens: int) -> float:
    price_per_1k = PROVIDER_TOKEN_PRICE_USD_PER_1K.get(provider, 0.0008)
    return round((total_tokens / 1000) * price_per_1k, 6)


def estimate_forecast_cost(provider: str, coin: str, horizon: str) -> Dict[str, Any]:
    points = int(TIME_HORIZONS.get(horizon, {"points": 7})["points"])
    prompt = build_forecast_prompt(coin, horizon, points, market_context=None)
    input_tokens = _estimate_tokens(prompt) + 450
    expected_output_tokens = 150 + points * 12
    total_tokens = input_tokens + expected_output_tokens
    return {
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": expected_output_tokens,
        "estimated_total_tokens": total_tokens,
        "estimated_cost_usd": _estimate_cost_usd(provider, total_tokens),
    }


def estimate_portfolio_cost(provider: str, holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = build_portfolio_prompt(holdings)
    input_tokens = _estimate_tokens(prompt) + 150 + 60 * len(holdings)
    expected_output_tokens = 150 + max(1, len(holdings)) * 45
    total_tokens = input_tokens + expected_output_tokens
    return {
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": expected_output_tokens,
        "estimated_total_tokens": total_tokens,
        "estimated_cost_usd": _estimate_cost_usd(provider, total_tokens),
    }


def chat_with_ai(provider: str, messages: List[Dict[str, str]], api_key: Optional[str],
                  lang: str = "en") -> AIEngineResult:
    if not messages:
        return AIEngineResult(False, None, False, "Ziadna sprava na odoslanie.")

    if not api_key:
        last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        reply = mock_chat_reply(last_user, lang)
        tokens = _estimate_tokens(reply)
        return AIEngineResult(True, {
            "reply": reply, "tokens_used": tokens,
            "estimated_cost_usd": 0.0,
        }, True, missing_api_key_message(lang))

    conversation = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
    last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    mentioned = [c for c in DEFAULT_COIN_IDS if re.search(rf"\b{c}\b", last_user, re.I) and c != "BTC"][:1]
    block = market_signals_block("BTC", *mentioned)
    prompt = (
        "Si strucny, priatelsky AI asistent pre krypto analyticku aplikaciu. "
        "Odpovedz strucne (max 4-5 viet) na poslednu spravu pouzivatela, "
        "v kontexte celej konverzacie nizsie. Ak sa pyta na trh, opri sa o aktualne data nizsie "
        "a nevymyslaj cisla.\n\n" + (f"{block}\n\n" if block else "") + conversation
    )
    prompt += language_instruction(lang, json_mode=False)
    success, text, error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(False, None, False, error)

    tokens = _estimate_tokens(prompt) + _estimate_tokens(text)
    cost = _estimate_cost_usd(provider, tokens)
    return AIEngineResult(True, {
        "reply": text.strip(), "tokens_used": tokens, "estimated_cost_usd": cost,
    }, False)


def call_ai_provider(provider: str, prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    success, text, error = _call_ai_provider_raw(provider, prompt, api_key)
    if not success:
        safe_error = error or ""
        secrets_to_hide = [api_key] if api_key else []
        try:
            secrets_to_hide.append(json.loads(api_key)["key"])
        except Exception:  # noqa: BLE001
            pass
        for secret in secrets_to_hide:
            if secret:
                safe_error = safe_error.replace(secret, "***")
        logger.warning("AI provider '%s' zlyhal: %s", provider, safe_error[:500])
        return success, text, safe_error
    return success, text, error
