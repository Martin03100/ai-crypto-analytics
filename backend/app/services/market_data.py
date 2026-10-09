"""Market data service."""

from __future__ import annotations

import math
import re
from defusedxml import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.config import CRYPTO_NEWS_RSS_URLS, FEAR_GREED_API_URL, REDDIT_CRYPTO_URL, REQUEST_TIMEOUT_SECONDS
from app.i18n_content import MARKET_EVENT_CALENDAR, market_events_for_lang
from app.utils.ttl_cache import TTLCache

_fear_greed_cache = TTLCache(ttl_seconds=900)
_FEAR_GREED_KEY = "fear_greed"

_DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AICryptoAnalytics/2.0)"}

_NEWS_SOURCE_TIMEOUT = 5
_MAX_FEED_BYTES = 3_000_000
_headlines_cache = TTLCache(ttl_seconds=300)


def get_fear_greed_index(force_refresh: bool = False) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    if not force_refresh:
        cached = _fear_greed_cache.get(_FEAR_GREED_KEY)
        if cached is not None:
            return True, cached, None

    try:
        response = requests.get(FEAR_GREED_API_URL, timeout=REQUEST_TIMEOUT_SECONDS, headers=_DEFAULT_HEADERS)
        response.raise_for_status()
        body = response.json()
        entries = body.get("data", [])
        if not entries:
            return False, None, "API vratilo prazdnu odpoved pre Fear & Greed Index."
        latest = entries[0]
        raw_ts = latest.get("timestamp", "")
        try:
            updated_at = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc).isoformat()
        except (TypeError, ValueError):
            updated_at = ""
        data = {
            "value": min(100, max(0, int(latest.get("value", 50)))),
            "classification": str(latest.get("value_classification", "Nezname")),
            "timestamp": raw_ts,
            "updated_at": updated_at,
        }
        _fear_greed_cache.set(_FEAR_GREED_KEY, data)
        return True, data, None
    except requests.exceptions.RequestException as exc:
        stale = _fear_greed_cache.get(_FEAR_GREED_KEY, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsiu cachovanu hodnotu (chyba siete: {exc})"
        return False, None, f"Chyba siete pri nacitani Fear & Greed Index: {exc}"
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        return False, None, f"Chyba pri spracovani Fear & Greed Index: {exc}"


_TAG_STRIP_PATTERN = re.compile(r"<[^>]+>")

_COIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
VALID_VS_CURRENCIES = ("usd", "eur", "czk", "btc")
VALID_CHART_DAYS = ("1", "7", "14", "30", "90", "180", "365", "max")


def is_valid_coin_id(value: str) -> bool:
    return bool(value) and bool(_COIN_ID_RE.match(value))


def safe_http_url(value: str) -> str:
    value = (value or "").strip()
    return value if value.lower().startswith(("http://", "https://")) else ""


def _clean_html(text: str) -> str:
    if not text:
        return ""
    return _TAG_STRIP_PATTERN.sub("", text).strip()


def _parse_rss_date(raw: str) -> Optional[datetime]:
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_one_rss_source(url: str, per_source_limit: int) -> List[Dict[str, str]]:
    response = requests.get(url, timeout=_NEWS_SOURCE_TIMEOUT, headers=_DEFAULT_HEADERS)
    response.raise_for_status()
    if len(response.content) > _MAX_FEED_BYTES:
        raise ValueError("RSS feed je neobvykle velky")
    root = ET.fromstring(response.content)
    items = root.findall(".//item")
    channel_title_el = root.find(".//channel/title")
    source_name = _clean_html(channel_title_el.text) if channel_title_el is not None and channel_title_el.text else "Krypto Spravy"
    headlines: List[Dict[str, str]] = []
    for item in items[:per_source_limit]:
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        title = _clean_html(title_el.text) if title_el is not None and title_el.text else ""
        link = safe_http_url(link_el.text) if link_el is not None and link_el.text else ""
        published_at = _parse_rss_date(pubdate_el.text) if pubdate_el is not None and pubdate_el.text else None
        if title:
            headlines.append({
                "title": title, "link": link, "source": source_name,
                "published_at": published_at.isoformat() if published_at else "",
            })
    return headlines


def get_reddit_crypto_posts(limit: int = 5) -> List[Dict[str, str]]:
    try:
        response = requests.get(
            REDDIT_CRYPTO_URL, timeout=_NEWS_SOURCE_TIMEOUT,
            headers={"User-Agent": "web:ai-crypto-analytics:2.2.0 (crypto sentiment aggregator)"},
        )
        response.raise_for_status()
        body = response.json()
        posts = body.get("data", {}).get("children", [])
        headlines: List[Dict[str, str]] = []
        for post in posts[:limit]:
            data = post.get("data", {})
            title = _clean_html(data.get("title", ""))
            if not title or data.get("stickied"):
                continue
            permalink = data.get("permalink", "")
            created_utc = data.get("created_utc")
            published_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat() if created_utc else ""
            headlines.append({
                "title": title,
                "link": f"https://reddit.com{permalink}" if permalink else "",
                "source": "r/CryptoCurrency",
                "published_at": published_at,
            })
        return headlines
    except Exception:  # noqa: BLE001
        return []


def get_crypto_headlines(limit: int = 8) -> Tuple[bool, List[Dict[str, str]], Optional[str]]:
    cache_key = f"headlines|{limit}"
    cached = _headlines_cache.get(cache_key)
    if cached is not None:
        return True, cached, None

    per_source_limit = max(2, limit // len(CRYPTO_NEWS_RSS_URLS) + 1)
    all_headlines: List[Dict[str, str]] = []
    errors: List[str] = []

    with ThreadPoolExecutor(max_workers=len(CRYPTO_NEWS_RSS_URLS) + 1) as pool:
        rss_futures = {pool.submit(_fetch_one_rss_source, url, per_source_limit): url for url in CRYPTO_NEWS_RSS_URLS}
        reddit_future = pool.submit(get_reddit_crypto_posts, 3)
        for future, url in rss_futures.items():
            try:
                all_headlines.extend(future.result())
            except (requests.exceptions.RequestException, ET.ParseError) as exc:
                errors.append(f"{url}: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{url}: {exc}")
        all_headlines.extend(reddit_future.result())

    if not all_headlines:
        stale = _headlines_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, "Pouzivam starsie cachovane spravy (vsetky zdroje zlyhali)."
        detail = "; ".join(errors) if errors else "Ziadny zdroj sprav nevratil data."
        return False, [], f"Nepodarilo sa nacitat spravy zo ziadneho zdroja: {detail}"

    all_headlines.sort(key=lambda h: h.get("published_at") or "", reverse=True)
    result = all_headlines[:limit]
    _headlines_cache.set(cache_key, result)
    return True, result, None



def get_upcoming_market_events(lang: str = "en", limit: int = 5,
                               today: Optional[date] = None) -> List[Dict[str, str]]:
    """Next scheduled macro events that move crypto markets, from the official calendar."""
    today = today or datetime.now(timezone.utc).date()
    labels = market_events_for_lang(lang)
    upcoming = sorted(
        (date.fromisoformat(day), kind) for day, kind in MARKET_EVENT_CALENDAR
        if date.fromisoformat(day) >= today and kind in labels
    )
    return [{"datum": day.strftime("%d.%m.%Y"), "udalost": labels[kind][0], "typ": labels[kind][1]}
            for day, kind in upcoming[:limit]]


from app.config import (  # noqa: E402
    COINGECKO_API_KEY, COINGECKO_SEARCH_URL, COINGECKO_SIMPLE_PRICE_URL, PRICE_CACHE_TTL_SECONDS,
)

_price_cache = TTLCache(ttl_seconds=PRICE_CACHE_TTL_SECONDS)
_market_chart_cache = TTLCache(ttl_seconds=PRICE_CACHE_TTL_SECONDS)


def clean_price_points(raw: Any) -> List[List[float]]:
    """Keeps only well-formed [timestamp, price] pairs with finite, positive prices."""
    points: List[List[float]] = []
    if not isinstance(raw, list):
        return points
    for item in raw:
        try:
            ts, price = float(item[0]), float(item[1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if math.isfinite(ts) and math.isfinite(price) and price > 0:
            points.append([ts, price])
    return points
_search_cache = TTLCache(ttl_seconds=300)
_history_cache = TTLCache(ttl_seconds=300)


def _cg_headers() -> Dict[str, str]:
    return {"x-cg-demo-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}


def get_live_prices(coin_ids: List[str], vs_currency: str = "usd", timeout: int = REQUEST_TIMEOUT_SECONDS) -> Tuple[bool, Optional[Dict[str, float]], Optional[str]]:
    if not coin_ids:
        return True, {}, None

    vs_currency = (vs_currency or "usd").lower()
    cache_key = ",".join(sorted(set(coin_ids))) + f"|{vs_currency}"

    cached = _price_cache.get(cache_key)
    if cached is not None:
        return True, cached, None

    try:
        response = requests.get(
            COINGECKO_SIMPLE_PRICE_URL,
            headers=_cg_headers(),
            params={"ids": cache_key.split("|")[0], "vs_currencies": vs_currency, "include_24hr_change": "true"},
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        prices: Dict[str, float] = {}
        for coin_id, values in (body.items() if isinstance(body, dict) else []):
            if isinstance(values, dict) and vs_currency in values:
                prices[coin_id] = {
                    vs_currency: float(values[vs_currency]),
                    f"{vs_currency}_24h_change": float(values.get(f"{vs_currency}_24h_change", 0.0) or 0.0),
                }
        _price_cache.set(cache_key, prices)
        return True, prices, None
    except requests.exceptions.RequestException as exc:
        stale = _price_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsie cachovane ceny (CoinGecko chyba: {exc})"
        return False, None, f"Chyba siete pri nacitani cien z CoinGecko: {exc}"
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        return False, None, f"Chyba pri spracovani odpovede CoinGecko: {exc}"


def get_market_chart(coin_id: str, vs_currency: str = "usd", days: str = "7", timeout: int = REQUEST_TIMEOUT_SECONDS) -> Tuple[bool, List[List[float]], Optional[str]]:
    vs_currency = (vs_currency or "usd").lower()
    cache_key = f"{coin_id}|{vs_currency}|{days}"
    cached = _market_chart_cache.get(cache_key)
    if cached is not None:
        return True, cached, None
    try:
        response = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            headers=_cg_headers(),
            params={"vs_currency": vs_currency, "days": days},
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        prices = clean_price_points(body.get("prices") if isinstance(body, dict) else None)
        if not prices:
            return False, [], "CoinGecko vratil prazdne alebo neplatne data grafu."
        _market_chart_cache.set(cache_key, prices)
        return True, prices, None
    except requests.exceptions.RequestException as exc:
        stale = _market_chart_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsie cachovane data (chyba: {exc})"
        return False, [], f"Chyba siete pri nacitani historickych cien: {exc}"
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        return False, [], f"Chyba pri spracovani historickych cien: {exc}"


def get_market_chart_range(coin_id: str, vs_currency: str, from_ts: int, to_ts: int) -> Tuple[bool, List[List[float]], Optional[str]]:
    vs_currency = (vs_currency or "usd").lower()
    cache_key = f"{coin_id}|{vs_currency}|{from_ts}|{to_ts}"
    cached = _market_chart_cache.get(cache_key)
    if cached is not None:
        return True, cached, None
    try:
        response = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range",
            headers=_cg_headers(),
            params={"vs_currency": vs_currency, "from": from_ts, "to": to_ts},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        prices = clean_price_points(body.get("prices") if isinstance(body, dict) else None)
        if not prices:
            return False, [], "CoinGecko vratil prazdne alebo neplatne data grafu."
        _market_chart_cache.set(cache_key, prices)
        return True, prices, None
    except requests.exceptions.RequestException as exc:
        stale = _market_chart_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsie cachovane data (chyba: {exc})"
        return False, [], f"Chyba siete pri nacitani historickych cien: {exc}"
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        return False, [], f"Chyba pri spracovani historickych cien: {exc}"


def search_coins(query: str, limit: int = 8) -> Tuple[bool, List[Dict[str, str]], Optional[str]]:
    query = (query or "").strip()
    if not query:
        return True, [], None
    cache_key = f"{query.lower()}|{limit}"
    cached = _search_cache.get(cache_key)
    if cached is not None:
        return True, cached, None
    try:
        response = requests.get(
            COINGECKO_SEARCH_URL, params={"query": query}, headers=_cg_headers(), timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        coins = body.get("coins", []) if isinstance(body, dict) else []
        result = [
            {"id": str(c.get("id")), "symbol": str(c.get("symbol", "")).upper(), "name": str(c.get("name", ""))}
            for c in (coins if isinstance(coins, list) else []) if isinstance(c, dict) and c.get("id")
        ][:limit]
        _search_cache.set(cache_key, result)
        return True, result, None
    except requests.exceptions.RequestException as exc:
        return False, [], f"Chyba siete pri vyhladavani mincí: {exc}"
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        return False, [], f"Chyba pri spracovani vysledkov vyhladavania: {exc}"


def get_market_history(coin_id: str, days: int = 30, timeout: int = REQUEST_TIMEOUT_SECONDS) -> Tuple[bool, Dict[str, List[List[float]]], Optional[str]]:
    cache_key = f"{coin_id}|{days}"
    cached = _history_cache.get(cache_key)
    if cached is not None:
        return True, cached, None
    try:
        response = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days}, headers=_cg_headers(), timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        data = {"prices": body.get("prices", []), "volumes": body.get("total_volumes", [])}
        if len(data["prices"]) < 2:
            return False, {}, "CoinGecko vratil prilis malo historickych dat."
        _history_cache.set(cache_key, data)
        return True, data, None
    except Exception as exc:  # noqa: BLE001
        stale = _history_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, None
        return False, {}, f"Chyba pri nacitani historickych dat: {exc}"


_markets_cache = TTLCache(ttl_seconds=120)


def get_coin_markets(coin_ids: List[str], timeout: int = REQUEST_TIMEOUT_SECONDS) -> Tuple[bool, Dict[str, Dict[str, Any]], Optional[str]]:
    ids = sorted({c for c in coin_ids if c})[:50]
    if not ids:
        return True, {}, None
    cache_key = ",".join(ids)
    cached = _markets_cache.get(cache_key)
    if cached is not None:
        return True, cached, None
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "ids": cache_key, "price_change_percentage": "24h,7d,30d"},
            headers=_cg_headers(), timeout=timeout,
        )
        response.raise_for_status()
        rows = {row["id"]: row for row in response.json() if isinstance(row, dict) and row.get("id")}
        _markets_cache.set(cache_key, rows)
        return True, rows, None
    except Exception as exc:  # noqa: BLE001
        stale = _markets_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, None
        return False, {}, f"Chyba pri nacitani trhovych dat portfolia: {exc}"
