"""Only requests that came through the Netlify /api proxy reach the API.

The backend's own address (onrender.com) is public. Without this check anyone could call it directly and, because the
client IP is read from X-Forwarded-For a fixed number of proxy hops from the right (TRUSTED_PROXY_HOPS), put a made-up
IP there and slip past every per-IP limit. Netlify signs each proxied request (netlify.toml: signed = "...") with a JWT
in the x-nf-sign header; with PROXY_SIGNATURE_SECRET set, requests without a valid signature are refused.
"""

from __future__ import annotations

import json

import jwt

from app.config import PROXY_SIGNATURE_SECRET

# Reached directly on purpose: the keep-awake ping and uptime checks, and Stripe (which signs its own requests).
EXEMPT_PATHS = frozenset({"/api/health", "/api/billing/webhook"})


def valid_signature(token: str, secret: str) -> bool:
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "iss"]})
    except jwt.PyJWTError:
        return False
    return claims.get("iss") == "netlify"


class ProxyGuardMiddleware:
    def __init__(self, app, secret: str = PROXY_SIGNATURE_SECRET) -> None:
        self.app = app
        self.secret = secret

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        if (scope["type"] != "http" or not self.secret or not path.startswith("/api/") or path in EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return
        token = dict(scope.get("headers", [])).get(b"x-nf-sign", b"").decode("latin-1")
        if token and valid_signature(token, self.secret):
            await self.app(scope, receive, send)
            return
        body = json.dumps({"detail": "Prístup je možný len cez webovú aplikáciu."}).encode("utf-8")
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
