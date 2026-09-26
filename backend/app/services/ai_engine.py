"""
app/services/ai_engine.py
===========================
Automatizovana AI vrstva - 5 providerov (Gemini, OpenAI, Anthropic,
DeepSeek, Grok). API kluc sa desifruje az tesne pred pouzitim
(viz app/security.py::decrypt_secret) a nikdy sa nikam neloguje.
Pri zlyhani (chybajuci/neplatny kluc, sietova chyba, nevalidny JSON)
sa transparentne prepne na deterministicky mock, aby endpoint nikdy
nevratil 500 kvoli vypadku externeho AI providera.
"""

from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from app.config import (
    ANTHROPIC_API_URL, ANTHROPIC_API_VERSION, ANTHROPIC_MODEL,
    DEEPSEEK_API_URL, DEEPSEEK_MODEL, DEFAULT_COIN_IDS, GROK_API_URL, GROK_MODEL,
    MOCK_BASE_PRICES, OPENAI_API_URL, OPENAI_MODEL,
    PROVIDER_TOKEN_PRICE_USD_PER_1K,
    REQUEST_TIMEOUT_SECONDS, SECTOR_CATEGORIES, TIME_HORIZONS,
)
from app.services import market_data

logger = logging.getLogger("aca.ai")
from app.services.validators import (
    build_daily_digest_prompt, build_forecast_prompt, build_news_prompt, build_portfolio_prompt,
    validate_digest_payload, validate_forecast_payload, validate_news_payload, validate_portfolio_payload,
)
from app.i18n_content import (
    missing_api_key_message, mock_chat_reply, mock_digest_summary, mock_forecast_reasoning,
    mock_portfolio_reason, unit_label, MOCK_DIGEST_KEY_POINTS, MOCK_NEWS_TRENDS,
    MOCK_PORTFOLIO_ANALYSIS_TEXT, MOCK_REBALANCING_CHECKLIST, normalize_lang,
)


class AIEngineResult:
    def __init__(self, success: bool, data: Optional[Dict[str, Any]], is_mock: bool,
                 error_message: Optional[str] = None) -> None:
        self.success = success
        self.data = data
        self.is_mock = is_mock
        self.error_message = error_message

    def as_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success, "data": self.data,
            "is_mock": self.is_mock, "error_message": self.error_message,
        }


# ---------------------------------------------------------------------------
# Retry & Exponential Backoff pre docasne vypadky provider API (napr. Gemini
# 503 "model overloaded", 429 rate limit, siet. timeouty). Neopakuje sa pri
# trvalych chybach (401 nespravny kluc a pod.) - tie sa vratia hned.
#
# DOLEZITE: Netlify (a podobne proxy pred FastAPI backendom) ma vlastny
# tvrdy limit cca 30-40s na to, kym backend zacne posielat odpoved - ak to
# nestihne, PROXY SAMA vrati 502 skor, nez FastAPI vobec stihne odpovedat
# (bez ohladu na to, ci by AI provider nakoniec uspel). _MAX_RETRIES=1 a
# REQUEST_TIMEOUT_SECONDS=12 su zamerne male, aby CELY najhorsi mozny
# pripad (2 pokusy + 1 pauza) ostal bezpecne pod touto hranicou:
# 12 + 1.5 + 12 = 25.5s, s rezervou cca 14s na sietovu/frontovu rezii.
# ---------------------------------------------------------------------------
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
_MAX_RETRIES = 1
_BACKOFF_BASE_SECONDS = 1.5


def _post_with_retry(url: str, headers: Dict[str, str], payload: Dict[str, Any],
                      timeout: int) -> requests.Response:
    """POST s exponencialnym backoffom pri 429/502/503/504 alebo sietovom
    timeoute/vypadku spojenia. Pri poslednom pokuse necha vynimku prejst von."""
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** attempt))
                continue
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** attempt))
                continue
            raise
    if last_exc:
        raise last_exc
    raise requests.exceptions.RequestException("Neznama chyba pri volani API.")


# ---------------------------------------------------------------------------
# Nizkourovnove volania providerov
#
# DOLEZITE (naklady/token spotreba): kazdy provider ma explicitne obmedzeny
# vystup na _MAX_OUTPUT_TOKENS a nizku temperature (0.4). Odpovede su vzdy
# kompaktny strukturovany JSON (zopar cenovych bodov + kratke zdovodnenie),
# takze vyssi limit by len umoznil modelu zbytocne "vypisovat sa" - a teda
# platit za tokeny, ktore appka aj tak zahodi pri parsovani. Rovnaky limit
# naprieč vsetkymi providermi = predvidatelne naklady bez ohladu na to, ktory
# si pouzivatel zvoli.
# ---------------------------------------------------------------------------
_MAX_OUTPUT_TOKENS = 1024
_TEMPERATURE = 0.4
# Kratky timeout pre "bonusove" volania na CoinGecko v _fetch_market_context()
# (nie plny REQUEST_TIMEOUT_SECONDS) - viz podrobne vysvetlenie priamo pri
# _fetch_market_context() nizsie.
_MARKET_CONTEXT_TIMEOUT = 5
# Gemini 3.x je "premyslajuci" model: do max_output_tokens sa ZAPOCITAVA aj
# jeho vnutorne premyslanie. Pri limite 1024 a predvolenej (strednej) urovni
# premyslania minul cely limit na premyslanie a vratil PRAZDNU odpoved -
# appka potom spadla do ukazkovych dat s nezrozumitelnou chybou. Preto:
# nizka uroven premyslania + vyssi strop (plati sa len za realne pouzite
# tokeny, nie za strop, takze vyssi strop naklady nezvysuje).
_GEMINI_MAX_OUTPUT_TOKENS = 4096


def _call_gemini(prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    last_error = ""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            from google import genai
            from google.genai import types
            # DOLEZITE: bez explicitneho http_options timeoutu google-genai SDK
            # pouziva svoj vlastny (nezdokumentovany, potencialne dlhy) default -
            # v kombinacii s retry loopom nizsie to mohlo trvat tak dlho, ze
            # Netlify proxy pred backendom sama vratila 502 skor, nez tento
            # kod vobec stihol odpovedat (viz komentar pri _MAX_RETRIES vyssie).
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_SECONDS * 1000))
            # BEZ temperature: pri Gemini 3.6 je podla Google zastarana a moze
            # byt odmietnuta (HTTP 400).
            response = client.models.generate_content(
                model="gemini-3.6-flash", contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=_GEMINI_MAX_OUTPUT_TOKENS,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            text = response.text or ""
            if not text.strip():
                return False, "", "Gemini vratil prazdnu odpoved (limit vystupu bol vycerpany premyslanim modelu)."
            return True, text, None
        except Exception as exc:  # noqa: BLE001 - musime zachytit vsetko, nikdy nepadnut
            last_error = str(exc)
            # Retry len na docasne vypadky (preťaženie/rate limit), nie napr. na neplatny kluc.
            is_retryable = any(marker in last_error.lower() for marker in ("503", "overloaded", "429", "rate limit", "unavailable", "timeout"))
            if is_retryable and attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** attempt))
                continue
            return False, "", f"Gemini API chyba: {exc}"
    return False, "", f"Gemini API chyba: {last_error}"


def _call_openai_compatible(url: str, model: str, prompt: str, api_key: str,
                             extra_headers: Optional[Dict[str, str]] = None) -> tuple[bool, str, Optional[str]]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    payload = {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": _TEMPERATURE, "max_tokens": _MAX_OUTPUT_TOKENS,
    }
    try:
        response = _post_with_retry(url, headers, payload, REQUEST_TIMEOUT_SECONDS)
        body = response.json()
        text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        return True, text, None
    except requests.exceptions.RequestException as exc:
        return False, "", f"API chyba ({url}): {exc}"
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        return False, "", f"Neocakavany format odpovede ({url}): {exc}"


def _call_anthropic(prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_API_VERSION, "Content-Type": "application/json"}
    payload = {"model": ANTHROPIC_MODEL, "max_tokens": _MAX_OUTPUT_TOKENS, "temperature": _TEMPERATURE,
               "messages": [{"role": "user", "content": prompt}]}
    try:
        response = _post_with_retry(ANTHROPIC_API_URL, headers, payload, REQUEST_TIMEOUT_SECONDS)
        body = response.json()
        blocks = body.get("content", [])
        text = blocks[0].get("text", "") if blocks else ""
        return True, text, None
    except requests.exceptions.RequestException as exc:
        return False, "", f"Anthropic API chyba: {exc}"
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        return False, "", f"Neocakavany format odpovede Anthropic: {exc}"


def _call_ai_provider_raw(provider: str, prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    if provider == "gemini":
        return _call_gemini(prompt, api_key)
    if provider == "openai":
        return _call_openai_compatible(OPENAI_API_URL, OPENAI_MODEL, prompt, api_key)
    if provider == "anthropic":
        return _call_anthropic(prompt, api_key)
    if provider == "deepseek":
        return _call_openai_compatible(DEEPSEEK_API_URL, DEEPSEEK_MODEL, prompt, api_key)
    if provider == "grok":
        return _call_openai_compatible(GROK_API_URL, GROK_MODEL, prompt, api_key)
    return False, "", f"Neznamy AI provider: {provider}"


# ---------------------------------------------------------------------------
# Mock generatory (fallback)
# ---------------------------------------------------------------------------
def _generate_mock_forecast(coin: str, horizon: str, lang: str = "en") -> Dict[str, Any]:
    horizon_config = TIME_HORIZONS.get(horizon, {"points": 7, "unit": "den"})
    points = int(horizon_config["points"])
    unit_key = str(horizon_config["unit"])
    unit = unit_label(unit_key, lang)
    base_price = MOCK_BASE_PRICES.get(coin, 100.0)

    random.seed(f"{coin}-{horizon}")
    prices: List[float] = []
    current = base_price
    for _ in range(points):
        current = max(0.0001, current * (1 + random.uniform(-0.04, 0.045)))
        prices.append(round(current, 4))

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


def _generate_mock_portfolio_analysis(holdings: List[Dict[str, Any]], lang: str = "en") -> Dict[str, Any]:
    actions = ["BUY", "SELL", "HOLD"]
    recommendations = []
    for item in holdings:
        coin = item.get("minca", "N/A")
        random.seed(coin)
        action = random.choice(actions)
        recommendations.append({"minca": coin, "akcia": action, "dovod": mock_portfolio_reason(action, coin, lang)})

    random.seed("sector-mock")
    raw_weights = [random.uniform(5, 30) for _ in SECTOR_CATEGORIES]
    total_weight = sum(raw_weights)
    sector_allocation = {s: round((w / total_weight) * 100, 1) for s, w in zip(SECTOR_CATEGORIES, raw_weights)}

    lang = normalize_lang(lang)
    return {
        "odporucania": recommendations,
        "odborna_analyza": MOCK_PORTFOLIO_ANALYSIS_TEXT[lang],
        "sektorova_alokacia": sector_allocation,
        "rebalancing_checklist": MOCK_REBALANCING_CHECKLIST[lang],
    }


def _generate_mock_news_summary(headlines: List[str], lang: str = "en") -> Dict[str, Any]:
    sentiments = ["Bullish", "Bearish", "Neutral"]
    news = []
    for i, title in enumerate(headlines):
        random.seed(f"{title}-{i}")
        news.append({"titulok": title, "sentiment": random.choice(sentiments)})
    return {
        "spravy": news,
        "trendy": MOCK_NEWS_TRENDS[normalize_lang(lang)],
    }


# ---------------------------------------------------------------------------
# Verejne funkcie volane z routerov
# ---------------------------------------------------------------------------
def _fetch_market_context(coin: str) -> Optional[str]:
    """Skutocne aktualne trhove data pre danu mincu (aktualna cena, 24h a 7d
    zmena) - format ako kratky textovy blok na vlozenie do AI promptu.

    DOLEZITE: bez tohto AI model nemal ZIADNU realnu kotvu (nevedel, aka je
    aktualna cena) a predikcie tak boli len vymyslene cisla naviazane na
    vseobecny "crypto stale rastie" narativ z trenovacich dat namiesto na
    realny aktualny trend - presne preto posobili systematicky prilis
    optimisticky. Vrati None (nie vynimku), ak sa data nepodari zohnat -
    volajuci potom prompt zostavi bez tejto casti, nikdy to nepadne.

    DOLEZITE (casovy rozpocet): tieto 2 volania su ZAMERNE s kratkym timeoutom
    (_MARKET_CONTEXT_TIMEOUT), nie plnym REQUEST_TIMEOUT_SECONDS - su to
    lahke JSON endpointy, co bezne odpovedia do 1-2s, takze kratky timeout
    normalnu prevadzku nijak neobmedzi. Bez tohto obmedzenia mohli tieto 2
    "bonusove" volania v najhorsom pripade zjest az 24s (2x plny timeout)
    E S T E PREDTYM, nez vobec zacalo samotne (pomalsie) volanie AI providera
    - spolu s tym by cely request mohol prekrocit ~40s limit Netlify proxy
    pred backendom a skoncit s 502 chybou, presne to, co sme predtym riesili.
    """
    coin_id = DEFAULT_COIN_IDS.get(coin.upper())
    if not coin_id:
        return None
    try:
        price_ok, prices, _ = market_data.get_live_prices([coin_id], "usd", timeout=_MARKET_CONTEXT_TIMEOUT)
        chart_ok, chart, _ = market_data.get_market_chart(coin_id, "usd", "7", timeout=_MARKET_CONTEXT_TIMEOUT)
        if not price_ok or not prices or coin_id not in prices:
            return None
        current = prices[coin_id]["usd"]
        change_24h = prices[coin_id].get("usd_24h_change", 0.0)
        parts = [f"Aktualna cena: ${current:,.2f} USD", f"Zmena za 24h: {change_24h:+.2f}%"]
        if chart_ok and len(chart) >= 2:
            price_7d_ago = chart[0][1]
            if price_7d_ago:
                change_7d = (current - price_7d_ago) / price_7d_ago * 100
                low = min(p[1] for p in chart)
                high = max(p[1] for p in chart)
                parts.append(f"Zmena za poslednych 7 dni: {change_7d:+.2f}%")
                parts.append(f"Rozpatie za 7 dni: ${low:,.2f} - ${high:,.2f} USD")
        return " | ".join(parts)
    except Exception:  # noqa: BLE001 - realne data su bonus, nikdy nesmu zhodit predikciu
        return None


def compute_forecast_accuracy(coin: str, timeframe: str, predicted_prices: List[float],
                               time_labels: List[str], created_at: datetime) -> Dict[str, Any]:
    """Spatne porovna ulozenu predikciu so SKUTOCNYM vyvojom ceny odvtedy, aby
    mal pouzivatel dokaz (nie len sluby), ci AI predikcie maju realnu
    vypovednu hodnotu. Tri mozne stavy:
    - "pending": horizont predikcie este neubehol (napr. 1-tyzdnova predikcia
      stara len 2 dni) - realne data na porovnanie proste este neexistuju.
    - "unavailable": minca nie je v DEFAULT_COIN_IDS (custom vyhladana minca)
      alebo CoinGecko data nezohnal - graceful fallback, nikdy vynimka.
    - "completed": realne porovnanie s vypocitanym % presnosti."""
    horizon_days_map = {"24h": 1, "1T": 7, "1M": 30, "1R": 365}
    horizon_days = horizon_days_map.get(timeframe, 7)
    created_at_utc = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    target_end = created_at_utc + timedelta(days=horizon_days)
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
    except Exception:  # noqa: BLE001 - toto je bonusova funkcia, nikdy nesmie zhodit endpoint
        ok, chart = False, []

    if not ok or len(chart) < 2:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": []}

    n = len(predicted_prices)
    chart_start_ts, chart_end_ts = chart[0][0], chart[-1][0]
    actual_prices: List[float] = []
    for i in range(n):
        frac = i / max(1, n - 1)
        target_ts = chart_start_ts + (chart_end_ts - chart_start_ts) * frac
        closest = min(chart, key=lambda p: abs(p[0] - target_ts))
        actual_prices.append(closest[1])

    errors = [abs(predicted_prices[i] - actual_prices[i]) / actual_prices[i]
              for i in range(n) if actual_prices[i]]
    if not errors:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": actual_prices}

    mape_pct = (sum(errors) / len(errors)) * 100
    accuracy_pct = round(max(0.0, 100.0 - mape_pct), 1)

    return {**base, "status": "completed", "accuracy_pct": accuracy_pct, "actual_prices": actual_prices}


def get_coin_forecast(provider: str, coin: str, horizon: str, api_key: Optional[str], lang: str = "en") -> AIEngineResult:
    if not api_key:
        return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True,
                               missing_api_key_message(lang))

    points = int(TIME_HORIZONS.get(horizon, {"points": 7})["points"])
    market_context = _fetch_market_context(coin)
    prompt = build_forecast_prompt(coin, horizon, points, market_context)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True, call_error)

    is_valid, parsed, validation_error = validate_forecast_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True, validation_error)

    return AIEngineResult(True, parsed, False)


def get_portfolio_analysis(provider: str, holdings: List[Dict[str, Any]], api_key: Optional[str],
                            lang: str = "en") -> AIEngineResult:
    if not holdings:
        return AIEngineResult(False, None, False, "Portfolio je prazdne - pridaj aspon jednu mincu.")

    if not api_key:
        return AIEngineResult(True, _generate_mock_portfolio_analysis(holdings, lang), True,
                               missing_api_key_message(lang))

    prompt = build_portfolio_prompt(holdings)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(True, _generate_mock_portfolio_analysis(holdings, lang), True, call_error)

    is_valid, parsed, validation_error = validate_portfolio_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(True, _generate_mock_portfolio_analysis(holdings, lang), True, validation_error)

    return AIEngineResult(True, parsed, False)


def get_news_sentiment_summary(provider: str, headlines: List[str], api_key: Optional[str],
                                lang: str = "en") -> AIEngineResult:
    if not headlines:
        return AIEngineResult(False, None, False, "Ziadne titulky na analyzu.")

    if not api_key:
        return AIEngineResult(True, _generate_mock_news_summary(headlines, lang), True,
                               missing_api_key_message(lang))

    prompt = build_news_prompt(headlines)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(True, _generate_mock_news_summary(headlines, lang), True, call_error)

    is_valid, parsed, validation_error = validate_news_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(True, _generate_mock_news_summary(headlines, lang), True, validation_error)

    return AIEngineResult(True, parsed, False)


def _generate_mock_digest(fg_value: int, fg_classification: str, lang: str = "en") -> Dict[str, Any]:
    return {
        "zhrnutie": mock_digest_summary(fg_value, fg_classification, lang),
        "kluceve_body": MOCK_DIGEST_KEY_POINTS[normalize_lang(lang)],
    }


def get_daily_digest(provider: str, fg_value: int, fg_classification: str,
                      headlines: List[str], api_key: Optional[str], lang: str = "en") -> AIEngineResult:
    if not api_key:
        return AIEngineResult(True, _generate_mock_digest(fg_value, fg_classification, lang), True,
                               missing_api_key_message(lang))

    prompt = build_daily_digest_prompt(fg_value, fg_classification, headlines)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(True, _generate_mock_digest(fg_value, fg_classification, lang), True, call_error)

    is_valid, parsed, validation_error = validate_digest_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(True, _generate_mock_digest(fg_value, fg_classification, lang), True, validation_error)

    return AIEngineResult(True, parsed, False)


# ---------------------------------------------------------------------------
# Test platnosti API kluca (Account page — tlacidlo "Testovať")
# ---------------------------------------------------------------------------
def test_api_key(provider: str, api_key: str) -> tuple[bool, Optional[str]]:
    """Vykona nizko-nakladove API volanie na overenie, ci je kluc platny
    a funkcny. Vracia (ok, chybova_sprava)."""
    if not api_key or not api_key.strip():
        return False, "API kluc je prazdny."
    success, _text, error = call_ai_provider(provider, "Odpovedz jednym slovom: OK", api_key.strip())
    if not success:
        return False, error or "Kluc sa nepodarilo overit."
    return True, None


# ---------------------------------------------------------------------------
# AI Chat asistent (plavajuce tlacidlo v aplikacii)
# ---------------------------------------------------------------------------
def _estimate_tokens(text: str) -> int:
    """Hruby odhad poctu tokenov (~4 znaky/token), iba pre orientacny UI indikator."""
    return max(1, round(len(text) / 4))


def _estimate_cost_usd(provider: str, total_tokens: int) -> float:
    price_per_1k = PROVIDER_TOKEN_PRICE_USD_PER_1K.get(provider, 0.0008)
    return round((total_tokens / 1000) * price_per_1k, 6)


def estimate_forecast_cost(provider: str, coin: str, horizon: str) -> Dict[str, Any]:
    """Odhad ceny PRED skutocnym volanim AI (pre potvrdzovacie okno na
    frontende) - vypocitany na TOM ISTOM prompte, aky by sa realne poslal, aby
    bol odhad vstupnych tokenov presny. market_context sa zamerne vynechava
    (na rozdiel od skutocneho volania v get_coin_forecast) - je to len o pár
    desiatok tokenov naviac a odhad tak nemusi cakat na sietovy dotaz na
    CoinGecko, aby ostal pre pouzivatela okamzity."""
    points = int(TIME_HORIZONS.get(horizon, {"points": 7})["points"])
    prompt = build_forecast_prompt(coin, horizon, points, market_context=None)
    input_tokens = _estimate_tokens(prompt)
    # Typicky vystup: kratke zdovodnenie + strukturalny JSON overhead, plus
    # trocha naviac za kazdy dalsi datovy bod (cislo + casovy popisok).
    expected_output_tokens = 150 + points * 12
    total_tokens = input_tokens + expected_output_tokens
    return {
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": expected_output_tokens,
        "estimated_total_tokens": total_tokens,
        "estimated_cost_usd": _estimate_cost_usd(provider, total_tokens),
    }


def estimate_portfolio_cost(provider: str, holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rovnaky princip ako estimate_forecast_cost(), pre Portfolio Advisor."""
    prompt = build_portfolio_prompt(holdings)
    input_tokens = _estimate_tokens(prompt)
    # Vystup rastie s poctom pozicii (kazda ma vlastne "akcia" + "dovod").
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
    prompt = (
        "Si strucny, priatelsky AI asistent pre krypto analyticku aplikaciu. "
        "Odpovedz strucne (max 4-5 viet) na poslednu spravu pouzivatela, "
        "v kontexte celej konverzacie nizsie:\n\n" + conversation
    )
    success, text, error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(False, None, False, error)

    tokens = _estimate_tokens(prompt) + _estimate_tokens(text)
    cost = _estimate_cost_usd(provider, tokens)
    return AIEngineResult(True, {
        "reply": text.strip(), "tokens_used": tokens, "estimated_cost_usd": cost,
    }, False)


def call_ai_provider(provider: str, prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    """Obal okolo _call_ai_provider_raw(), ktory kazde zlyhanie zapise do
    serverovych logov (Render -> Logs). Bez toho pouzivatel videl len
    ukazkove data so vseobecnou chybou a skutocna pricina sa dala len hadat.
    API kluc sa z chybovej spravy pre istotu vymaze, keby ho tam provider
    niekedy vratil."""
    success, text, error = _call_ai_provider_raw(provider, prompt, api_key)
    if not success:
        safe_error = (error or "").replace(api_key, "***") if api_key else (error or "")
        logger.warning("AI provider '%s' zlyhal: %s", provider, safe_error[:500])
    return success, text, error
