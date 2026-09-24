"""app/routers/auth.py — registracia, prihlasenie, odhlasenie a reset hesla.

JWT zije v HttpOnly cookie (viz app/deps.py). Prihlasenie je chranene proti
hrubej sile dvoma vrstvami: rate limit podla IP (app/rate_limit.py) a
account lockout podla poctu neuspesnych pokusov (app/config.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import (
    ACCOUNT_LOCKOUT_MINUTES, APP_ENV, AUTH_COOKIE_MAX_AGE_SECONDS, AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_SECURE, FRONTEND_URL, MAX_FAILED_LOGIN_ATTEMPTS, PASSWORD_RESET_TOKEN_MINUTES,
    RATE_LIMIT_LOGIN,
)
from app.deps import get_current_user, get_db
from app.models import PasswordResetToken, User
from app.rate_limit import rate_limit_by_ip
from app.schemas import ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, TokenResponse
from app.security import (
    create_access_token, generate_reset_token, hash_password, hash_reset_token,
    sanitize_text, verify_password,
)
from app.services.email_service import is_smtp_configured, render_reset_password_email, send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookie(response: Response, user: User) -> None:
    token = create_access_token(user.id, user.username, user.token_version)
    response.set_cookie(
        key=AUTH_COOKIE_NAME, value=token, max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True, secure=AUTH_COOKIE_SECURE, samesite=AUTH_COOKIE_SAMESITE, path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    username = sanitize_text(payload.username, max_length=64)
    existing = db.query(User).filter(User.username == username).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Toto pouzivatelske meno je uz obsadene.")

    email = sanitize_text(payload.email, max_length=255)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Zadaj platnú emailovú adresu.")
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email is not None:
        raise HTTPException(status_code=400, detail="Tento email už používa iný účet.")

    user = User(username=username, password_hash=hash_password(payload.password), email=email)
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_auth_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user.id, user.username, user.token_version),
                          username=user.username, user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    username = sanitize_text(payload.username, max_length=64)
    user = db.query(User).filter(User.username == username).first()

    # Rovnaka chybova sprava pre "neexistuje" aj "zle heslo" (nikdy neprezradzuj,
    # ktore pouzivatelske mena existuju).
    generic_error = HTTPException(status_code=401, detail="Nespravne pouzivatelske meno alebo heslo.")

    if user is None:
        raise generic_error

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        remaining = int((user.locked_until.replace(tzinfo=timezone.utc) - now).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Účet je dočasne uzamknutý pre priveľa neúspešných pokusov. Skús to znova o {remaining} min.",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
        db.commit()
        raise generic_error

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    _set_auth_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user.id, user.username, user.token_version),
                          username=user.username, user_id=user.id, email=user.email)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}


@router.get("/me", response_model=TokenResponse)
def me(user: User = Depends(get_current_user)) -> TokenResponse:
    """Zisti, ci je pouzivatel prihlaseny na zaklade HttpOnly cookie (volane
    pri nacitani appky namiesto citania tokenu z localStorage)."""
    return TokenResponse(access_token="", username=user.username, user_id=user.id, email=user.email)


@router.post("/forgot-password", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """Vzdy vrati rovnaku genericku odpoved (aj ked pouzivatel/email
    neexistuje), aby sa nedalo cez tento endpoint zistovat, kto ma ucet."""
    generic_response = {
        "success": True,
        "message": "Ak účet s emailom existuje, poslali sme naň odkaz na reset hesla.",
    }
    username = sanitize_text(payload.username, max_length=64)
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.email:
        return generic_response

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES)
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()

    reset_link = f"{FRONTEND_URL}/auth?resetToken={raw_token}"
    text_body, html_body = render_reset_password_email(user.username, reset_link, PASSWORD_RESET_TOKEN_MINUTES)
    sent = send_email(user.email, "Obnovenie hesla — AI Crypto Analytics", text_body, html_body)

    result = dict(generic_response)
    # V dev rezime (bez SMTP) vratime link priamo v odpovedi, aby sa dal
    # tok reálne otestovat bez emailoveho servera. V PRODUKCII sa link
    # NIKDY nevracia v odpovedi, aj keby administrator zabudol nastavit
    # SMTP — inak by ktokolvek, kto pozna existujuce pouzivatelske meno,
    # mohol cez tento endpoint ziskat funkcny reset odkaz priamo z API
    # odpovede, bez potreby pristupu k danemu emailu.
    if not sent and not is_smtp_configured() and APP_ENV != "production":
        result["dev_reset_link"] = reset_link
    return result


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    token_hash = hash_reset_token(payload.token)
    now = datetime.now(timezone.utc)
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()

    if row is None or row.used or row.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=400, detail="Odkaz na reset hesla je neplatný alebo expirovaný.")

    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Odkaz na reset hesla je neplatný alebo expirovaný.")

    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1  # invaliduje vsetky doteraz vydane JWT
    user.failed_login_attempts = 0
    user.locked_until = None
    row.used = True
    db.commit()

    return {"success": True, "message": "Heslo bolo zmenené. Prihlás sa novým heslom."}
