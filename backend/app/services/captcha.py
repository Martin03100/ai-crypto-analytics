"""app/services/captcha.py - Cloudflare Turnstile (bezplatna CAPTCHA).

Vypnute, kym nie je nastaveny TURNSTILE_SECRET_KEY - appka tak funguje aj
bez CAPTCHA (lokalny vyvoj, testy). Na produkcii chrani registraciu a
"zabudnute heslo" pred botmi."""

from __future__ import annotations

from typing import Optional

import requests

from app.config import TURNSTILE_SECRET_KEY


def verify_captcha(token: Optional[str], remote_ip: Optional[str] = None) -> bool:
    if not TURNSTILE_SECRET_KEY:
        return True
    if not token:
        return False
    try:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET_KEY, "response": token, "remoteip": remote_ip or ""},
            timeout=5,
        )
        return bool(response.json().get("success"))
    except Exception:  # noqa: BLE001 - pri vypadku overenia radsej odmietnut
        return False
