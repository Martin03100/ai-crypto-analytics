"""Authentication API."""

from __future__ import annotations

import hmac
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    ACCOUNT_LOCKOUT_MINUTES, APP_ENV, AUTH_COOKIE_MAX_AGE_SECONDS, AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_SECURE, MAX_FAILED_LOGIN_ATTEMPTS, PASSWORD_RESET_TOKEN_MINUTES,
    RATE_LIMIT_LOGIN, RATE_LIMIT_RESET_CODE,
)
from app.deps import get_current_user, get_db
from app.models import EmailVerificationCode, PasswordResetToken, User
from app.rate_limit import check_rate_limit, get_client_ip, rate_limit_by_ip
from app.schemas import (
    USERNAME_RE, ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, TokenResponse,
    VerifyEmailRequest, VerifyResetCodeRequest,
)
from app.security import (
    create_access_token, decrypt_secret, dummy_verify, generate_reset_code, hash_password, hash_reset_token,
    needs_rehash, sanitize_text, verify_password,
)
from app.services import audit
from app.services.account_cleanup import release_email_if_unverified
from app.services.captcha import verify_captcha
from app.services import totp
from app.services.totp import consume_totp_code
from app.services.email_service import (
    is_email_configured, render_lockout_email, render_new_login_email, render_reset_password_email, send_email,
    subject as email_subject,
)
from app.services.premium import find_referrer, grant_referral_reward, is_premium
from app.services.verification import send_verification_code

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookie(response: Response, user: User) -> None:
    token = create_access_token(user.id, user.username, user.token_version)
    response.set_cookie(
        key=AUTH_COOKIE_NAME, value=token, max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True, secure=AUTH_COOKIE_SECURE, samesite=AUTH_COOKIE_SAMESITE, path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def register(payload: RegisterRequest, response: Response, request: Request, background_tasks: BackgroundTasks,
             db: Session = Depends(get_db)) -> TokenResponse:
    if not verify_captcha(payload.captcha_token, get_client_ip(request)):
        raise HTTPException(status_code=400, detail="Overenie, že nie si robot, zlyhalo. Skús to znova.")
    username = sanitize_text(payload.username, max_length=64)
    if not USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="Používateľské meno musí mať 3–32 znakov: písmená bez diakritiky, čísla, bodku, pomlčku alebo podčiarkovník.",
        )
    existing = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Toto pouzivatelske meno je uz obsadene.")

    email = sanitize_text(payload.email, max_length=255).lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Zadaj platnú emailovú adresu.")
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email is not None:
        if not (is_email_configured() and release_email_if_unverified(db, email)):
            raise HTTPException(status_code=400, detail="Tento email už používa iný účet.")

    referrer = find_referrer(db, payload.referral_code)
    user = User(username=username, password_hash=hash_password(payload.password), email=email,
                email_verified=False if is_email_configured() else None, lang=payload.lang or "en",
                referred_by_id=referrer.id if referrer else None)
    db.add(user)
    try:
        db.flush()
        audit.record(db, user.id, "register", request)
        if user.email_verified is None:   # no email confirmation in this deployment
            grant_referral_reward(db, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Toto pouzivatelske meno je uz obsadene.") from None
    db.refresh(user)
    if user.email_verified is False:
        send_verification_code(db, user, background_tasks)

    _set_auth_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user.id, user.username, user.token_version),
                          username=user.username, user_id=user.id, email=user.email,
                          email_verified=user.email_verified, totp_enabled=bool(user.totp_enabled),
                          premium=is_premium(user))


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def login(payload: LoginRequest, response: Response, request: Request, background_tasks: BackgroundTasks,
          db: Session = Depends(get_db)) -> TokenResponse:
    username = sanitize_text(payload.username, max_length=64)
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = db.query(User).filter(func.lower(User.username) == username.lower()).first()

    generic_error = HTTPException(status_code=401, detail="Nespravne pouzivatelske meno alebo heslo.")

    if user is None:
        dummy_verify(payload.password)
        raise generic_error

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        remaining = int((user.locked_until.replace(tzinfo=timezone.utc) - now).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Účet je dočasne uzamknutý pre priveľa neúspešných pokusov. Skús to znova o {remaining} min.",
        )

    if not verify_password(payload.password, user.password_hash):
        _register_failed_attempt(db, user, now, background_tasks, request)
        raise generic_error

    if user.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(status_code=401, detail="Zadaj 6-miestny kód z overovacej aplikácie (2FA).",
                                headers={"X-Error-Code": "totp_required"})
        secret = decrypt_secret(user.totp_secret or "", user.id)
        outcome = consume_totp_code(db, user, secret, payload.totp_code)
        if outcome == totp.REUSED:   # the right code, just already spent: not a guessing attempt
            raise HTTPException(status_code=401, detail="Tento kód z overovacej aplikácie už bol použitý. Počkaj na ďalší.")
        if outcome != totp.OK:
            _register_failed_attempt(db, user, now, background_tasks, request, details="2fa")
            raise HTTPException(status_code=401, detail="Nesprávny kód z overovacej aplikácie (2FA).")

    user.failed_login_attempts = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    ip, user_agent = audit.client_info(request)
    new_device = audit.is_new_device(db, user.id, user_agent)
    audit.record(db, user.id, "login_success", request)
    db.commit()
    if new_device and user.email and user.email_verified is not False and is_email_configured():
        _send_new_login_alert(background_tasks, user, now, user_agent, ip)

    _set_auth_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user.id, user.username, user.token_version),
                          username=user.username, user_id=user.id, email=user.email,
                          email_verified=user.email_verified, totp_enabled=bool(user.totp_enabled),
                          premium=is_premium(user))


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}


@router.get("/me", response_model=TokenResponse)
def me(user: User = Depends(get_current_user)) -> TokenResponse:
    return TokenResponse(access_token="", username=user.username, user_id=user.id, email=user.email,
                         email_verified=user.email_verified, totp_enabled=bool(user.totp_enabled),
                         premium=is_premium(user))


@router.post("/forgot-password", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def forgot_password(payload: ForgotPasswordRequest, request: Request, background_tasks: BackgroundTasks,
                    db: Session = Depends(get_db)) -> dict:
    if not verify_captcha(payload.captcha_token, get_client_ip(request)):
        raise HTTPException(status_code=400, detail="Overenie, že nie si robot, zlyhalo. Skús to znova.")
    generic_response = {
        "success": True,
        "message": "Ak účet s emailom existuje, poslali sme naň kód na reset hesla.",
    }
    email = sanitize_text(payload.email, max_length=255).lower()
    check_rate_limit(f"forgot-email:{email}", 3, 900)
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.email:
        return generic_response

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used.is_(False)
    ).update({"used": True})

    code, code_hash = generate_reset_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES)
    db.add(PasswordResetToken(user_id=user.id, token_hash=code_hash, expires_at=expires_at))
    db.commit()

    text_body, html_body = render_reset_password_email(user.username, code, PASSWORD_RESET_TOKEN_MINUTES, user.lang)
    title = email_subject("reset", user.lang)
    if is_email_configured():
        background_tasks.add_task(send_email, user.email, title, text_body, html_body)
    else:
        send_email(user.email, title, text_body, html_body)

    result = dict(generic_response)
    if not is_email_configured() and APP_ENV != "production":
        result["dev_reset_code"] = code
    return result


def _find_valid_reset_token(db: Session, user_id: int, code: str) -> PasswordResetToken | None:
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user_id, PasswordResetToken.used.is_(False))
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if row is None:
        return None
    now = datetime.now(timezone.utc)
    if row.expires_at.replace(tzinfo=timezone.utc) < now:
        return None
    if not hmac.compare_digest(row.token_hash, hash_reset_token(code)):
        return None
    return row


@router.post("/verify-reset-code", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_RESET_CODE))])
def verify_reset_code(payload: VerifyResetCodeRequest, db: Session = Depends(get_db)) -> dict:
    email = sanitize_text(payload.email, max_length=255).lower()
    check_rate_limit(f"reset-code:{email}", 5, 900)
    user = db.query(User).filter(User.email == email).first()
    if user is None or _find_valid_reset_token(db, user.id, payload.code) is None:
        raise HTTPException(status_code=400, detail="Kód je nesprávny alebo expirovaný.")
    return {"valid": True}


@router.post("/reset-password", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_RESET_CODE))])
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    email = sanitize_text(payload.email, max_length=255).lower()
    check_rate_limit(f"reset-code:{email}", 5, 900)
    user = db.query(User).filter(User.email == email).first()
    row = _find_valid_reset_token(db, user.id, payload.code) if user else None

    if user is None or row is None:
        raise HTTPException(status_code=400, detail="Kód je nesprávny alebo expirovaný.")

    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    user.failed_login_attempts = 0
    user.locked_until = None
    row.used = True
    audit.record(db, user.id, "password_reset", request)
    db.commit()

    return {"success": True, "message": "Heslo bolo zmenené. Prihlás sa novým heslom."}



def _send_new_login_alert(background_tasks: BackgroundTasks, user: User, now: datetime,
                          user_agent: str | None, ip: str | None) -> None:
    when = now.strftime("%d.%m.%Y %H:%M UTC")
    text_body, html_body = render_new_login_email(user.username, when, audit.describe_user_agent(user_agent), ip or "?",
                                                  user.lang)
    background_tasks.add_task(send_email, user.email, email_subject("login", user.lang), text_body, html_body)


def _register_failed_attempt(db: Session, user: User, now, background_tasks: BackgroundTasks,
                             request: Request | None = None, details: str | None = None) -> None:
    user.failed_login_attempts += 1
    locked = False
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = now + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
        user.failed_login_attempts = 0
        locked = True
    audit.record(db, user.id, "login_failed", request, details)
    if locked:
        audit.record(db, user.id, "account_locked", request)
    db.commit()
    if locked and user.email and is_email_configured():
        text_body, html_body = render_lockout_email(user.username, ACCOUNT_LOCKOUT_MINUTES, user.lang)
        threading.Thread(target=send_email, daemon=True, args=(
            user.email, email_subject("lock", user.lang), text_body, html_body)).start()


@router.post("/verify-email", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_RESET_CODE))])
def verify_email(payload: VerifyEmailRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if user.email_verified is not False:
        return {"success": True, "email_verified": True}
    check_rate_limit(f"verify-email:{user.id}", 5, 900)
    row = (db.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id)
           .order_by(EmailVerificationCode.created_at.desc()).first())
    if (row is None or row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
            or not hmac.compare_digest(row.code_hash, hash_reset_token(payload.code.strip()))):
        raise HTTPException(status_code=400, detail="Kód je nesprávny alebo expirovaný.")
    user.email_verified = True
    db.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id).delete(synchronize_session=False)
    grant_referral_reward(db, user)
    db.commit()
    return {"success": True, "email_verified": True}


@router.post("/resend-verification", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_RESET_CODE))])
def resend_verification(background_tasks: BackgroundTasks, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> dict:
    if user.email_verified is not False:
        return {"success": True}
    check_rate_limit(f"resend-verification:{user.id}", 3, 900)
    send_verification_code(db, user, background_tasks)
    return {"success": True}
