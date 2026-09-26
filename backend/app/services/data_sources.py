"""app/services/data_sources.py — dalsie BEZPLATNE zdroje dat pre AI analyzu.

Kazda funkcia vracia kratky textovy riadok (alebo slovnik) pre AI prompt,
alebo None, ak zdroj nie je dostupny. NIKDY nevyhodi vynimku - vypadok
jedneho zdroja nesmie ovplyvnit ostatne ani zhodit analyzu. Vsetko ma
kratky timeout a cache (setri limity bezplatnych API a zrychluje appku).

Zdroje a kluce (vsetky volitelne - bez kluca sa zdroj jednoducho preskoci
alebo funguje v obmedzenom rezime):
- CoinGecko (COINGECKO_API_KEY): profil mince (kategoria, rank, ATH), spravy o minci
- Hyperliquid (bez kluca): funding rate a open interest z perpetual futures
- Blockchair (BLOCKCHAIR_API_KEY volitelne): on-chain aktivita a velryby (BTC, ETH, DOGE)
- DefiLlama (bez kluca): TVL siete (kolko kapitalu je v DeFi na danej sieti)
- GitHub (GITHUB_TOKEN volitelne): aktivita vyvojarov projektu
- Reddit (bez kluca): hlas komunity konkretnej mince
- FRED (FRED_API_KEY): makro - sadzby Fedu, inflacia, dolar, S&P 500, dluhopisy
- GDELT (bez kluca): svetove spravy - politika, sankcie, clo, regulacia
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from app.config import BLOCKCHAIR_API_KEY, COINGECKO_API_KEY, FRED_API_KEY, GITHUB_TOKEN
from app.services.market_data import _cg_headers, _clean_html
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger("aca.sources")

_TIMEOUT = 5
_REDDIT_UA = {"User-Agent": "web:ai-crypto-analytics:2.2.0 (crypto sentiment aggregator)"}
_fast_cache = TTLCache(ttl_seconds=300)     # deriváty - menia sa rýchlo
_med_cache = TTLCache(ttl_seconds=900)      # správy, on-chain, Reddit
_slow_cache = TTLCache(ttl_seconds=21600)   # profil mince, TVL, makro, GitHub (6 h)

# Aký typ mince -> na čo sa má AI pri analýze pozerať najviac.
TYPE_GUIDANCE = {
    "meme": "Typ mince: MEME coin - cenu hybe hlavne socialny hype, pozornost komunity a velryby; "
            "fundamenty maju malu vahu, volatilita byva extremna.",
    "defi": "Typ mince: DeFi projekt - dolezite su TVL, tok kapitalu v DeFi a regulacia.",
    "l1": "Typ mince: L1/L2 siet - dolezita je aktivita siete (on-chain, TVL), vyvoj projektu a trend BTC.",
}


def _redact(text: str) -> str:
    for secret in (FRED_API_KEY, BLOCKCHAIR_API_KEY, GITHUB_TOKEN, COINGECKO_API_KEY):
        if secret:
            text = text.replace(secret, "***")
    return text


def _get_json(url: str, cache: TTLCache, key: str, params: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None, method: str = "GET", body: Any = None) -> Any:
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        if method == "POST":
            response = requests.post(url, json=body, headers=headers or {}, timeout=_TIMEOUT)
        else:
            response = requests.get(url, params=params, headers=headers or {}, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - zdroj je bonus, nikdy nesmie zhodit analyzu
        logger.info("Zdroj %s nedostupny: %s", url.split("?")[0], _redact(str(exc))[:200])
        return cache.get(key, allow_stale=True)
    cache.set(key, data)
    return data


def _titles(items: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    out = []
    for item in items:
        title = _clean_html(str(item.get("title") or ""))[:100]
        if title:
            out.append(title)
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------
# CoinGecko - profil a správy konkrétnej mince
# --------------------------------------------------------------------------
def coin_profile(coin_id: str) -> Optional[Dict[str, Any]]:
    data = _get_json(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}", _slow_cache, f"profile|{coin_id}",
        params={"localization": "false", "tickers": "false", "market_data": "true",
                "community_data": "false", "developer_data": "false", "sparkline": "false"},
        headers=_cg_headers(),
    )
    if not isinstance(data, dict):
        return None
    market = data.get("market_data") or {}
    links = data.get("links") or {}
    circulating, max_supply = market.get("circulating_supply"), market.get("max_supply")
    repos = (links.get("repos_url") or {}).get("github") or []
    return {
        "categories": [c for c in (data.get("categories") or []) if c][:4],
        "rank": data.get("market_cap_rank"),
        "ath_change_pct": (market.get("ath_change_percentage") or {}).get("usd"),
        "supply_ratio": circulating / max_supply if circulating and max_supply else None,
        "github": repos[0] if repos else "",
        "subreddit": links.get("subreddit_url") or "",
    }


def coin_type(categories: List[str]) -> str:
    text = " ".join(categories).lower()
    if "meme" in text:
        return "meme"
    if "decentralized finance" in text or "defi" in text:
        return "defi"
    if "layer 1" in text or "layer 2" in text or "smart contract" in text:
        return "l1"
    return "other"


def profile_line(profile: Dict[str, Any]) -> Optional[str]:
    parts = []
    if profile.get("categories"):
        parts.append("kategorie: " + ", ".join(profile["categories"]))
    if profile.get("rank"):
        parts.append(f"rank #{profile['rank']}")
    if isinstance(profile.get("ath_change_pct"), (int, float)):
        parts.append(f"{profile['ath_change_pct']:+.0f}% od historickeho maxima")
    if profile.get("supply_ratio"):
        parts.append(f"v obehu {profile['supply_ratio'] * 100:.0f}% max. ponuky")
    return "Profil mince: " + " | ".join(parts) if parts else None


def coin_news(coin_id: str) -> Optional[str]:
    data = _get_json("https://api.coingecko.com/api/v3/news", _med_cache, f"cgnews|{coin_id}",
                     params={"coin_id": coin_id, "per_page": 5}, headers=_cg_headers())
    items = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
    titles = _titles(items or [])
    return "Spravy o tejto minci (CoinGecko): " + "; ".join(titles) if titles else None


# --------------------------------------------------------------------------
# Hyperliquid - deriváty (funding rate, open interest), bez kľúča
# --------------------------------------------------------------------------
def derivatives(symbol: str) -> Optional[str]:
    data = _get_json("https://api.hyperliquid.xyz/info", _fast_cache, "hyperliquid",
                     method="POST", body={"type": "metaAndAssetCtxs"})
    try:
        universe, contexts = data[0]["universe"], data[1]
        index = next(i for i, asset in enumerate(universe) if asset.get("name") == symbol.upper())
        ctx = contexts[index]
        funding = float(ctx["funding"]) * 100
        open_interest_usd = float(ctx["openInterest"]) * float(ctx["markPx"])
    except Exception:  # noqa: BLE001 - minca nemusi mat perpetual kontrakt
        return None
    return (f"Derivaty (Hyperliquid perp): funding {funding:+.4f}%/h "
            f"({'longy platia shortom' if funding > 0 else 'shorty platia longom'}) | "
            f"open interest ${open_interest_usd / 1e6:,.0f}M")


# --------------------------------------------------------------------------
# Blockchair - on-chain aktivita a veľryby (BTC, ETH, DOGE)
# --------------------------------------------------------------------------
_BLOCKCHAIR_CHAINS = {
    "bitcoin": ("bitcoin", "output_total_usd", 1_000_000),
    "ethereum": ("ethereum", "value_usd", 1_000_000),
    "dogecoin": ("dogecoin", "output_total_usd", 250_000),
}


def onchain_stats(coin_id: str) -> Optional[Dict[str, Any]]:
    """On-chain aktivita a velryby ako strukturovane data (karta na stranke Trh)."""
    config = _BLOCKCHAIR_CHAINS.get(coin_id)
    if not config:
        return None
    chain, field, threshold = config
    key_param = {"key": BLOCKCHAIR_API_KEY} if BLOCKCHAIR_API_KEY else {}
    result: Dict[str, Any] = {"chain": chain, "whale_threshold_usd": threshold}

    stats = _get_json(f"https://api.blockchair.com/{chain}/stats", _med_cache, f"bc-stats|{chain}", params=key_param or None)
    stats_data = stats.get("data") if isinstance(stats, dict) else None
    if isinstance(stats_data, dict):
        if stats_data.get("transactions_24h"):
            result["transactions_24h"] = int(stats_data["transactions_24h"])
        if stats_data.get("mempool_transactions") is not None:
            result["mempool_transactions"] = int(stats_data["mempool_transactions"])

    whales = _get_json(f"https://api.blockchair.com/{chain}/transactions", _med_cache, f"bc-whales|{chain}",
                       params={"q": f"{field}({threshold}..)", "s": "time(desc)", "limit": 10, **key_param})
    rows = whales.get("data") if isinstance(whales, dict) else None
    if rows:
        values = [float(row.get(field) or 0) for row in rows]
        times = []
        for row in rows:
            try:
                times.append(datetime.strptime(str(row["time"]), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc))
            except (KeyError, ValueError):
                continue
        result.update({
            "whale_count": len(rows), "whale_total_usd": sum(values), "whale_max_usd": max(values),
            "whale_span_hours": round((datetime.now(timezone.utc) - min(times)).total_seconds() / 3600, 1) if times else None,
        })
    return result if len(result) > 2 else None


def onchain(coin_id: str) -> Optional[str]:
    """Textovy riadok pre AI prompt (z onchain_stats)."""
    stats = onchain_stats(coin_id)
    if not stats:
        return None
    parts = []
    if stats.get("transactions_24h"):
        parts.append(f"{stats['transactions_24h']:,} transakcii za 24h")
    if stats.get("mempool_transactions") is not None:
        parts.append(f"mempool {stats['mempool_transactions']:,} cakajucich")
    if stats.get("whale_count"):
        span = f" za {stats['whale_span_hours']:.1f}h" if stats.get("whale_span_hours") is not None else ""
        parts.append(f"velryby (presuny nad ${stats['whale_threshold_usd'] / 1e6:g}M): poslednych {stats['whale_count']}{span}, "
                     f"spolu ${stats['whale_total_usd'] / 1e6:,.0f}M, najvacsi ${stats['whale_max_usd'] / 1e6:,.0f}M")
    return f"On-chain {stats['chain']} (Blockchair): " + " | ".join(parts) if parts else None


# --------------------------------------------------------------------------
# DefiLlama - TVL siete, bez kľúča
# --------------------------------------------------------------------------
def chain_tvl(coin_id: str) -> Optional[str]:
    chains = _get_json("https://api.llama.fi/v2/chains", _slow_cache, "llama|chains")
    if not isinstance(chains, list):
        return None
    match = next((c for c in chains if isinstance(c, dict) and c.get("gecko_id") == coin_id), None)
    if not match or not match.get("tvl"):
        return None
    name, tvl = match.get("name", ""), float(match["tvl"])
    parts = [f"DeFi TVL siete {name}: ${tvl / 1e9:,.2f}B"]
    history = _get_json(f"https://api.llama.fi/v2/historicalChainTvl/{quote(name)}", _slow_cache, f"llama|hist|{name}")
    if isinstance(history, list) and len(history) > 31:
        last = float(history[-1].get("tvl") or 0)
        for label, back in (("7d", 8), ("30d", 31)):
            old = float(history[-back].get("tvl") or 0)
            if old:
                parts.append(f"{label} {(last / old - 1) * 100:+.1f}%")
    return " | ".join(parts)


# --------------------------------------------------------------------------
# GitHub - aktivita vývojárov
# --------------------------------------------------------------------------
def github_activity(repo_url: str) -> Optional[str]:
    match = re.match(r"https?://github\.com/([^/\s]+)/([^/\s#?]+)", repo_url or "")
    if not match:
        return None
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    data = _get_json(f"https://api.github.com/repos/{owner}/{repo}/commits", _slow_cache, f"gh|{owner}/{repo}",
                     params={"since": since, "per_page": 100}, headers=headers)
    if not isinstance(data, list):
        return None
    count = "100+" if len(data) >= 100 else str(len(data))
    return f"Vyvoj projektu (GitHub {owner}/{repo}): {count} commitov za 30 dni"


# --------------------------------------------------------------------------
# Reddit - komunita konkrétnej mince
# --------------------------------------------------------------------------
def coin_subreddit(subreddit_url: str) -> Optional[str]:
    match = re.search(r"reddit\.com/r/([A-Za-z0-9_]+)", subreddit_url or "")
    if not match:
        return None
    name = match.group(1)
    data = _get_json(f"https://www.reddit.com/r/{name}/hot.json", _med_cache, f"reddit|{name}",
                     params={"limit": 8}, headers=_REDDIT_UA)
    posts = ((data.get("data") or {}).get("children") or []) if isinstance(data, dict) else []
    titles = _titles([p.get("data", {}) for p in posts if not p.get("data", {}).get("stickied")])
    return f"Komunita r/{name}: " + "; ".join(titles) if titles else None


# --------------------------------------------------------------------------
# FRED - makroekonomika (vyžaduje bezplatný FRED_API_KEY)
# --------------------------------------------------------------------------
def _fred(series_id: str, limit: int) -> List[float]:
    data = _get_json("https://api.stlouisfed.org/fred/series/observations", _slow_cache, f"fred|{series_id}",
                     params={"series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json",
                             "sort_order": "desc", "limit": limit})
    values = []
    for obs in (data.get("observations") or []) if isinstance(data, dict) else []:
        try:
            values.append(float(obs["value"]))
        except (KeyError, TypeError, ValueError):
            continue  # FRED oznacuje chybajuce hodnoty ako "."
    return values  # najnovsie prve


def macro_summary() -> Optional[str]:
    if not FRED_API_KEY:
        return None
    parts = []
    fed = _fred("FEDFUNDS", 2)
    if fed:
        parts.append(f"sadzba Fedu {fed[0]:.2f}%")
    cpi = _fred("CPIAUCSL", 14)
    if len(cpi) >= 13:
        parts.append(f"inflacia CPI {(cpi[0] / cpi[12] - 1) * 100:+.1f}% r/r")
    dollar = _fred("DTWEXBGS", 30)
    if len(dollar) >= 21:
        parts.append(f"index dolara {(dollar[0] / dollar[20] - 1) * 100:+.1f}% za mesiac")
    sp500 = _fred("SP500", 10)
    if len(sp500) >= 6:
        parts.append(f"S&P 500 {(sp500[0] / sp500[5] - 1) * 100:+.1f}% za tyzden")
    bond = _fred("DGS10", 5)
    if bond:
        parts.append(f"10r US dlhopis {bond[0]:.2f}%")
    return "Makro (FRED): " + " | ".join(parts) if parts else None


# --------------------------------------------------------------------------
# GDELT - svetové dianie (politika, sankcie, clá, regulácia), bez kľúča
# --------------------------------------------------------------------------
def world_news() -> Optional[str]:
    data = _get_json(
        "https://api.gdeltproject.org/api/v2/doc/doc", _med_cache, "gdelt",
        params={"query": '(cryptocurrency OR bitcoin OR "federal reserve" OR tariffs OR sanctions) sourcelang:english',
                "mode": "artlist", "maxrecords": 6, "format": "json", "timespan": "24h", "sort": "hybridrel"},
    )
    titles = _titles((data.get("articles") or []) if isinstance(data, dict) else [], limit=4)
    return "Svetove dianie (GDELT, 24h): " + "; ".join(titles) if titles else None
