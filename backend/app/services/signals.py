"""Market signals from public, keyless sources: derivatives, options, liquidations, capital flows, the whole market,
the Bitcoin network, macro and traditional markets, the event calendar, regulators and prediction markets.

Every source is optional: a source that fails or is blocked in the server's region is skipped. Each signal carries a
plain number for the UI and a line of context for the AI models, with a hint of how traders usually read it."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional

import requests

from app.utils.ttl_cache import TTLCache

logger = logging.getLogger("aca.signals")

_UA = {"User-Agent": "ai-crypto-analytics/2.4 (market research; contact aicryptoanalytics7@gmail.com)"}
_TIMEOUT = 8
_fast = TTLCache(ttl_seconds=300)        # derivatives, prices
_medium = TTLCache(ttl_seconds=900)      # options, stablecoins, network, regulators
_slow = TTLCache(ttl_seconds=6 * 3600)   # daily macro series
_bundle = TTLCache(ttl_seconds=300)

GROUPS = ("derivatives", "options", "flows", "market", "network", "macro", "events", "regulation", "predictions")
OPTION_COINS = ("BTC", "ETH")
# Perpetual symbols where the exchanges quote 1000 units.
_BINANCE = {"SHIB": "1000SHIBUSDT", "PEPE": "1000PEPEUSDT"}
_BYBIT = {"SHIB": "SHIB1000USDT", "PEPE": "1000PEPEUSDT"}
CRYPTO_WORDS = re.compile(r"crypto|bitcoin|ether|digital asset|token|stablecoin|blockchain|defi|coinbase|binance", re.I)


# Short names for e-mails and Telegram (the web app has its own translations).
LABELS = {
    "funding": ("Funding", "Funding", "Funding"), "open_interest": ("Open interest", "Open interest", "Open interest"),
    "long_short": ("Long/short ratio", "Pomer long/short", "Poměr long/short"),
    "liquidations": ("Liquidations", "Likvidácie", "Likvidace"), "put_call": ("Options put/call", "Opcie put/call", "Opce put/call"),
    "dvol": ("Implied volatility", "Implikovaná volatilita", "Implikovaná volatilita"),
    "stablecoins": ("Stablecoin supply", "Zásoba stablecoinov", "Zásoba stablecoinů"),
    "coinbase_premium": ("Coinbase premium", "Coinbase prémia", "Coinbase prémie"),
    "btc_dominance": ("BTC dominance", "Dominancia BTC", "Dominance BTC"),
    "total_cap": ("Crypto market cap", "Kapitalizácia trhu", "Kapitalizace trhu"),
    "btc_fees": ("BTC fees", "Poplatky BTC", "Poplatky BTC"), "hashrate": ("Hashrate", "Hashrate", "Hashrate"),
    "vix": ("VIX", "VIX", "VIX"), "nasdaq": ("Nasdaq", "Nasdaq", "Nasdaq"), "sp500": ("S&P 500", "S&P 500", "S&P 500"),
    "dollar": ("US dollar", "Americký dolár", "Americký dolar"), "us10y": ("US 10y yield", "Výnos 10r dlhopisu USA", "Výnos 10l dluhopisu USA"),
    "oil": ("Oil", "Ropa", "Ropa"), "fed_rate": ("Fed rate", "Sadzba Fedu", "Sazba Fedu"),
    "inflation": ("US inflation", "Inflácia USA", "Inflace USA"), "gold": ("Gold", "Zlato", "Zlato"),
    "event": ("Calendar", "Kalendár", "Kalendář"), "regulator_news": ("Regulators", "Regulátori", "Regulátoři"),
    "polymarket": ("Polymarket", "Polymarket", "Polymarket"),
}


def headline(items: List[Dict[str, Any]], lang: str, limit: int = 4) -> List[str]:
    """The strongest non-neutral signals as short lines, e.g. "Funding: +0.0450% / 8h ▼"."""
    idx = {"en": 0, "sk": 1, "cs": 2}.get(lang, 0)
    picked = [s for s in items if s["tone"] != "neutral"][:limit]
    return [f"{LABELS.get(s['key'], (s['key'],) * 3)[idx]}: {s['display']} {'▲' if s['tone'] == 'bullish' else '▼'}" for s in picked]


def signal(group: str, key: str, value: Optional[float], display: str, tone: str, source: str, note: str) -> Dict[str, Any]:
    return {"group": group, "key": key, "value": value, "display": display, "tone": tone, "source": source, "note": note}


def _get(url: str, cache: TTLCache, params: Optional[dict] = None, as_text: bool = False) -> Any:
    key = url + json.dumps(params or {}, sort_keys=True)
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        res = requests.get(url, params=params, headers=_UA, timeout=_TIMEOUT)
        res.raise_for_status()
        data = res.text if as_text else res.json()
    except Exception as exc:  # noqa: BLE001 - any failure just skips the source
        logger.info("Signal source %s unavailable: %s", url.split("?")[0], type(exc).__name__)
        return cache.get(key, allow_stale=True)
    cache.set(key, data)
    return data


def _f(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _pct(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}%"


def _usd(value: float) -> str:
    for size, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= size:
            return f"${value / size:.2f}{suffix}"
    return f"${value:,.0f}"


# ---------- derivatives ----------

def funding_tone(rate_pct: float) -> str:
    if rate_pct >= 0.03:
        return "bearish"          # longs pay a lot: crowded, prone to a flush
    if rate_pct <= -0.01:
        return "bullish"          # shorts pay: squeeze risk
    return "neutral"


def ratio_tone(ratio: float) -> str:
    return "bearish" if ratio >= 2.0 else "bullish" if ratio <= 0.8 else "neutral"


def _binance(symbol: str) -> Optional[dict]:
    pair = _BINANCE.get(symbol, f"{symbol}USDT")
    premium = _get("https://fapi.binance.com/fapi/v1/premiumIndex", _fast, {"symbol": pair})
    if not isinstance(premium, dict) or _f(premium.get("lastFundingRate")) is None:
        return None
    out = {"exchange": "Binance", "funding": _f(premium["lastFundingRate"]) * 100}
    hist = _get("https://fapi.binance.com/futures/data/openInterestHist", _fast, {"symbol": pair, "period": "1h", "limit": 25})
    if isinstance(hist, list) and len(hist) >= 2:
        now, before = _f(hist[-1].get("sumOpenInterestValue")), _f(hist[0].get("sumOpenInterestValue"))
        if now and before:
            out["oi_usd"], out["oi_change"] = now, (now / before - 1) * 100
    ratio = _get("https://fapi.binance.com/futures/data/globalLongShortAccountRatio", _fast,
                 {"symbol": pair, "period": "1h", "limit": 1})
    if isinstance(ratio, list) and ratio:
        out["long_short"] = _f(ratio[-1].get("longShortRatio"))
    return out


def _bybit(symbol: str) -> Optional[dict]:
    pair = _BYBIT.get(symbol, f"{symbol}USDT")
    data = _get("https://api.bybit.com/v5/market/tickers", _fast, {"category": "linear", "symbol": pair})
    rows = ((data or {}).get("result") or {}).get("list") if isinstance(data, dict) else None
    if not rows or _f(rows[0].get("fundingRate")) is None:
        return None
    out = {"exchange": "Bybit", "funding": _f(rows[0]["fundingRate"]) * 100, "oi_usd": _f(rows[0].get("openInterestValue"))}
    ratio = _get("https://api.bybit.com/v5/market/account-ratio", _fast,
                 {"category": "linear", "symbol": pair, "period": "1h", "limit": 1})
    lst = ((ratio or {}).get("result") or {}).get("list") if isinstance(ratio, dict) else None
    if lst:
        buy, sell = _f(lst[0].get("buyRatio")), _f(lst[0].get("sellRatio"))
        if buy and sell:
            out["long_short"] = buy / sell
    return out


def _okx(symbol: str) -> Optional[dict]:
    inst = f"{symbol}-USDT-SWAP"
    data = _get("https://www.okx.com/api/v5/public/funding-rate", _fast, {"instId": inst})
    rows = data.get("data") if isinstance(data, dict) else None
    if not rows or _f(rows[0].get("fundingRate")) is None:
        return None
    out = {"exchange": "OKX", "funding": _f(rows[0]["fundingRate"]) * 100}
    oi = _get("https://www.okx.com/api/v5/public/open-interest", _fast, {"instType": "SWAP", "instId": inst})
    if isinstance(oi, dict) and oi.get("data"):
        out["oi_usd"] = _f(oi["data"][0].get("oiUsd"))
    ratio = _get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio", _fast,
                 {"ccy": symbol, "period": "1H"})
    if isinstance(ratio, dict) and ratio.get("data"):
        out["long_short"] = _f(ratio["data"][0][1])
    return out


def derivatives(symbol: str) -> List[Dict[str, Any]]:
    """Funding, open interest and long/short ratio from the first exchange that answers (some block regions)."""
    for fetch in (_binance, _bybit, _okx):
        data = fetch(symbol)
        if data:
            break
    else:
        return []
    src, out = data["exchange"].lower(), []
    rate = data["funding"]
    out.append(signal("derivatives", "funding", round(rate, 4), f"{rate:+.4f}% / 8h", funding_tone(rate), src,
                      f"{symbol} perpetual funding {rate:+.4f}% per 8h on {data['exchange']} "
                      f"({'crowded longs, risk of a long squeeze' if rate >= 0.03 else 'shorts paying, squeeze risk' if rate <= -0.01 else 'balanced'})"))
    if data.get("oi_usd"):
        change = data.get("oi_change")
        out.append(signal("derivatives", "open_interest", round(change, 2) if change is not None else None,
                          _usd(data["oi_usd"]) + (f" ({_pct(change, 1)} 24h)" if change is not None else ""),
                          "neutral", src, f"{symbol} open interest {_usd(data['oi_usd'])}"
                          + (f", {_pct(change, 1)} in 24h (rising OI with rising price confirms the trend; with falling price it adds pressure)"
                             if change is not None else "")))
    ls = data.get("long_short")
    if ls:
        out.append(signal("derivatives", "long_short", round(ls, 2), f"{ls:.2f}", ratio_tone(ls), src,
                          f"{symbol} long/short account ratio {ls:.2f} (above 2 = retail heavily long, contrarian bearish; below 0.8 = crowded shorts)"))
    return out


def liquidations(symbol: str) -> List[Dict[str, Any]]:
    data = _get("https://www.okx.com/api/v5/public/liquidation-orders", _fast,
                {"instType": "SWAP", "uly": f"{symbol}-USDT", "state": "filled", "limit": 100})
    rows = data.get("data") if isinstance(data, dict) else None
    if not rows:
        return []
    since = (time.time() - 86400) * 1000
    longs = shorts = 0.0
    for d in rows[0].get("details") or []:
        if (_f(d.get("ts")) or 0) < since:
            continue
        size = _f(d.get("sz")) or 0
        if d.get("posSide") == "long":
            longs += size
        elif d.get("posSide") == "short":
            shorts += size
    total = longs + shorts
    if not total:
        return []
    share = longs / total * 100
    tone = "bearish" if share >= 65 else "bullish" if share <= 35 else "neutral"
    return [signal("derivatives", "liquidations", round(share, 1), f"{share:.0f}% long", tone, "okx",
                   f"{symbol} recent liquidations on OKX: {share:.0f}% longs / {100 - share:.0f}% shorts "
                   "(mostly longs liquidated = forced selling; mostly shorts = short squeeze)")]


# ---------- options ----------

def options(symbol: str) -> List[Dict[str, Any]]:
    if symbol not in OPTION_COINS:
        return []
    out = []
    book = _get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency", _medium,
                {"currency": symbol, "kind": "option"})
    rows = book.get("result") if isinstance(book, dict) else None
    if rows:
        puts = sum(_f(r.get("open_interest")) or 0 for r in rows if str(r.get("instrument_name", "")).endswith("-P"))
        calls = sum(_f(r.get("open_interest")) or 0 for r in rows if str(r.get("instrument_name", "")).endswith("-C"))
        if calls:
            pc = puts / calls
            tone = "bearish" if pc >= 1.0 else "bullish" if pc <= 0.6 else "neutral"
            out.append(signal("options", "put_call", round(pc, 2), f"{pc:.2f}", tone, "deribit",
                              f"{symbol} options put/call open-interest ratio {pc:.2f} on Deribit "
                              "(above 1 = heavy hedging / bearish positioning, below 0.6 = bullish calls dominate)"))
    end = int(time.time() * 1000)
    vol = _get("https://www.deribit.com/api/v2/public/get_volatility_index_data", _medium,
               {"currency": symbol, "start_timestamp": end - 8 * 86400 * 1000, "end_timestamp": end, "resolution": "43200"})
    points = ((vol or {}).get("result") or {}).get("data") if isinstance(vol, dict) else None
    if points and len(points) >= 2:
        now, before = _f(points[-1][4]), _f(points[0][4])
        if now and before:
            change = (now / before - 1) * 100
            out.append(signal("options", "dvol", round(now, 1), f"{now:.1f} ({_pct(change, 0)} 7d)",
                              "bearish" if change >= 20 else "neutral", "deribit",
                              f"{symbol} implied volatility index (DVOL) {now:.1f}, {_pct(change, 0)} over 7 days "
                              "(a fast rise = traders paying for protection, bigger moves expected)"))
    return out


# ---------- flows ----------

def stablecoins() -> List[Dict[str, Any]]:
    data = _get("https://stablecoins.llama.fi/stablecoincharts/all", _medium, {"stablecoin": ""})
    if not isinstance(data, list) or len(data) < 31:
        return []

    def total(row):
        return _f((row.get("totalCirculatingUSD") or {}).get("peggedUSD"))
    now, week, month = total(data[-1]), total(data[-8]), total(data[-31])
    if not now or not week or not month:
        return []
    w, m = (now / week - 1) * 100, (now / month - 1) * 100
    tone = "bullish" if w >= 0.5 else "bearish" if w <= -0.5 else "neutral"
    return [signal("flows", "stablecoins", round(w, 2), f"{_usd(now)} ({_pct(w, 1)} 7d)", tone, "defillama_stablecoins",
                   f"Stablecoin supply {_usd(now)}: {_pct(w, 1)} in 7 days, {_pct(m, 1)} in 30 days "
                   "(growing supply = fresh money ready to buy crypto)")]


def coinbase_premium() -> List[Dict[str, Any]]:
    cb = _get("https://api.exchange.coinbase.com/products/BTC-USD/ticker", _fast)
    okx = _get("https://www.okx.com/api/v5/market/ticker", _fast, {"instId": "BTC-USDT"})
    us = _f((cb or {}).get("price")) if isinstance(cb, dict) else None
    world = _f(((okx or {}).get("data") or [{}])[0].get("last")) if isinstance(okx, dict) else None
    if not us or not world:
        return []
    prem = (us / world - 1) * 100
    tone = "bullish" if prem >= 0.05 else "bearish" if prem <= -0.05 else "neutral"
    return [signal("flows", "coinbase_premium", round(prem, 3), _pct(prem, 3), tone, "coinbase",
                   f"Coinbase premium {prem:+.3f}% (BTC on Coinbase vs. global exchanges; positive = strong US and "
                   "institutional demand, negative = US selling)")]


# ---------- whole market & network ----------

def global_market() -> List[Dict[str, Any]]:
    data = _get("https://api.coingecko.com/api/v3/global", _fast)
    d = data.get("data") if isinstance(data, dict) else None
    if not d:
        return []
    out = []
    dom = _f((d.get("market_cap_percentage") or {}).get("btc"))
    if dom:
        out.append(signal("market", "btc_dominance", round(dom, 1), f"{dom:.1f}%", "neutral", "coingecko",
                          f"Bitcoin dominance {dom:.1f}% (rising dominance = money hiding in BTC, altcoins usually lag)"))
    cap, change = _f((d.get("total_market_cap") or {}).get("usd")), _f(d.get("market_cap_change_percentage_24h_usd"))
    if cap and change is not None:
        tone = "bullish" if change >= 2 else "bearish" if change <= -2 else "neutral"
        out.append(signal("market", "total_cap", round(change, 2), f"{_usd(cap)} ({_pct(change, 1)} 24h)", tone, "coingecko",
                          f"Total crypto market cap {_usd(cap)}, {_pct(change, 1)} in 24h"))
    return out


def btc_network() -> List[Dict[str, Any]]:
    out = []
    fees = _get("https://mempool.space/api/v1/fees/recommended", _medium)
    fast = _f((fees or {}).get("fastestFee")) if isinstance(fees, dict) else None
    if fast is not None:
        out.append(signal("network", "btc_fees", fast, f"{fast:.0f} sat/vB", "neutral", "mempool",
                          f"Bitcoin network fee {fast:.0f} sat/vB (spikes mean a rush of on-chain activity)"))
    rate = _get("https://mempool.space/api/v1/mining/hashrate/1m", _medium)
    points = (rate or {}).get("hashrates") if isinstance(rate, dict) else None
    if points and len(points) >= 2:
        now, before = _f(points[-1].get("avgHashrate")), _f(points[0].get("avgHashrate"))
        if now and before:
            change = (now / before - 1) * 100
            out.append(signal("network", "hashrate", round(change, 1), f"{now / 1e18:.0f} EH/s ({_pct(change, 0)} 30d)",
                              "bullish" if change >= 5 else "bearish" if change <= -10 else "neutral", "mempool",
                              f"Bitcoin hashrate {now / 1e18:.0f} EH/s, {_pct(change, 0)} in 30 days (falling hashrate can mean miners selling)"))
    return out


# ---------- macro ----------

def fred_series(series: str, days: int = 400) -> List[float]:
    start = (date.today() - timedelta(days=days)).isoformat()
    text = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", _slow, {"id": series, "cosd": start}, as_text=True)
    values: List[float] = []
    for row in csv.reader(io.StringIO(text or "")):
        if len(row) == 2 and (number := _f(row[1])) is not None:
            values.append(number)
    return values


def _change(values: List[float], back: int) -> Optional[float]:
    if len(values) <= back or not values[-1 - back]:
        return None
    return (values[-1] / values[-1 - back] - 1) * 100


def macro() -> List[Dict[str, Any]]:
    out = []
    vix = fred_series("VIXCLS")
    if vix:
        level = vix[-1]
        out.append(signal("macro", "vix", level, f"{level:.1f}", "bearish" if level >= 25 else "bullish" if level <= 15 else "neutral",
                          "fred", f"VIX fear index {level:.1f} (above 25 = stock-market stress, crypto usually falls with risk assets)"))
    for key, series, back, label in (("nasdaq", "NASDAQCOM", 5, "Nasdaq"), ("sp500", "SP500", 5, "S&P 500")):
        change = _change(fred_series(series), back)
        if change is not None:
            out.append(signal("macro", key, round(change, 2), f"{_pct(change, 1)} 1w",
                              "bullish" if change >= 2 else "bearish" if change <= -2 else "neutral", "fred",
                              f"{label} {_pct(change, 1)} over the last week (crypto tracks tech stocks closely)"))
    dollar = _change(fred_series("DTWEXBGS"), 20)
    if dollar is not None:
        out.append(signal("macro", "dollar", round(dollar, 2), f"{_pct(dollar, 1)} 1m",
                          "bearish" if dollar >= 1.5 else "bullish" if dollar <= -1.5 else "neutral", "fred",
                          f"US dollar index {_pct(dollar, 1)} over a month (a stronger dollar usually weighs on crypto)"))
    bonds = fred_series("DGS10")
    if bonds:
        change = bonds[-1] - bonds[-21] if len(bonds) > 21 else None
        out.append(signal("macro", "us10y", bonds[-1], f"{bonds[-1]:.2f}%" + (f" ({change:+.2f} 1m)" if change is not None else ""),
                          "bearish" if (change or 0) >= 0.3 else "bullish" if (change or 0) <= -0.3 else "neutral", "fred",
                          f"US 10-year yield {bonds[-1]:.2f}%" + (f", {change:+.2f} pp over a month (rising yields = tighter money)" if change is not None else "")))
    oil = _change(fred_series("DCOILWTICO"), 20)
    if oil is not None:
        out.append(signal("macro", "oil", round(oil, 1), f"{_pct(oil, 1)} 1m", "neutral", "fred",
                          f"WTI oil {_pct(oil, 1)} over a month (an oil spike feeds inflation fears)"))
    fed = fred_series("FEDFUNDS", 120)
    cpi = fred_series("CPIAUCSL", 520)
    if fed:
        out.append(signal("macro", "fed_rate", fed[-1], f"{fed[-1]:.2f}%", "neutral", "fred", f"Fed funds rate {fed[-1]:.2f}%"))
    if len(cpi) >= 13:
        yoy = (cpi[-1] / cpi[-13] - 1) * 100
        out.append(signal("macro", "inflation", round(yoy, 1), f"{yoy:.1f}% y/y", "bearish" if yoy >= 3.5 else "neutral", "fred",
                          f"US CPI inflation {yoy:.1f}% year on year (high inflation = fewer rate cuts)"))
    gold = _get("https://api.coingecko.com/api/v3/simple/price", _fast,
                {"ids": "pax-gold", "vs_currencies": "usd", "include_24hr_change": "true"})
    g = (gold or {}).get("pax-gold") if isinstance(gold, dict) else None
    if g and _f(g.get("usd")):
        change = _f(g.get("usd_24h_change")) or 0.0
        out.append(signal("macro", "gold", round(change, 2), f"${g['usd']:,.0f} ({_pct(change, 1)} 24h)", "neutral", "coingecko",
                          f"Gold ${g['usd']:,.0f}, {_pct(change, 1)} in 24h (gold up with crypto down = flight to safety)"))
    return out


# ---------- calendar, regulators, prediction markets ----------

def events(today: Optional[date] = None) -> List[Dict[str, Any]]:
    from app.services.market_data import get_upcoming_market_events
    today = today or datetime.now(timezone.utc).date()
    out = []
    for e in get_upcoming_market_events("en", limit=3, today=today):
        day = datetime.strptime(e["datum"], "%d.%m.%Y").date()
        days = (day - today).days
        if days <= 14:
            when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
            out.append(signal("events", "event", days, f"{e['udalost']} · {when}", "neutral", "calendar",
                              f"Scheduled: {e['udalost']} {when} ({day.isoformat()}) - volatility often rises around it"))
    return out


def _rss_titles(url: str, days: int = 7, limit: int = 3, only_crypto: bool = True) -> List[str]:
    text = _get(url, _medium, as_text=True)
    if not text:
        return []
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    titles = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title or (only_crypto and not CRYPTO_WORDS.search(title + " " + (item.findtext("description") or ""))):
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published < since:
                continue
        except (TypeError, ValueError):
            pass
        titles.append(title[:140])
        if len(titles) >= limit:
            break
    return titles


def regulation() -> List[Dict[str, Any]]:
    out = []
    for source, url in (("sec", "https://www.sec.gov/news/pressreleases.rss"),
                        ("cftc", "https://www.cftc.gov/RSS/RSSGP/rssgp.xml")):
        for title in _rss_titles(url):
            out.append(signal("regulation", "regulator_news", None, title, "neutral", source,
                              f"Regulator ({source.upper()}) this week: {title}"))
    return out[:4]


def prediction_markets(symbol: str) -> List[Dict[str, Any]]:
    data = _get("https://gamma-api.polymarket.com/markets", _medium,
                {"limit": 100, "active": "true", "closed": "false", "order": "volume24hr", "ascending": "false"})
    if not isinstance(data, list):
        return []
    names = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "xrp", "DOGE": "doge"}
    words = re.compile(rf"\b({names.get(symbol, symbol.lower())}|bitcoin|crypto|fed|interest rate)\b", re.I)
    out = []
    for m in data:
        question = str(m.get("question") or "")
        if not words.search(question):
            continue
        try:
            outcomes, prices = json.loads(m.get("outcomes") or "[]"), json.loads(m.get("outcomePrices") or "[]")
            yes = _f(prices[outcomes.index("Yes")]) if "Yes" in outcomes else None
        except (ValueError, TypeError, IndexError):
            continue
        if yes is None:
            continue
        out.append(signal("predictions", "polymarket", round(yes * 100), f"{question[:90]} · {yes * 100:.0f}% yes",
                          "neutral", "polymarket", f"Polymarket odds: \"{question}\" - {yes * 100:.0f}% yes"))
        if len(out) >= 3:
            break
    return out


# ---------- bundle ----------

def collect(symbol: str = "BTC", timeout: float = 12.0) -> Dict[str, Any]:
    """All signals for a coin (derivatives and options are coin-specific; the rest is market-wide)."""
    symbol = (symbol or "BTC").upper()
    cached = _bundle.get(symbol)
    if cached is not None:
        return cached
    jobs: List[Callable[[], List[Dict[str, Any]]]] = [
        lambda: derivatives(symbol), lambda: liquidations(symbol), lambda: options(symbol), stablecoins,
        coinbase_premium, global_market, btc_network, macro, events, regulation, lambda: prediction_markets(symbol),
    ]
    items: List[Dict[str, Any]] = []
    pool = ThreadPoolExecutor(max_workers=len(jobs))
    try:
        futures = [pool.submit(job) for job in jobs]
        done, _pending = wait(futures, timeout=timeout)
        for future in futures:
            if future in done:
                try:
                    items.extend(future.result() or [])
                except Exception:  # noqa: BLE001
                    logger.exception("Signal job failed")
    finally:
        pool.shutdown(wait=False)
    items.sort(key=lambda s: GROUPS.index(s["group"]))
    bundle = {"coin": symbol, "items": items, "sources": sorted({s["source"] for s in items}),
              "lines": [s["note"] for s in items], "updated_at": datetime.now(timezone.utc).isoformat(),
              "score": score(items)}
    if items:
        _bundle.set(symbol, bundle)
    return bundle


def score(items: List[Dict[str, Any]]) -> Dict[str, int]:
    tones = [s["tone"] for s in items]
    return {"bullish": tones.count("bullish"), "bearish": tones.count("bearish"), "neutral": tones.count("neutral")}


def context_block(bundle: Dict[str, Any]) -> Optional[str]:
    if not bundle.get("lines"):
        return None
    return "Market signals (live, public sources):\n- " + "\n- ".join(bundle["lines"])
