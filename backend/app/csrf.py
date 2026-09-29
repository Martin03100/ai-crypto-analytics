"""CSRF protection middleware."""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE, CSRF_COOKIE_NAME, CSRF_HEADER_NAME

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_EXEMPT_PATHS = {"/api/auth/login", "/api/auth/register", "/api/health"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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
                httponly=False,
                secure=AUTH_COOKIE_SECURE, samesite=AUTH_COOKIE_SAMESITE, path="/",
            )
        return response
