"""Rate limiting."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Depends, HTTPException, Request, status

from app.config import APP_ENV, TRUSTED_PROXY_HOPS

logger = logging.getLogger("aca.ratelimit")

_hits: Dict[str, Deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_STALE_AFTER_SECONDS = 3600
_SWEEP_EVERY = 500
_calls_since_sweep = 0


def _sweep(now: float) -> None:
    for key in [k for k, bucket in _hits.items() if not bucket or now - bucket[-1] > _STALE_AFTER_SECONDS]:
        del _hits[key]


def _check(key: str, max_calls: int, window_seconds: int) -> None:
    global _calls_since_sweep
    now = time.monotonic()
    with _lock:
        _calls_since_sweep += 1
        if _calls_since_sweep >= _SWEEP_EVERY:
            _calls_since_sweep = 0
            _sweep(now)
        bucket = _hits[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_calls:
            retry_after = max(1, int(bucket[0] + window_seconds - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Príliš veľa požiadaviek. Skús to znova o {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            if TRUSTED_PROXY_HOPS > 0:
                return parts[max(0, len(parts) - TRUSTED_PROXY_HOPS)]
            return parts[0]
    return request.client.host if request.client else "unknown"


if APP_ENV == "production" and TRUSTED_PROXY_HOPS == 0:
    logger.warning(
        "TRUSTED_PROXY_HOPS nie je nastavene: IP klienta sa berie z prveho zaznamu X-Forwarded-For, "
        "ktory si moze klient sfalsovat (obchadzanie limitov podla IP). Nastav TRUSTED_PROXY_HOPS "
        "(napr. 1 pre Render)."
    )


def _route_key(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


check_rate_limit = _check


def rate_limit_global(name: str, max_calls: int, window_seconds: int):
    def dependency() -> None:
        _check(f"global:{name}", max_calls, window_seconds)
    return dependency


def rate_limit_by_ip(max_calls: int, window_seconds: int):
    def dependency(request: Request) -> None:
        client_ip = get_client_ip(request)
        _check(f"ip:{_route_key(request)}:{client_ip}", max_calls, window_seconds)
    return dependency


def rate_limit_by_user(max_calls: int, window_seconds: int):
    from app.deps import get_current_user

    def dependency(request: Request, user=Depends(get_current_user)) -> None:
        key = f"user:{_route_key(request)}:{user.id}"
        _check(key, max_calls, window_seconds)
    return dependency
