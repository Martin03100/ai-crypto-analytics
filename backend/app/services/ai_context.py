"""Market data put into the AI prompts: price history with indicators, market signals, sentiment and news,
collected in parallel within a time limit."""

from __future__ import annotations

import logging
import statistics
from concurrent.futures import ThreadPoolExecutor
import time
from typing import Any, Dict, List, Optional, Tuple


from app.config import (
    DEFAULT_COIN_IDS,
)
from app.services import data_sources, market_data, signals

logger = logging.getLogger("aca.ai")


_MARKET_CONTEXT_TIMEOUT = 5


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
    if future is None:
        return None
    try:
        return future.result(timeout=max(0.1, deadline - time.monotonic()))
    except Exception:  # noqa: BLE001
        return None


_SIGNALS_WAIT = 14


def _append_signals(lines: List[str], sources: List[str], future, started: float) -> None:
    bundle = _await(future, started + _SIGNALS_WAIT)
    block = signals.context_block(bundle) if bundle else None
    if block:
        lines.append(block)
        sources.extend(bundle["sources"])


def market_signals_block(*symbols: str) -> Optional[str]:
    """Signals for prompts outside forecasts (news summary, digest, chat). Never raises."""
    blocks, seen = [], set()
    for symbol in symbols or ("BTC",):
        try:
            bundle = signals.collect(symbol)
        except Exception:  # noqa: BLE001
            continue
        fresh = [line for line in bundle.get("lines", []) if line not in seen]
        seen.update(fresh)
        if fresh:
            blocks.append("- " + "\n- ".join(fresh))
    return "Market signals (live, public sources):\n" + "\n".join(blocks) if blocks else None


def _append_common_context(lines: List[str], sources: List[str], futures: Dict[str, Any], deadline: float) -> None:
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
    coin_id = DEFAULT_COIN_IDS.get(coin.upper())
    if not coin_id:
        return None, []
    symbol = coin.upper()
    pool = ThreadPoolExecutor(max_workers=13)
    try:
        started = time.monotonic()
        deadline = started + _MARKET_CONTEXT_TIMEOUT + 1
        futures = {
            "signals": pool.submit(signals.collect, symbol),
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
        _append_signals(lines, sources, futures["signals"], started)
        return "\n".join(lines), sources
    except Exception:  # noqa: BLE001
        return None, []
    finally:
        pool.shutdown(wait=False)


def _fetch_market_context(coin: str) -> Optional[str]:
    return _build_market_context(coin)[0]


def _build_portfolio_context(holdings: List[Dict[str, Any]]) -> Tuple[Optional[str], List[str]]:
    ids = [h.get("coin_id") or DEFAULT_COIN_IDS.get(str(h.get("minca", "")).upper()) for h in holdings]
    pool = ThreadPoolExecutor(max_workers=7)
    try:
        started = time.monotonic()
        deadline = started + _MARKET_CONTEXT_TIMEOUT + 1
        futures = {
            "signals": pool.submit(signals.collect, "BTC"),
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
        _append_signals(lines, sources, futures["signals"], started)
        return "\n".join(lines), sources
    except Exception:  # noqa: BLE001
        return None, []
    finally:
        pool.shutdown(wait=False)
