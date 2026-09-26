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

import ipaddress
import json
import logging
import socket
import statistics
from concurrent.futures import ThreadPoolExecutor
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from app.config import (
    ANTHROPIC_API_URL, ANTHROPIC_API_VERSION, ANTHROPIC_MODEL,
    DEEPSEEK_API_URL, DEEPSEEK_MODEL, DEFAULT_COIN_IDS, GROK_API_URL, GROK_MODEL,
    MOCK_BASE_PRICES, OPENAI_API_URL, OPENAI_MODEL,
    PROVIDER_TOKEN_PRICE_USD_PER_1K,
    REQUEST_TIMEOUT_SECONDS, SECTOR_CATEGORIES, TIME_HORIZONS,
)
from app.services import data_sources, market_data

logger = logging.getLogger("aca.ai")
from app.services.validators import (
    language_instruction,
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
    if provider == "custom":
        return _call_custom_provider(prompt, api_key)
    return False, "", f"Neznamy AI provider: {provider}"


def validate_custom_base_url(url: str) -> Optional[str]:
    """Ochrana proti SSRF: adresa vlastneho providera musi byt https a smerovat
    na VEREJNY internet. Inak by cez appku slo posielat poziadavky na interne
    servery hostingu (napr. 127.0.0.1, 10.x.x.x, 169.254.169.254 - metadata
    cloudu). Vracia None, ak je adresa v poriadku, inak chybovu spravu."""
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return "Neplatná adresa API vlastného providera."
    if parsed.scheme != "https" or not parsed.hostname:
        return "Adresa API vlastného providera musí začínať https:// a obsahovať doménu."
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return "Doménu adresy API vlastného providera sa nepodarilo nájsť."
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            return "Adresa API vlastného providera musí smerovať na verejný internet, nie na internú sieť."
    return None


def _call_custom_provider(prompt: str, secret: str) -> tuple[bool, str, Optional[str]]:
    """Lubovolne OpenAI-kompatibilne API (OpenRouter, Groq, Mistral, Together...).
    Adresa sa overuje aj pri kazdom volani (nielen pri ulozeni) a presmerovania
    sa nenasleduju - aby sa ochrana nedala obist zmenou DNS alebo redirectom."""
    try:
        config = json.loads(secret)
        base_url, model, key = config["base_url"], config["model"], config["key"]
    except (ValueError, KeyError, TypeError):
        return False, "", "Vlastný provider nie je správne nastavený (adresa, model, kľúč)."
    problem = validate_custom_base_url(base_url)
    if problem:
        return False, "", problem
    try:
        response = requests.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": _TEMPERATURE, "max_tokens": _MAX_OUTPUT_TOKENS},
            timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=False,
        )
        if response.is_redirect:
            return False, "", "Vlastný provider vrátil presmerovanie - zadaj priamu adresu API."
        response.raise_for_status()
        text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        if not text.strip():
            return False, "", "Vlastný provider vrátil prázdnu odpoveď."
        return True, text, None
    except Exception as exc:  # noqa: BLE001
        return False, "", f"Vlastny provider chyba: {exc}"


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
def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))][-period:]
    gains = sum(d for d in deltas if d > 0) / period
    losses = sum(-d for d in deltas if d < 0) / period
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def _summarize_history(symbol: str, data: Dict[str, List[List[float]]]) -> Optional[str]:
    """Z 30d hodinovej historie vypocita kompaktny prehlad: zmeny 24h/7d/30d,
    7d rozpatie, RSI(14), poziciu voci SMA7/SMA30, dennu volatilitu a trend
    objemu. Pocita to KOD (presne), nie AI (ta by si cisla len odhadla)."""
    prices = data.get("prices") or []
    if len(prices) < 2:
        return None
    now_ts, current = prices[-1][0], prices[-1][1]

    def price_at(hours_ago: float) -> Optional[float]:
        target = now_ts - hours_ago * 3_600_000
        if prices[0][0] > target + 3 * 3_600_000:
            return None
        return min(prices, key=lambda p: abs(p[0] - target))[1]

    def pct(old: Optional[float]) -> Optional[float]:
        return (current - old) / old * 100 if old else None

    parts = [f"{symbol}: cena ${current:,.2f}"]
    for label, hours in (("24h", 24), ("7d", 168), ("30d", 720)):
        change = pct(price_at(hours))
        if change is not None:
            parts.append(f"{label} {change:+.1f}%")
    week = [p[1] for p in prices if p[0] >= now_ts - 168 * 3_600_000]
    if week:
        parts.append(f"7d rozpatie ${min(week):,.2f}-${max(week):,.2f}")

    closes = []
    for day in range(30, -1, -1):
        value = price_at(24 * day)
        if value is not None:
            closes.append(value)
    rsi = _rsi(closes)
    if rsi is not None:
        parts.append(f"RSI(14) {rsi:.0f}")
    for n in (7, 30):
        if len(closes) >= n:
            sma = sum(closes[-n:]) / n
            parts.append(f"vs SMA{n} {pct(sma):+.1f}%")
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] * 100 for i in range(1, len(closes)) if closes[i - 1]]
    if len(returns) >= 5:
        parts.append(f"denna volatilita ~{statistics.pstdev(returns[-14:]):.1f}%")
    volumes = data.get("volumes") or []
    week_vol = [v[1] for v in volumes if v[0] >= now_ts - 168 * 3_600_000 and v[1]]
    if week_vol and volumes[-1][1]:
        parts.append(f"objem 24h vs 7d priemer {volumes[-1][1] / (sum(week_vol) / len(week_vol)):.2f}x")
    return " | ".join(parts)


def _await(future, deadline: float):
    """Vysledok paralelnej ulohy, alebo None pri chybe/prekroceni casu."""
    if future is None:
        return None
    try:
        return future.result(timeout=max(0.1, deadline - time.monotonic()))
    except Exception:  # noqa: BLE001 - timeout aj chyba zdroja = bez tychto dat
        return None


def _append_common_context(lines: List[str], sources: List[str], futures: Dict[str, Any], deadline: float) -> None:
    """Spolocne riadky pre predikciu aj portfolio: BTC, nalada, makro, spravy, svet."""
    btc = _await(futures.get("btc"), deadline)
    if btc and btc[0]:
        summary = _summarize_history("BTC (lider trhu)", btc[1])
        if summary:
            lines.append(summary)
    fear_greed = _await(futures.get("fg"), deadline)
    if fear_greed and fear_greed[0] and fear_greed[1]:
        lines.append(f"Fear & Greed index: {fear_greed[1].get('value')} ({fear_greed[1].get('classification')})")
        sources.append("fear_greed")
    for key, label in (("macro", "fred"), ("coin_news", "coingecko_news"), ("world", "gdelt")):
        value = _await(futures.get(key), deadline)
        if value:
            lines.append(value)
            sources.append(label)
    news = _await(futures.get("news"), deadline)
    if news and news[0] and news[1]:
        lines.append("Najnovsie krypto titulky: " + "; ".join(h["title"][:100] for h in news[1][:5]))
        sources.append("news_rss")


def _build_market_context(coin: str) -> Tuple[Optional[str], List[str]]:
    """Vsetky dostupne data pre AI predikciu jednej mince + zoznam pouzitych
    zdrojov (zobrazi sa pouzivatelovi). Zdroje sa nacitavaju PARALELNE s
    kratkym limitom (celkovo max ~_MARKET_CONTEXT_TIMEOUT+1 s), aby sa spolu
    s AI volanim zmestili do ~40s limitu Netlify proxy. Podla typu mince
    (meme / DeFi / L1) sa pridaju dalsie zdroje a instrukcia, na co sa
    zamerat. Nikdy nevyhodi vynimku."""
    coin_id = DEFAULT_COIN_IDS.get(coin.upper())
    if not coin_id:
        return None, []
    symbol = coin.upper()
    pool = ThreadPoolExecutor(max_workers=12)
    try:
        deadline = time.monotonic() + _MARKET_CONTEXT_TIMEOUT + 1
        futures = {
            "coin": pool.submit(market_data.get_market_history, coin_id, 30, _MARKET_CONTEXT_TIMEOUT),
            "btc": pool.submit(market_data.get_market_history, "bitcoin", 30, _MARKET_CONTEXT_TIMEOUT) if coin_id != "bitcoin" else None,
            "fg": pool.submit(market_data.get_fear_greed_index),
            "news": pool.submit(market_data.get_crypto_headlines, 5),
            "profile": pool.submit(data_sources.coin_profile, coin_id),
            "coin_news": pool.submit(data_sources.coin_news, coin_id),
            "deriv": pool.submit(data_sources.derivatives, symbol),
            "onchain": pool.submit(data_sources.onchain, coin_id),
            "tvl": pool.submit(data_sources.chain_tvl, coin_id),
            "macro": pool.submit(data_sources.macro_summary),
            "world": pool.submit(data_sources.world_news),
        }
        coin_res = _await(futures["coin"], deadline)
        summary = _summarize_history(symbol, coin_res[1]) if coin_res and coin_res[0] else None
        if not summary:
            return None, []
        lines, sources = [summary], ["coingecko_market"]

        profile = _await(futures["profile"], deadline)
        dev_future = subreddit_future = None
        if profile:
            kind = data_sources.coin_type(profile.get("categories") or [])
            if kind in ("l1", "defi") and profile.get("github"):
                dev_future = pool.submit(data_sources.github_activity, profile["github"])
            if profile.get("subreddit"):
                subreddit_future = pool.submit(data_sources.coin_subreddit, profile["subreddit"])
            line = data_sources.profile_line(profile)
            if line:
                lines.append(line)
                sources.append("coingecko_profile")
            if data_sources.TYPE_GUIDANCE.get(kind):
                lines.append(data_sources.TYPE_GUIDANCE[kind])

        for key, label in (("deriv", "hyperliquid"), ("onchain", "blockchair"), ("tvl", "defillama")):
            value = _await(futures[key], deadline)
            if value:
                lines.append(value)
                sources.append(label)
        for future, label in ((dev_future, "github"), (subreddit_future, "reddit_coin")):
            value = _await(future, deadline)
            if value:
                lines.append(value)
                sources.append(label)
        _append_common_context(lines, sources, futures, deadline)
        return "\n".join(lines), sources
    except Exception:  # noqa: BLE001
        return None, []
    finally:
        pool.shutdown(wait=False)


def _fetch_market_context(coin: str) -> Optional[str]:
    """Len text kontextu (bez zoznamu zdrojov) - viz _build_market_context()."""
    return _build_market_context(coin)[0]


def _build_portfolio_context(holdings: List[Dict[str, Any]]) -> Tuple[Optional[str], List[str]]:
    """Realne data pre analyzu portfolia. PREDTYM AI dostala len nazvy mincí
    a mnozstva - bez cien, trendov ci spraw, takze odporucania boli len odhad.
    Hodnoty a vahy pozicii pocita KOD (presne), nie AI."""
    ids = [h.get("coin_id") or DEFAULT_COIN_IDS.get(str(h.get("minca", "")).upper()) for h in holdings]
    pool = ThreadPoolExecutor(max_workers=6)
    try:
        deadline = time.monotonic() + _MARKET_CONTEXT_TIMEOUT + 1
        futures = {
            "markets": pool.submit(market_data.get_coin_markets, [i for i in ids if i], _MARKET_CONTEXT_TIMEOUT),
            "btc": pool.submit(market_data.get_market_history, "bitcoin", 30, _MARKET_CONTEXT_TIMEOUT),
            "fg": pool.submit(market_data.get_fear_greed_index),
            "news": pool.submit(market_data.get_crypto_headlines, 5),
            "macro": pool.submit(data_sources.macro_summary),
            "world": pool.submit(data_sources.world_news),
        }
        markets = _await(futures["markets"], deadline)
        rows = markets[1] if markets and markets[0] else {}
        if not rows:
            return None, []
        values: List[Optional[float]] = []
        for holding, coin_id in zip(holdings, ids):
            row = rows.get(coin_id) if coin_id else None
            price = row.get("current_price") if row else None
            values.append(float(holding.get("mnozstvo") or 0) * price if price else None)
        total = sum(v for v in values if v)
        lines: List[str] = []

        def change(row: Dict[str, Any], key: str) -> str:
            value = row.get(key)
            return f"{value:+.1f}%" if isinstance(value, (int, float)) else "n/a"

        for holding, coin_id, value in zip(holdings, ids, values):
            symbol = str(holding.get("minca", "?")).upper()
            row = rows.get(coin_id) if coin_id else None
            if not row or value is None:
                lines.append(f"{symbol}: {holding.get('mnozstvo')} ks | bez trhovych dat")
                continue
            weight = value / total * 100 if total else 0
            lines.append(
                f"{symbol}: hodnota ${value:,.0f} ({weight:.0f}% portfolia) | 24h {change(row, 'price_change_percentage_24h_in_currency')} | "
                f"7d {change(row, 'price_change_percentage_7d_in_currency')} | 30d {change(row, 'price_change_percentage_30d_in_currency')} | "
                f"rank #{row.get('market_cap_rank') or '?'} | {change(row, 'ath_change_percentage')} od historickeho maxima"
            )
        weights = sorted((v / total * 100 for v in values if v and total), reverse=True)
        if weights:
            lines.append(f"Celkova hodnota ${total:,.0f} | najvacsia pozicia {weights[0]:.0f}% | pocet pozicii {len(holdings)}")
        sources = ["coingecko_prices"]
        _append_common_context(lines, sources, futures, deadline)
        return "\n".join(lines), sources
    except Exception:  # noqa: BLE001
        return None, []
    finally:
        pool.shutdown(wait=False)


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
    start_ms, end_ms = created_at_utc.timestamp() * 1000, target_end.timestamp() * 1000
    actual_prices: List[float] = []
    for i in range(n):
        # bod i = cas vytvorenia + (i+1) krokov - rovnako ako casy v grafe
        target_ts = start_ms + (end_ms - start_ms) * (i + 1) / n
        closest = min(chart, key=lambda p: abs(p[0] - target_ts))
        actual_prices.append(closest[1])

    errors = [abs(predicted_prices[i] - actual_prices[i]) / actual_prices[i]
              for i in range(n) if actual_prices[i]]
    if not errors:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": actual_prices}

    mape_pct = (sum(errors) / len(errors)) * 100
    accuracy_pct = round(max(0.0, 100.0 - mape_pct), 1)

    # Pri kryptomenach aj naivny odhad "cena sa nezmeni" casto dosiahne 95%+
    # podla tejto metriky - samotne percento by teda pouzivatela zavadzalo.
    # Preto porovnanie s tymto naivnym odhadom + ci predikcia trafila SMER.
    start_price = chart[0][1]
    baseline_errors = [abs(start_price - a) / a for a in actual_prices if a]
    baseline_pct = round(max(0.0, 100.0 - sum(baseline_errors) / len(baseline_errors) * 100), 1) if baseline_errors else None
    direction_correct = (predicted_prices[-1] >= start_price) == (actual_prices[-1] >= start_price)
    return {**base, "status": "completed", "accuracy_pct": accuracy_pct, "actual_prices": actual_prices,
            "baseline_accuracy_pct": baseline_pct, "direction_correct": direction_correct}


def get_coin_forecast(provider: str, coin: str, horizon: str, api_key: Optional[str], lang: str = "en") -> AIEngineResult:
    if not api_key:
        return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True,
                               missing_api_key_message(lang))

    points = int(TIME_HORIZONS.get(horizon, {"points": 7})["points"])
    market_context, sources_used = _build_market_context(coin)
    prompt = build_forecast_prompt(coin, horizon, points, market_context) + language_instruction(lang)
    success, raw_text, call_error = call_ai_provider(provider, prompt, api_key)
    if not success:
        return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True, call_error)

    is_valid, parsed, validation_error = validate_forecast_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(True, _generate_mock_forecast(coin, horizon, lang), True, validation_error)

    parsed["zdroje_dat"] = sources_used
    # Presny cas vytvorenia + skutocna cena v tom case - graf z nich zobrazi
    # realne casy (napr. 7:00 -> 7:00) a zaciatok oboch kriviek.
    parsed["vytvorene"] = datetime.now(timezone.utc).isoformat()
    if market_context:
        ok, history, _ = market_data.get_market_history(DEFAULT_COIN_IDS[coin.upper()], 30, _MARKET_CONTEXT_TIMEOUT)
        if ok and history.get("prices"):
            parsed["aktualna_cena"] = history["prices"][-1][1]
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
    if not success:
        return AIEngineResult(True, _generate_mock_portfolio_analysis(holdings, lang), True, call_error)

    is_valid, parsed, validation_error = validate_portfolio_payload(raw_text)
    if not is_valid or parsed is None:
        return AIEngineResult(True, _generate_mock_portfolio_analysis(holdings, lang), True, validation_error)

    parsed["zdroje_dat"] = sources_used
    return AIEngineResult(True, parsed, False)


def get_news_sentiment_summary(provider: str, headlines: List[str], api_key: Optional[str],
                                lang: str = "en") -> AIEngineResult:
    if not headlines:
        return AIEngineResult(False, None, False, "Ziadne titulky na analyzu.")

    if not api_key:
        return AIEngineResult(True, _generate_mock_news_summary(headlines, lang), True,
                               missing_api_key_message(lang))

    prompt = build_news_prompt(headlines) + language_instruction(lang)
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

    prompt = build_daily_digest_prompt(fg_value, fg_classification, headlines) + language_instruction(lang)
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
    input_tokens = _estimate_tokens(prompt) + 450  # + trhove data, doplnane az pri realnom volani
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
    input_tokens = _estimate_tokens(prompt) + 150 + 60 * len(holdings)  # + trhove data, doplnane az pri realnom volani
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
    """Obal okolo _call_ai_provider_raw(), ktory kazde zlyhanie zapise do
    serverovych logov (Render -> Logs). Bez toho pouzivatel videl len
    ukazkove data so vseobecnou chybou a skutocna pricina sa dala len hadat.
    API kluc sa z chybovej spravy pre istotu vymaze, keby ho tam provider
    niekedy vratil."""
    success, text, error = _call_ai_provider_raw(provider, prompt, api_key)
    if not success:
        safe_error = error or ""
        secrets_to_hide = [api_key] if api_key else []
        try:  # vlastny provider: v api_key je JSON - skry aj samotny kluc v nom
            secrets_to_hide.append(json.loads(api_key)["key"])
        except Exception:  # noqa: BLE001
            pass
        for secret in secrets_to_hide:
            if secret:
                safe_error = safe_error.replace(secret, "***")
        logger.warning("AI provider '%s' zlyhal: %s", provider, safe_error[:500])
    return success, text, error
