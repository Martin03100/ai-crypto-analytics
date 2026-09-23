"""app/csrf.py — CSRF ochrana pre cookie-based auth (double-submit token).

Auth token je v HttpOnly cookie (JS si ho neprecita, chrani pred XSS), co ale
samo o sebe neochrani pred CSRF - cudzia stranka moze poslat request na nase
API a prehliadac cookie priposle automaticky. Preto k tomu pridavame
"double-submit" CSRF token: netajny nahodny retazec v BEZNEJ (JS-citatelnej)
cookie, ktory frontend musi zopakovat aj v hlavicke `X-CSRF-Token`. Cudzia
stranka hlavicku nastavit nevie (a citat nasu cookie tiez nie - same-origin
policy), takze bez nej sa mutacny request odmietne.

SameSite=Lax na auth cookie uz sam osebe blokuje vacsinu CSRF scenarov;
toto je zamerna druha vrstva (defense-in-depth), nie jediny mechanizmus.
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE, CSRF_COOKIE_NAME, CSRF_HEADER_NAME

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Endpointy, kde CSRF token este nemoze existovat (prvotne prihlasenie),
# alebo kde nehrozi (verejne, bezstavove citanie) - login/register su
# chranene rate-limitom + heslom, nie CSRF tokenom.
_EXEMPT_PATHS = {"/api/auth/login", "/api/auth/register", "/api/health"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Kazdemu requestu zarucime existenciu CSRF cookie (JS-citatelna,
        # NIE HttpOnly) - frontend si ju precita a posiela spat v hlavicke.
        existing_token = request.cookies.get(CSRF_COOKIE_NAME)

        if request.method not in _SAFE_METHODS and request.url.path not in _EXEMPT_PATHS:
            header_token = request.headers.get(CSRF_HEADER_NAME)
            if not existing_token or not header_token or not secrets.compare_digest(existing_token, header_token):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Neplatný alebo chýbajúci CSRF token. Obnov stránku a skús to znova."},
                )

        response = await call_next(request)

        if not existing_token:
            new_token = secrets.token_urlsafe(32)
            response.set_cookie(
                key=CSRF_COOKIE_NAME, value=new_token,
                httponly=False,  # zamerne citatelna z JS - to je cely princip double-submit
                secure=AUTH_COOKIE_SECURE, samesite=AUTH_COOKIE_SAMESITE, path="/",
            )
        return response
