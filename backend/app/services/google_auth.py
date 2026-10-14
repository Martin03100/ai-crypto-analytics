"""Sign in with Google: checks the ID token the browser received from Google Identity Services.

Google's tokeninfo endpoint verifies the signature and expiry; this module then makes sure the token was issued for
this app (aud), by Google (iss), and that Google has confirmed the e-mail address.
"""

from __future__ import annotations

import logging
import re
import secrets
from typing import Optional

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import GOOGLE_CLIENT_ID
from app.models import User
from app.schemas import USERNAME_RE

logger = logging.getLogger("aca.google")

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


def enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID)


def verify_credential(credential: str) -> Optional[dict]:
    """The token's claims ({"sub", "email", ...}) when it is valid for this app, otherwise None."""
    if not enabled():
        return None
    try:
        res = requests.get(TOKENINFO_URL, params={"id_token": credential}, timeout=10)
    except requests.RequestException as exc:
        logger.warning("Google tokeninfo nedostupne: %s", exc)
        return None
    if res.status_code != 200:
        return None
    try:
        claims = res.json()
    except ValueError:
        return None
    if (claims.get("aud") != GOOGLE_CLIENT_ID or claims.get("iss") not in _ISSUERS
            or str(claims.get("email_verified")).lower() != "true" or not claims.get("sub") or not claims.get("email")):
        return None
    return claims


def free_username(db: Session, email: str) -> str:
    """A unique username derived from the e-mail's local part ("jan.novak@..." -> "jan.novak", "jan.novak2"...)."""
    base = re.sub(r"[^A-Za-z0-9_.-]", "", email.split("@")[0])[:24] or "user"
    if len(base) < 3:
        base = f"{base}user"
    candidate = base
    for _ in range(50):
        taken = db.query(User.id).filter(func.lower(User.username) == candidate.lower()).first()
        if USERNAME_RE.match(candidate) and not taken:
            return candidate
        candidate = f"{base}{secrets.randbelow(9000) + 100}"
    return f"user{secrets.token_hex(4)}"
