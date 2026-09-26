"""
app/services/market_data.py
=============================
Integracia verejnych, bezplatnych API pre trhove data (Fear & Greed Index,
RSS krypto spravy) plus staticke udalosti. Ziadna funkcia nikdy nepusti
nezachytenu vynimku von.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.config import CRYPTO_NEWS_RSS_URLS, FEAR_GREED_API_URL, REDDIT_CRYPTO_URL, REQUEST_TIMEOUT_SECONDS
from app.i18n_content import market_events_for_lang
from app.utils.ttl_cache import TTLCache

# Alternative.me sa realne prepocitava len ~raz za 24h, takze nema zmysel
# bombardovat ho pri kazdom nacitani stranky. Kratky cache (15 min) znizuje
# zataz a zaroven chrani pred tym, aby doslo k tichemu MOCK fallbacku
# kvoli prilis castym requestom.
_fear_greed_cache = TTLCache(ttl_seconds=900)  # 15 min
_FEAR_GREED_KEY = "fear_greed"

_DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AICryptoAnalytics/2.0)"}

# Kratky timeout pre JEDNOTLIVE zdroje sprav (nacitavaju sa paralelne) - viz
# vysvetlenie pri get_crypto_headlines(). Spravy sa cachuju 5 minut.
_NEWS_SOURCE_TIMEOUT = 5
_headlines_cache = TTLCache(ttl_seconds=300)


def get_fear_greed_index(force_refresh: bool = False) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """force_refresh=True obchadza cache (manualne "Aktualizovat" tlacidlo na
    Dashboarde) - hodnota sa aj tak na zdroji (alternative.me) meni len raz
    denne o polnoci UTC, takze aj po obnoveni bude casto rovnaka, ale
    pouzivatel tym ziska istotu, ze vidi naozaj cerstvo overenu hodnotu."""
    if not force_refresh:
        cached = _fear_greed_cache.get(_FEAR_GREED_KEY)
        if cached is not None:
            return True, cached, None

    try:
        # Bez User-Agent hlavicky vie Cloudflare pred alternative.me
        # obcas vratit 403 a appka by ticho spadla do MOCK rezimu.
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
            "value": int(latest.get("value", 50)),
            "classification": str(latest.get("value_classification", "Nezname")),
            "timestamp": raw_ts,
            "updated_at": updated_at,
        }
        _fear_greed_cache.set(_FEAR_GREED_KEY, data)
        return True, data, None
    except requests.exceptions.RequestException as exc:
        # Ak mame stary cache (aj expirovany), radsej ho vratime (oznaceny ako
        # mierne zastaraly) nez appku hodit do MOCK rezimu s vymyslenou hodnotou 50.
        stale = _fear_greed_cache.get(_FEAR_GREED_KEY, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsiu cachovanu hodnotu (chyba siete: {exc})"
        return False, None, f"Chyba siete pri nacitani Fear & Greed Index: {exc}"
    except (ValueError, KeyError, TypeError) as exc:
        return False, None, f"Chyba pri spracovani Fear & Greed Index: {exc}"


def get_dummy_fear_greed_index() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {"value": 50, "classification": "[DUMMY] Neutral",
            "timestamp": str(int(now.timestamp())), "updated_at": now.isoformat()}


_TAG_STRIP_PATTERN = re.compile(r"<[^>]+>")


def _clean_html(text: str) -> str:
    if not text:
        return ""
    return _TAG_STRIP_PATTERN.sub("", text).strip()


def _parse_rss_date(raw: str) -> Optional[datetime]:
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Vzdy prevod na UTC - rozne RSS zdroje posielaju rozne casove pasma
        # (+0000, -0400...), a zoradovanie ISO retazcov s roznymi offsetmi
        # by bolo nespravne (textove porovnanie, nie casove).
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_one_rss_source(url: str, per_source_limit: int) -> List[Dict[str, str]]:
    """Nacita a sparsuje JEDEN RSS feed. Volajuce get_crypto_headlines() to
    obali try/except per-zdroj, takze vypadok jedneho feedu (napr. docasne
    nedostupny CoinTelegraph) nezhodi zvysne zdroje."""
    response = requests.get(url, timeout=_NEWS_SOURCE_TIMEOUT, headers=_DEFAULT_HEADERS)
    response.raise_for_status()
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
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        published_at = _parse_rss_date(pubdate_el.text) if pubdate_el is not None and pubdate_el.text else None
        if title:
            headlines.append({
                "title": title, "link": link, "source": source_name,
                "published_at": published_at.isoformat() if published_at else "",
            })
    return headlines


def get_reddit_crypto_posts(limit: int = 5) -> List[Dict[str, str]]:
    """Hot prispevky z r/CryptoCurrency cez verejne, bez-prihlasovacie JSON
    API Redditu - dava appke aj skutocny "hlas komunity", nie len redakcne
    spravy. Nikdy nevyhodi vynimku von (prazdny zoznam pri akomkolvek
    zlyhani) - je to bonusovy zdroj, ziadny ineho zdroj naň nespolieha.
    POZNAMKA: na rozdiel od RSS feedov Reddit obcas blokuje pozadavky z
    datacentrovych IP adries (typicky aj hosting ako Render) bez ohladu na
    spravny User-Agent - ak sa to deje, funkcia jednoducho vrati prazdny
    zoznam a appka pokracuje len s RSS zdrojmi."""
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
            if not title or data.get("stickied"):  # pripnute posty su zvycajne pravidla subredditu, nie spravy
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
    except Exception:  # noqa: BLE001 - bonusovy zdroj, nikdy nesmie zhodit hlavnu funkciu
        return []


def get_crypto_headlines(limit: int = 8) -> Tuple[bool, List[Dict[str, str]], Optional[str]]:
    """Agreguje titulky z VIACERYCH nezavislych RSS zdrojov (viz
    CRYPTO_NEWS_RSS_URLS v config.py) plus Reddit - diverzifikuje spravy
    naprieč viacerymi redakciami namiesto jedneho pohladu. Kazdy zdroj je
    izolovany (vypadok jedneho neovplyvni zvysne). Vysledky su zoradene
    podla casu publikovania (najnovsie prve).

    DOLEZITE (casovy rozpocet): zdroje sa nacitavaju PARALELNE (nie jeden
    po druhom) a s kratkym timeoutom na zdroj. Pri sekvencnom nacitani 4
    zdrojov s plnym timeoutom mohol najhorsi pripad trvat az ~48s - co by
    samo o sebe prekrocilo ~40s limit Netlify proxy (502 chyba), a pri
    Daily Digest by sa k tomu este pridalo AI volanie. Paralelne + kratky
    timeout = najhorsi pripad cca _NEWS_SOURCE_TIMEOUT sekund celkovo.
    Vysledok sa navyse cachuje, aby opakovane nacitania stranky nevolali
    vsetky zdroje znova."""
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
            except Exception as exc:  # noqa: BLE001 - jeden zly zdroj nesmie zhodit ostatne
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


def get_dummy_crypto_headlines(limit: int = 6) -> List[Dict[str, str]]:
    templates = [
        "Bitcoin dosahuje nove lokalne maximum uprostred institucionalneho zaujmu",
        "Regulatori vysetruju velku burzu kvoli suladu s predpismi",
        "Ethereum upgrade slubuje nizsie transakcne poplatky",
        "Trh kryptomien zaznamenava vypredaj po makroekonomickych datach",
        "DeFi protokol oznamuje partnerstvo s tradicnou bankou",
        "Nova L2 siet prekonala milnik v pocte dennych transakcii",
    ]
    now = datetime.now(timezone.utc)
    return [
        {
            "title": f"[DUMMY] {t}", "link": "#", "source": "Demo Zdroj",
            "published_at": (now - timedelta(hours=i * 2 + 1)).isoformat(),
        }
        for i, t in enumerate(templates[:limit])
    ]


def get_upcoming_market_events(lang: str = "en") -> List[Dict[str, str]]:
    today = datetime.now(timezone.utc).date()
    result = []
    for event in market_events_for_lang(lang):
        event_date = today + timedelta(days=int(event["offset_days"]))
        result.append({"datum": event_date.strftime("%d.%m.%Y"), "udalost": event["event"], "typ": event["type"]})
    return result


# ---------------------------------------------------------------------------
# Live ceny (CoinGecko) s jednoduchou in-memory cache (TTL), aby sme
# neprekrocili rate limit bezplatneho CoinGecko API (chyba 429).
# ---------------------------------------------------------------------------
from app.config import (  # noqa: E402
    COINGECKO_API_KEY, COINGECKO_SEARCH_URL, COINGECKO_SIMPLE_PRICE_URL, PRICE_CACHE_TTL_SECONDS,
)

_price_cache = TTLCache(ttl_seconds=PRICE_CACHE_TTL_SECONDS)
_market_chart_cache = TTLCache(ttl_seconds=PRICE_CACHE_TTL_SECONDS)
_search_cache = TTLCache(ttl_seconds=300)  # vyhladavacie vysledky sa menia zriedka
_history_cache = TTLCache(ttl_seconds=300)  # 30d historia pre AI predikcie - 5 min staci, setri limit


def _cg_headers() -> Dict[str, str]:
    """Hlavicka s CoinGecko Demo klucom, ak je nastaveny (viz config.py)."""
    return {"x-cg-demo-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}


def get_live_prices(coin_ids: List[str], vs_currency: str = "usd", timeout: int = REQUEST_TIMEOUT_SECONDS) -> Tuple[bool, Optional[Dict[str, float]], Optional[str]]:
    """Vrati ceny pre zoznam CoinGecko id v zvolenej mene (usd/eur/czk/btc).
    Vysledky su cachovane na PRICE_CACHE_TTL_SECONDS (predvolene 60s), aby
    opakovane requesty z frontendu (napr. prepocet portfolia) nevolali
    CoinGecko znova a znova. `timeout` je nastavitelny - pri volani z
    _fetch_market_context() (ai_engine.py) sa pouziva kratsi limit, aby
    tieto dve "bonusove" volania nezjedli cely casovy rozpocet requestu este
    predtym, nez vobec zacne samotne (pomalsie) volanie AI providera."""
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
        for coin_id, values in body.items():
            if isinstance(values, dict) and vs_currency in values:
                prices[coin_id] = {
                    vs_currency: float(values[vs_currency]),
                    f"{vs_currency}_24h_change": float(values.get(f"{vs_currency}_24h_change", 0.0) or 0.0),
                }
        _price_cache.set(cache_key, prices)
        return True, prices, None
    except requests.exceptions.RequestException as exc:
        # Ak mame stary cache (aj expirovany), radsej ho vratime nez zlyhat celkom.
        stale = _price_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsie cachovane ceny (CoinGecko chyba: {exc})"
        return False, None, f"Chyba siete pri nacitani cien z CoinGecko: {exc}"
    except (ValueError, KeyError, TypeError) as exc:
        return False, None, f"Chyba pri spracovani odpovede CoinGecko: {exc}"


def get_market_chart(coin_id: str, vs_currency: str = "usd", days: str = "7", timeout: int = REQUEST_TIMEOUT_SECONDS) -> Tuple[bool, List[List[float]], Optional[str]]:
    """Historicke cenove data pre interaktivny graf (Trhovy Sentiment stranka):
    zoom/prepinanie casovych ramcov. Vracia zoznam [timestamp_ms, cena].
    `timeout` viz get_live_prices() vyssie - rovnaky dovod."""
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
        prices = body.get("prices", [])
        _market_chart_cache.set(cache_key, prices)
        return True, prices, None
    except requests.exceptions.RequestException as exc:
        stale = _market_chart_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsie cachovane data (chyba: {exc})"
        return False, [], f"Chyba siete pri nacitani historickych cien: {exc}"
    except (ValueError, KeyError, TypeError) as exc:
        return False, [], f"Chyba pri spracovani historickych cien: {exc}"


def get_market_chart_range(coin_id: str, vs_currency: str, from_ts: int, to_ts: int) -> Tuple[bool, List[List[float]], Optional[str]]:
    """Historicke cenove data za PRESNY casovy rozsah (unix timestampy, sekundy)
    - na rozdiel od get_market_chart() (vzdy "poslednych N dni od TERAZ"), toto
    vie zohnat cenu za lubovolne OBDOBIE V MINULOSTI. Pouzite na spatne
    porovnanie ulozenej predikcie so skutocnym vyvojom ceny (viz
    ai_engine.py::compute_forecast_accuracy) - predikcia mohla byt vytvorena
    pred tyzdnami, takze "poslednych 7 dni od teraz" by mierilo na uplne iny
    casovy usek, nez ktory predikcia v skutocnosti pokryvala."""
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
        prices = body.get("prices", [])
        _market_chart_cache.set(cache_key, prices)
        return True, prices, None
    except requests.exceptions.RequestException as exc:
        stale = _market_chart_cache.get(cache_key, allow_stale=True)
        if stale is not None:
            return True, stale, f"Pouzivam starsie cachovane data (chyba: {exc})"
        return False, [], f"Chyba siete pri nacitani historickych cien: {exc}"
    except (ValueError, KeyError, TypeError) as exc:
        return False, [], f"Chyba pri spracovani historickych cien: {exc}"


def search_coins(query: str, limit: int = 8) -> Tuple[bool, List[Dict[str, str]], Optional[str]]:
    """Vyhladavanie ktorejkolvek mincy podporovanej na CoinGecko (pre custom
    vyber mincí v Portfolio Advisor aj globalne vyhladavanie v hlavicke),
    s kratkym cachovanim opakovanych dopytov."""
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
        coins = body.get("coins", [])[:limit]
        result = [
            {"id": c.get("id", ""), "symbol": str(c.get("symbol", "")).upper(), "name": c.get("name", "")}
            for c in coins if c.get("id")
        ]
        _search_cache.set(cache_key, result)
        return True, result, None
    except requests.exceptions.RequestException as exc:
        return False, [], f"Chyba siete pri vyhladavani mincí: {exc}"
    except (ValueError, KeyError, TypeError) as exc:
        return False, [], f"Chyba pri spracovani vysledkov vyhladavania: {exc}"


def get_market_history(coin_id: str, days: int = 30, timeout: int = REQUEST_TIMEOUT_SECONDS) -> Tuple[bool, Dict[str, List[List[float]]], Optional[str]]:
    """30-dnova hodinova historia ceny A objemu v JEDNOM volani (predtym 2
    samostatne volania len na cenu a 7d graf) - zaklad pre technicke
    indikatory v AI predikciach (viz ai_engine._summarize_history)."""
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
    """Cena, rank a zmeny 24h/7d/30d pre VIAC mincí v JEDNOM volani (pre
    analyzu portfolia - az 30 mincí by inak znamenalo 30 volani)."""
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
