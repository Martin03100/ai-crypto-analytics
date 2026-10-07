"""FastAPI dependencies."""

from __future__ import annotations

from typing import Iterator, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import AUTH_COOKIE_NAME
from app.database import SessionLocal
from app.models import User
from app.security import decode_access_token

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


_UNVERIFIED_ALLOWED_PATHS = ("/api/auth/", "/api/account/email", "/api/account/delete")


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
    try:
        user = db.get(User, int(user_id))
    except (TypeError, ValueError):
        raise credentials_error from None
    if user is None:
        raise credentials_error
    token_version = payload.get("tv", 0)
    if token_version != user.token_version:
        raise credentials_error
    if user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tento účet je zablokovaný.")
    if user.email_verified is False and not request.url.path.startswith(_UNVERIFIED_ALLOWED_PATHS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Najprv si over email kódom, ktorý sme ti poslali.")
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    from app.services.roles import is_admin

    if not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Prístup len pre administrátora.")
    if not user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrátor musí mať zapnuté 2FA.")
    return user


def save_limit_reached(db: Session, model, user_id: int) -> bool:
    from app import config

    return db.query(model).filter(model.user_id == user_id).count() >= config.MAX_SAVED_ITEMS_PER_USER


def ensure_below_save_limit(db: Session, model, user_id: int) -> None:
    from app.config import MAX_SAVED_ITEMS_PER_USER

    if save_limit_reached(db, model, user_id):
        raise HTTPException(status_code=400, detail=f"Dosiahol si limit {MAX_SAVED_ITEMS_PER_USER} uložených "
                                                    "záznamov. Zmaž staršie a skús to znova.")


def get_decrypted_api_key(db, user_id: int, provider: str):
    from app.models import ApiKey
    from app.security import decrypt_secret, encrypt_secret, is_legacy_ciphertext

    row = db.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.provider == provider).first()
    if row is None:
        return None
    plain = decrypt_secret(row.encrypted_key, user_id)
    if plain is not None and is_legacy_ciphertext(row.encrypted_key):
        row.encrypted_key = encrypt_secret(plain, user_id)
        db.commit()
    return plain
