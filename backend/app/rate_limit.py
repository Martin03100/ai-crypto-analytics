"""app/rate_limit.py — jednoduchy in-memory rate limiter (sliding window).

Pre jeden proces staci; pri viac-procesovom/viac-serverovom nasadeni by bolo
treba zdielany store (Redis a pod.). Tu chranime pred hrubou silou na
/auth/login a pred zbytocnym zaťažovanim (a cerpanim API kreditu) na
AI endpointoch.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Depends, HTTPException, Request, status

# key -> zoznam timestampov poslednych volani (sekundy, float)
_hits: Dict[str, List[float]] = defaultdict(list)


def _check(key: str, max_calls: int, window_seconds: int) -> None:
    now = time.monotonic()
    bucket = _hits[key]
    # zahod zaznamy mimo aktualneho okna
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= max_calls:
        retry_after = max(1, int(bucket[0] + window_seconds - now))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Príliš veľa požiadaviek. Skús to znova o {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    bucket.append(now)


def get_client_ip(request: Request) -> str:
    """Vrati skutocnu IP adresu klienta, aj ked appka bezi za reverse proxy
    (Render/Netlify/Vercel — presne nasa odporucana deployment topologia).

    Render aj Netlify/Vercel pridavaju hlavicku `X-Forwarded-For` s povodnou
    klientskou IP na ZACIATKU zoznamu (kazdy dalsi hop svoju IP PRIDAVA na
    koniec, nikdy neprepisuje tu prvu). Bez tohto by `request.client.host`
    za proxy vzdy ukazoval na IP samotneho proxy servera — rate limiting
    podla IP by tak fakticky spajal VSETKYCH pouzivatelov appky do jedneho
    zdielaneho "vedra" (jeden pouzivatel by mohol limitom zablokovat vsetkych
    ostatnych).

    POZOR na dôveru k hlavičke: ak by appka niekedy bežala BEZ dôveryhodného
    proxy pred sebou (priamo vystavená internetu), ktokoľvek by si mohol
    X-Forwarded-For sfalšovať a obísť tak rate limiting. V odporúčanej
    topológii z DEPLOYMENT.md (Render/Netlify/Vercel) je to bezpečné, lebo
    tieto platformy hlavičku vždy nastavujú/prepisujú svojou skutočnou
    hodnotou a klient sa k backendu inak ako cez ne nedostane."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _route_key(request: Request) -> str:
    """Sablona routy (napr. /api/forecast/history/{entry_id}/accuracy), nie
    realna URL. Inak by kazde ID malo vlastny, samostatny limit - a limit by
    sa dal obist jednoduchym prechadzanim ID (1, 2, 3...)."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


# Verejny alias - pre limity podla hodnoty z tela requestu (napr. per-email).
check_rate_limit = _check


def rate_limit_by_ip(max_calls: int, window_seconds: int):
    """FastAPI dependency factory: limituje podla IP adresy volajuceho.
    Vhodne pre neautentifikovane endpointy ako /auth/login."""
    def dependency(request: Request) -> None:
        client_ip = get_client_ip(request)
        _check(f"ip:{_route_key(request)}:{client_ip}", max_calls, window_seconds)
    return dependency


def rate_limit_by_user(max_calls: int, window_seconds: int):
    """FastAPI dependency factory: limituje podla prihlaseneho pouzivatela.
    Vyzaduje, aby endpoint uz mal medzi zavislostami `user: User =
    Depends(get_current_user)` - tato zavislost si ho vyziada znova (FastAPI
    zdiela vysledok v ramci jedneho requestu, takze DB sa nepyta 2x)."""
    from app.deps import get_current_user  # lazy import, aby sa predislo cyklu

    def dependency(request: Request, user=Depends(get_current_user)) -> None:
        key = f"user:{_route_key(request)}:{user.id}"
        _check(key, max_calls, window_seconds)
    return dependency
