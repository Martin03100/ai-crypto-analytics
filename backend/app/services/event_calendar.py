"""Market event calendar: US macro releases, crypto option expiries, the Bitcoin halving and large token unlocks.

Macro dates are the officially published ones (Fed, BLS). Option expiries follow Deribit's fixed rule.
The halving date is an estimate from the current block height. Unlocks come from DefiLlama's public
emission datasets (no key). Every network source is optional: when it fails, its events are left out."""

from __future__ import annotations

import calendar as _cal
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from app.config import DEFAULT_COIN_IDS
from app.i18n_content import MARKET_EVENT_CALENDAR
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

NEW_YORK = ZoneInfo("America/New_York")
TIMEOUT = 5
HALVING_HEIGHT = 1_050_000          # 5th Bitcoin halving
BLOCK_MINUTES = 10
UNLOCK_MIN_SHARE = 0.005            # a day that releases >= 0.5 % of the already unlocked supply
UNLOCK_DAYS = 45

# Employment Situation (jobs report) release days. Source: bls.gov/schedule/news_release/empSit.htm
NFP_DATES = ("2026-01-09", "2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05", "2026-07-02",
             "2026-08-07", "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04")

# DefiLlama emission dataset slugs for the coins the app follows (coins without vesting schedules are absent).
UNLOCK_SLUGS = {"SUI": "sui", "APT": "aptos", "AVAX": "avalanche", "NEAR": "near", "UNI": "uniswap",
                "TON": "ton", "DOT": "polkadot", "ADA": "cardano"}
EMISSIONS_URL = "https://defillama-datasets.llama.fi/emissions/{slug}"

KINDS = ("fomc", "cpi", "nfp", "options_monthly", "options_quarterly", "halving", "unlock")
CATEGORY = {"fomc": "macro", "cpi": "macro", "nfp": "macro", "options_monthly": "crypto",
            "options_quarterly": "crypto", "halving": "crypto", "unlock": "unlock"}
IMPACT = {"fomc": "high", "cpi": "high", "nfp": "medium", "options_monthly": "medium",
          "options_quarterly": "high", "halving": "high", "unlock": "medium"}

_cache = TTLCache(ttl_seconds=6 * 3600)


def _ny(day: date, hour: int, minute: int) -> datetime:
    """A New York wall-clock time as naive UTC (handles summer/winter time)."""
    return datetime.combine(day, time(hour, minute), tzinfo=NEW_YORK).astimezone(timezone.utc).replace(tzinfo=None)


def _event(kind: str, at: datetime, *, estimated: bool = False, **extra: Any) -> Dict[str, Any]:
    suffix = extra.get("coin", "").lower()
    return {"id": f"{kind}-{at:%Y%m%d}{'-' + suffix if suffix else ''}", "kind": kind, "category": CATEGORY[kind],
            "impact": IMPACT[kind], "at": at.isoformat() + "Z", "estimated": estimated, **extra}


def macro_events() -> List[Dict[str, Any]]:
    out = []
    for day, kind in MARKET_EVENT_CALENDAR:
        d = date.fromisoformat(day)
        out.append(_event(kind, _ny(d, 14, 0) if kind == "fomc" else _ny(d, 8, 30)))
    out += [_event("nfp", _ny(date.fromisoformat(d), 8, 30)) for d in NFP_DATES]
    return out


def last_friday(year: int, month: int) -> date:
    last = date(year, month, _cal.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - 4) % 7)


def option_expiries(today: date, months: int = 4) -> List[Dict[str, Any]]:
    """Deribit: the monthly expiry is the last Friday of the month at 08:00 UTC; Mar/Jun/Sep/Dec are quarterly."""
    out = []
    year, month = today.year, today.month
    for _ in range(months):
        day = last_friday(year, month)
        kind = "options_quarterly" if month in (3, 6, 9, 12) else "options_monthly"
        out.append(_event(kind, datetime.combine(day, time(8, 0))))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def _get_json(url: str) -> Any:
    try:
        res = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "AI-Crypto-Analytics/1.0"})
        return res.json() if res.ok else None
    except (requests.RequestException, ValueError):
        return None


def block_height() -> Optional[int]:
    for url in ("https://mempool.space/api/blocks/tip/height", "https://blockstream.info/api/blocks/tip/height"):
        value = _get_json(url)
        if isinstance(value, int) and value > 800_000:
            return value
    return None


def halving_event(now: datetime) -> Optional[Dict[str, Any]]:
    height = _cache.get("height")
    if height is None:
        height = block_height() or 0          # 0 = unreachable; remembered too, so a dead API is not retried each time
        _cache.set("height", height)
    if not height:
        return None
    blocks = HALVING_HEIGHT - height
    if blocks <= 0:
        return None
    at = (now + timedelta(minutes=blocks * BLOCK_MINUTES)).replace(minute=0, second=0, microsecond=0)
    return _event("halving", at, estimated=True, blocks_left=blocks)


def unlocks_from_series(coin: str, data: Any, today: date, days: int = UNLOCK_DAYS) -> List[Dict[str, Any]]:
    """Sum DefiLlama's cumulative "unlocked" series and keep the days with a large jump."""
    series = (data or {}).get("documentedData", {}).get("data") if isinstance(data, dict) else None
    if not isinstance(series, list):
        return []
    total: Dict[int, float] = {}
    for item in series:
        for point in (item or {}).get("data") or []:
            ts, value = point.get("timestamp"), point.get("unlocked")
            if isinstance(ts, (int, float)) and isinstance(value, (int, float)):
                day = int(ts) // 86400
                total[day] = total.get(day, 0.0) + float(value)
    if len(total) < 2:
        return []
    start = (today - date(1970, 1, 1)).days
    days_sorted = sorted(total)
    base = next((total[d] for d in reversed(days_sorted) if d <= start), None)
    if not base:
        return []
    out = []
    prev_value = base
    for d in days_sorted:
        if d <= start or d > start + days:
            continue
        jump = total[d] - prev_value
        prev_value = total[d]
        if jump > 0 and jump / base >= UNLOCK_MIN_SHARE:
            at = datetime(1970, 1, 1) + timedelta(days=d)
            out.append(_event("unlock", at, coin=coin, amount=round(jump), share_pct=round(jump / base * 100, 2)))
    return out


def token_unlocks(today: date) -> List[Dict[str, Any]]:
    cached = _cache.get(f"unlocks:{today}")
    if cached is not None:
        return cached
    coins = [(c, s) for c, s in UNLOCK_SLUGS.items() if c in DEFAULT_COIN_IDS]
    with ThreadPoolExecutor(max_workers=len(coins) or 1) as pool:
        datasets = list(pool.map(lambda cs: _get_json(EMISSIONS_URL.format(slug=cs[1])), coins))
    out: List[Dict[str, Any]] = []
    for (coin, _slug), data in zip(coins, datasets):
        out += unlocks_from_series(coin, data, today)
    _cache.set(f"unlocks:{today}", out)
    return out


def upcoming(days: int = 60, now: Optional[datetime] = None, network: bool = True) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    end = now + timedelta(days=days)
    items = macro_events() + option_expiries(now.date())
    if network:
        items += token_unlocks(now.date())
    items = [e for e in items if now - timedelta(hours=2) <= _at(e) <= end]
    items.sort(key=_at)
    halving = halving_event(now) if network else None
    return {"events": items, "halving": halving, "days": days, "generated_at": now.isoformat() + "Z"}


def _at(event: Dict[str, Any]) -> datetime:
    return datetime.fromisoformat(event["at"].rstrip("Z"))


def find(event_id: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """An event the user may set a reminder for (from the next 120 days, no network needed for macro/options)."""
    for e in upcoming(120, now)["events"]:
        if e["id"] == event_id:
            return e
    return None


def event_at(event: Dict[str, Any]) -> datetime:
    return _at(event)
