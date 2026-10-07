"""Health of the external services the app depends on (public status page)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, List, Tuple

import requests
from sqlalchemy import text

from app.config import (
    ANTHROPIC_API_URL, CRYPTO_NEWS_RSS_URLS, DEEPSEEK_API_URL, FEAR_GREED_API_URL, GROK_API_URL, OPENAI_API_URL,
)
from app.utils.ttl_cache import TTLCache

_TIMEOUT_SECONDS = 5
_SLOW_MS = 3000
_cache = TTLCache(ttl_seconds=60)

# (id, group, url). For AI providers any HTTP answer below 500 (e.g. 401 without a key) means
# the service is reachable; we never send user keys from here.
HTTP_CHECKS: List[Tuple[str, str, str]] = [
    ("coingecko", "data", "https://api.coingecko.com/api/v3/ping"),
    ("fear_greed", "data", f"{FEAR_GREED_API_URL}?limit=1"),
    ("blockchair", "data", "https://api.blockchair.com/bitcoin/stats"),
    ("news_rss", "data", CRYPTO_NEWS_RSS_URLS[0]),
    ("gemini", "ai", "https://generativelanguage.googleapis.com/v1beta/models"),
    ("openai", "ai", OPENAI_API_URL.rsplit("/chat/", 1)[0] + "/models"),
    ("anthropic", "ai", ANTHROPIC_API_URL),
    ("deepseek", "ai", DEEPSEEK_API_URL.rsplit("/chat/", 1)[0] + "/models"),
    ("grok", "ai", GROK_API_URL.rsplit("/chat/", 1)[0] + "/models"),
]


def _classify_http(status_code: int, latency_ms: int) -> str:
    if status_code >= 500:
        return "down"
    if status_code == 429 or latency_ms > _SLOW_MS:
        return "degraded"
    return "up"


def _check_http(url: str) -> Tuple[str, int]:
    start = time.monotonic()
    try:
        response = requests.get(url, timeout=_TIMEOUT_SECONDS,
                                headers={"User-Agent": "ai-crypto-analytics-status/1.0"}, stream=True)
        response.close()
        latency = int((time.monotonic() - start) * 1000)
        return _classify_http(response.status_code, latency), latency
    except requests.RequestException:
        return "down", int((time.monotonic() - start) * 1000)


def _check_database() -> Tuple[str, int]:
    from app.database import SessionLocal
    start = time.monotonic()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return "up", int((time.monotonic() - start) * 1000)
    except Exception:  # noqa: BLE001
        return "down", int((time.monotonic() - start) * 1000)


def overall_status(services: List[Dict]) -> str:
    """The app is 'down' only if its own core is; missing external data just degrades it."""
    if any(s["group"] == "core" and s["status"] == "down" for s in services):
        return "down"
    if any(s["status"] != "up" for s in services if s["group"] != "ai"):
        return "degraded"
    return "up"


def collect_status(checks: List[Tuple[str, str, Callable[[], Tuple[str, int]]]] | None = None) -> Dict:
    cached = _cache.get("status")
    if checks is None and cached is not None:
        return cached
    if checks is None:
        checks = [("backend", "core", lambda: ("up", 0)), ("database", "core", _check_database)]
        checks += [(sid, group, (lambda u=url: _check_http(u))) for sid, group, url in HTTP_CHECKS]
    with ThreadPoolExecutor(max_workers=len(checks)) as pool:
        futures = [(sid, group, pool.submit(fn)) for sid, group, fn in checks]
        services = []
        for sid, group, future in futures:
            try:
                status, latency = future.result(timeout=_TIMEOUT_SECONDS + 2)
            except Exception:  # noqa: BLE001
                status, latency = "down", None
            services.append({"id": sid, "group": group, "status": status, "latency_ms": latency})
    result = {"overall": overall_status(services), "checked_at": datetime.now(timezone.utc).isoformat(),
              "services": services}
    _cache.set("status", result)
    return result


HISTORY_DAYS = 30


def record_sample(db) -> int:
    """Background job: store one result per service and keep only the last ~35 days."""
    from datetime import timedelta
    from app.models import StatusSample
    result = collect_status()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for s in result["services"]:
        db.add(StatusSample(checked_at=now, service=s["id"], status=s["status"], latency_ms=s["latency_ms"]))
    db.query(StatusSample).filter(StatusSample.checked_at < now - timedelta(days=HISTORY_DAYS + 5)).delete()
    db.commit()
    return len(result["services"])


def history(db, now: datetime | None = None) -> Dict:
    """Per service and day: share of checks where the service was reachable (days without checks have no data)."""
    from datetime import timedelta
    from app.models import StatusSample
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    since = (now - timedelta(days=HISTORY_DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    days = [(since + timedelta(days=i)).date().isoformat() for i in range(HISTORY_DAYS)]
    per: Dict[str, Dict[str, List[int]]] = {}
    for service, status, checked in (db.query(StatusSample.service, StatusSample.status, StatusSample.checked_at)
                                     .filter(StatusSample.checked_at >= since).all()):
        day = per.setdefault(service, {}).setdefault(checked.date().isoformat(), [0, 0])
        day[0] += status in ("up", "degraded")  # reachable; slow or rate-limited is not an outage
        day[1] += 1
    services = []
    for service, by_day in sorted(per.items()):
        ups, total = sum(v[0] for v in by_day.values()), sum(v[1] for v in by_day.values())
        services.append({"id": service, "uptime_pct": round(ups / total * 100, 2) if total else None,
                         "days": [{"day": d, "uptime_pct": round(by_day[d][0] / by_day[d][1] * 100, 1) if d in by_day else None}
                                  for d in days]})
    return {"days": days, "services": services}
