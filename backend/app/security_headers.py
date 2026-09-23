"""
app/security_headers.py
=========================
Prida na kazdu HTTP odpoved zakladnu sadu bezpecnostnych hlaviciek. Tento
backend je cisto JSON API (skutocne HTML/JS renderuje frontend na Netlify/
Vercel), takze CSP je zamerne restriktivna - ziadna stranka z tohto servera
sa nema co embeddovat ani vykonavat skripty priamo.

Vynimka: v developmente (APP_ENV != "production") su /docs a /redoc
(Swagger/ReDoc UI) aktivne (viz app/main.py) a tie potrebuju nacitat
skripty/styly z cdn.jsdelivr.net - preto sa CSP hlavicka v NEPRODUKCNOM
rezime vynechava, aby tieto dev nastroje fungovali bez upravy.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import APP_ENV


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        if APP_ENV == "production":
            # HSTS iba v produkcii (na lokalnom http://localhost by donutil
            # prehliadac vynucovat HTTPS aj tam, kde ziadne nie je).
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
            # Cisto JSON API - ziadna stranka odtialto sa nema vykonavat ako
            # dokument v prehliadaci, preto restriktivna CSP. /docs, /redoc
            # su v produkcii aj tak vypnute (viz app/main.py).
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response
