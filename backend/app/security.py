"""Security utilities."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
import jwt
from passlib.context import CryptContext

from app.config import (
    API_KEY_ENCRYPTION_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY, PASSWORD_HASH_ROUNDS,
)

_pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"], deprecated="auto",
    pbkdf2_sha256__default_rounds=PASSWORD_HASH_ROUNDS, pbkdf2_sha256__min_rounds=PASSWORD_HASH_ROUNDS,
)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def needs_rehash(password_hash: str) -> bool:
    try:
        return _pwd_context.needs_update(password_hash)
    except ValueError:
        return False


_DUMMY_HASH = _pwd_context.hash("aca-timing-equalizer")


def dummy_verify(password: str) -> None:
    try:
        _pwd_context.verify(password, _DUMMY_HASH)
    except ValueError:
        pass


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def create_access_token(subject: int, username: str, token_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": str(subject), "username": username, "tv": token_version, "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key(API_KEY_ENCRYPTION_SECRET))


_V2_PREFIX = "v2:"


def _user_fernet(user_id: int) -> Fernet:
    return Fernet(_derive_fernet_key(f"{API_KEY_ENCRYPTION_SECRET}:user:{user_id}"))


def encrypt_secret(plain_text: str, user_id: Optional[int] = None) -> str:
    if user_id is None:
        return _fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
    return _V2_PREFIX + _user_fernet(user_id).encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str, user_id: Optional[int] = None) -> Optional[str]:
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
    cleaned = plain_text.strip()
    if len(cleaned) <= 8:
        return "•" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"


import secrets  # noqa: E402


def generate_reset_code() -> tuple[str, str]:
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return code, digest


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


_CONTROL_CHARS = "".join(chr(c) for c in range(0, 32) if c not in (9, 10, 13))
_SANITIZE_TABLE = str.maketrans("", "", _CONTROL_CHARS)


def sanitize_text(value: str, max_length: int = 500) -> str:
    if not isinstance(value, str):
        return value
    cleaned = value.translate(_SANITIZE_TABLE).strip()
    return cleaned[:max_length]



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
    code = (code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return False
    counter = int((at if at is not None else _time.time()) // 30)
    return any(hmac.compare_digest(_hotp(secret_b32, counter + d), code) for d in range(-window, window + 1))


def totp_uri(secret_b32: str, username: str) -> str:
    label = _quote(f"AI Crypto Analytics:{username}")
    return f"otpauth://totp/{label}?secret={secret_b32}&issuer=AI%20Crypto%20Analytics&digits=6&period=30"


import json as _json  # noqa: E402


def _forecast_message(user_id: int, provider: str, coin: str, horizon: str, prices, created: str) -> bytes:
    payload = [int(user_id), str(provider), str(coin).upper(), str(horizon), [float(p) for p in prices], str(created)]
    return _json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _forecast_key() -> bytes:
    return hashlib.sha256(f"forecast-signature:{JWT_SECRET_KEY}".encode("utf-8")).digest()


def sign_forecast(user_id: int, provider: str, coin: str, horizon: str, prices, created: str) -> str:
    msg = _forecast_message(user_id, provider, coin, horizon, prices, created)
    return hmac.new(_forecast_key(), msg, hashlib.sha256).hexdigest()


def verify_forecast_signature(signature: object, user_id: int, provider: str, coin: str, horizon: str,
                              prices, created: str) -> bool:
    if not isinstance(signature, str):
        return False
    try:
        expected = sign_forecast(user_id, provider, coin, horizon, prices, created)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, signature)
