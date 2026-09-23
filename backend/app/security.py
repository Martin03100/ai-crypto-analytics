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


def encrypt_secret(plain_text: str) -> str:
    """Zasifruje hodnotu pomocou AES-256 (Fernet) pred zapisom do DB."""
    return _fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> Optional[str]:
    """Desifruje hodnotu VYHRADNE v pamati, tesne pred pouzitim v API volani."""
    try:
        return _fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


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


def generate_reset_token() -> tuple[str, str]:
    """Vrati (surovy_token_pre_link, sha256_hash_pre_db)."""
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest


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
