"""
app/security.py
=================
- Hashovanie hesiel (PBKDF2-HMAC-SHA256 so solou, cez passlib).
- JWT vydavanie / overovanie (python-jose).
- Bank-grade sifrovanie API klucov: AES-256 cez Fernet (cryptography kniznica).
  Kluce sa sifruju PRED zapisom do DB a desifruju sa VYHRADNE v pamati,
  tesne pred pouzitim v aktivnom API volani. Do UI ide iba maskovany
  nahlad (napr. "sk-...4a2b"), nikdy plny kluc.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import API_KEY_ENCRYPTION_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

# ---------------------------------------------------------------------------
# Heslo hashing
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: int, username: str, token_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": str(subject), "username": username, "tv": token_version, "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# AES-256 (Fernet) sifrovanie API klucov
# ---------------------------------------------------------------------------
def _derive_fernet_key(secret: str) -> bytes:
    """Odvodi platny 32-bajtovy url-safe base64 Fernet kluc z lubovolneho secretu."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key(API_KEY_ENCRYPTION_SECRET))


_V2_PREFIX = "v2:"


def _user_fernet(user_id: int) -> Fernet:
    """Kluc odvodeny pre KONKRETNEHO pouzivatela. Sifrovany text je tak
    naviazany na jeho ucet - ani utocnik s pristupom do DB nemoze presunut
    cudzi zasifrovany kluc do svojho uctu (desifrovanie by zlyhalo)."""
    return Fernet(_derive_fernet_key(f"{API_KEY_ENCRYPTION_SECRET}:user:{user_id}"))


def encrypt_secret(plain_text: str, user_id: Optional[int] = None) -> str:
    """Zasifruje hodnotu pomocou AES (Fernet) pred zapisom do DB. S `user_id`
    pouzije kluc odvodeny pre daneho pouzivatela (novy format "v2:")."""
    if user_id is None:
        return _fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
    return _V2_PREFIX + _user_fernet(user_id).encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str, user_id: Optional[int] = None) -> Optional[str]:
    """Desifruje hodnotu VYHRADNE v pamati, tesne pred pouzitim. Zvlada novy
    format (viazany na pouzivatela) aj starsi (spolocny kluc)."""
    try:
        if cipher_text.startswith(_V2_PREFIX):
            if user_id is None:
                return None
            return _user_fernet(user_id).decrypt(cipher_text[len(_V2_PREFIX):].encode("utf-8")).decode("utf-8")
        return _fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def is_legacy_ciphertext(cipher_text: str) -> bool:
    return not cipher_text.startswith(_V2_PREFIX)


def mask_key(plain_text: str) -> str:
    """Vrati maskovany nahlad kluca pre UI, napr. 'sk-ab...4a2b'."""
    cleaned = plain_text.strip()
    if len(cleaned) <= 8:
        return "•" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"


# ---------------------------------------------------------------------------
# Password reset tokeny — generujeme nahodny secret, do DB ukladame LEN jeho
# SHA-256 hash (rovnaky princip ako pri API klucoch: citatelne tajomstvo sa
# nikdy neuklada). Uzivatel dostane surovy token iba raz, v odkaze.
# ---------------------------------------------------------------------------
import secrets  # noqa: E402


def generate_reset_code() -> tuple[str, str]:
    """Vrati (surovy 6-cifernny kod pre email, sha256 hash pre DB).
    Kratky ciselny kod (nie dlhy nahodny token v odkaze) - pouzivatel ho
    prepise priamo v appke, nemusi opustit tab kvoli klikaniu na odkaz."""
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return code, digest


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Sanitizacia volneho textoveho vstupu (username, holdings symboly a pod.)
# ---------------------------------------------------------------------------
_CONTROL_CHARS = "".join(chr(c) for c in range(0, 32) if c not in (9, 10, 13))
_SANITIZE_TABLE = str.maketrans("", "", _CONTROL_CHARS)


def sanitize_text(value: str, max_length: int = 500) -> str:
    """Odstrani riadiace znaky (napr. null byte, ANSI escape) a orezovacie
    biele znaky. NEescapuje HTML - to je zodpovednost React (auto-escapuje
    pri renderovani) a nikdy sa tento vstup nevklada priamo do SQL (vsade
    pouzivame SQLAlchemy ORM s parametrizovanymi dotazmi)."""
    if not isinstance(value, str):
        return value
    cleaned = value.translate(_SANITIZE_TABLE).strip()
    return cleaned[:max_length]



# ---------------------------------------------------------------------------
# 2FA - TOTP (RFC 6238), kompatibilne s Google Authenticator, Authy a pod.
# ---------------------------------------------------------------------------
import hmac  # noqa: E402
import struct  # noqa: E402
import time as _time  # noqa: E402
from urllib.parse import quote as _quote  # noqa: E402


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def totp_now(secret_b32: str, at: Optional[float] = None) -> str:
    return _hotp(secret_b32, int((at if at is not None else _time.time()) // 30))


def verify_totp(secret_b32: str, code: str, at: Optional[float] = None, window: int = 1) -> bool:
    """Prijme kod z aktualneho 30s okna a +-1 okna (tolerancia rozdielu hodin)."""
    code = (code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return False
    counter = int((at if at is not None else _time.time()) // 30)
    return any(hmac.compare_digest(_hotp(secret_b32, counter + d), code) for d in range(-window, window + 1))


def totp_uri(secret_b32: str, username: str) -> str:
    label = _quote(f"AI Crypto Analytics:{username}")
    return f"otpauth://totp/{label}?secret={secret_b32}&issuer=AI%20Crypto%20Analytics&digits=6&period=30"
