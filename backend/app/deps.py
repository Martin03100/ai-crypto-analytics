"""app/deps.py — spolocne FastAPI zavislosti (DB session, current user).

Autentifikacia: token sa cita PREDNOSTNE z HttpOnly cookie (nastavenej
v routers/auth.py), co chrani pred XSS krádežou tokenu z localStorage.
Ako fallback sa akceptuje aj klasicka `Authorization: Bearer` hlavicka,
aby ostali funkcne API-only klienti (napr. curl/Postman pri vyvoji).
"""

from __future__ import annotations

from typing import Iterator, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import AUTH_COOKIE_NAME
from app.database import SessionLocal
from app.models import User
from app.security import decode_access_token

# auto_error=False, lebo primarny zdroj je cookie - Bearer header je len fallback.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_token(request: Request, header_token: Optional[str]) -> Optional[str]:
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    return cookie_token or header_token


def get_current_user(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Neplatne alebo expirovane prihlasenie.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _extract_token(request, header_token)
    if not token:
        raise credentials_error
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error
    user = db.get(User, int(user_id))
    if user is None:
        raise credentials_error
    # Ak sa medzitym pouzivatel odhlasil zo vsetkych zariadeni alebo zmenil
    # heslo, token_version v DB sa zvysil a stare tokeny uz nie su platne.
    token_version = payload.get("tv", 0)
    if token_version != user.token_version:
        raise credentials_error
    return user


def get_decrypted_api_key(db, user_id: int, provider: str):
    """Najde ulozeny (sifrovany) API kluc pouzivatela pre providera a desifruje
    ho AZ TU, tesne pred pouzitim v aktivnom API volani. Viz app/security.py."""
    from app.models import ApiKey
    from app.security import decrypt_secret

    row = db.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.provider == provider).first()
    if row is None:
        return None
    return decrypt_secret(row.encrypted_key)
