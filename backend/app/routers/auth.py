"""app/routers/auth.py — registracia, prihlasenie, odhlasenie a reset hesla.

JWT zije v HttpOnly cookie (viz app/deps.py). Prihlasenie je chranene proti
hrubej sile dvoma vrstvami: rate limit podla IP (app/rate_limit.py) a
account lockout podla poctu neuspesnych pokusov (app/config.py).
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
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
    ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, TokenResponse,
    VerifyEmailRequest, VerifyResetCodeRequest,
)
from app.security import (
    create_access_token, generate_reset_code, hash_password, hash_reset_token,
    decrypt_secret, sanitize_text, verify_password, verify_totp,
)
from app.services.captcha import verify_captcha
from app.services.email_service import is_email_configured, render_lockout_email, render_reset_password_email, send_email
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
    existing = db.query(User).filter(User.username == username).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Toto pouzivatelske meno je uz obsadene.")

    email = sanitize_text(payload.email, max_length=255).lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Zadaj platnú emailovú adresu.")
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email is not None:
        raise HTTPException(status_code=400, detail="Tento email už používa iný účet.")

    # Overovanie emailu je zapnute len ak appka vie posielat emaily.
    user = User(username=username, password_hash=hash_password(payload.password), email=email,
                email_verified=False if is_email_configured() else None)
    db.add(user)
    db.commit()
    db.refresh(user)
    if user.email_verified is False:
        send_verification_code(db, user, background_tasks)

    _set_auth_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user.id, user.username, user.token_version),
                          username=user.username, user_id=user.id, email=user.email,
                          email_verified=user.email_verified, totp_enabled=bool(user.totp_enabled))


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def login(payload: LoginRequest, response: Response, background_tasks: BackgroundTasks,
          db: Session = Depends(get_db)) -> TokenResponse:
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
        _register_failed_attempt(db, user, now, background_tasks)
        raise generic_error

    if user.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(status_code=401, detail="Zadaj 6-miestny kód z overovacej aplikácie (2FA).")
        secret = decrypt_secret(user.totp_secret or "", user.id)
        if not secret or not verify_totp(secret, payload.totp_code):
            _register_failed_attempt(db, user, now, background_tasks)
            raise HTTPException(status_code=401, detail="Nesprávny kód z overovacej aplikácie (2FA).")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    _set_auth_cookie(response, user)
    return TokenResponse(access_token=create_access_token(user.id, user.username, user.token_version),
                          username=user.username, user_id=user.id, email=user.email,
                          email_verified=user.email_verified, totp_enabled=bool(user.totp_enabled))


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}


@router.get("/me", response_model=TokenResponse)
def me(user: User = Depends(get_current_user)) -> TokenResponse:
    """Zisti, ci je pouzivatel prihlaseny na zaklade HttpOnly cookie (volane
    pri nacitani appky namiesto citania tokenu z localStorage)."""
    return TokenResponse(access_token="", username=user.username, user_id=user.id, email=user.email,
                         email_verified=user.email_verified, totp_enabled=bool(user.totp_enabled))


@router.post("/forgot-password", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_LOGIN))])
def forgot_password(payload: ForgotPasswordRequest, request: Request, background_tasks: BackgroundTasks,
                    db: Session = Depends(get_db)) -> dict:
    if not verify_captcha(payload.captcha_token, get_client_ip(request)):
        raise HTTPException(status_code=400, detail="Overenie, že nie si robot, zlyhalo. Skús to znova.")
    """Vzdy vrati rovnaku genericku odpoved (aj ked pouzivatel/email
    neexistuje), aby sa nedalo cez tento endpoint zistovat, kto ma ucet."""
    generic_response = {
        "success": True,
        "message": "Ak účet s emailom existuje, poslali sme naň kód na reset hesla.",
    }
    email = sanitize_text(payload.email, max_length=255).lower()
    # Per-email limit (nie len per-IP): bez neho by sa dala cudzia schranka
    # zahltit reset emailmi z mnohych IP adries. Aplikuje sa rovnako pre
    # existujuce aj neexistujuce emaily - neprezradza, kto ma ucet.
    check_rate_limit(f"forgot-email:{email}", 3, 900)
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.email:
        return generic_response

    # Predchadzajuce nepouzite kody pre tohto pouzivatela znehodnot - platny
    # je vzdy len ten najnovsi, aby aj starsi unikly/nezmazany kod prestal
    # fungovat hned, ako si pouzivatel vyziada novy.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used.is_(False)
    ).update({"used": True})

    code, code_hash = generate_reset_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES)
    db.add(PasswordResetToken(user_id=user.id, token_hash=code_hash, expires_at=expires_at))
    db.commit()

    text_body, html_body = render_reset_password_email(user.username, code, PASSWORD_RESET_TOKEN_MINUTES)
    subject = "Kód na obnovenie hesla — AI Crypto Analytics"
    if is_email_configured():
        # Odoslanie AZ PO odpovedi: inak by odpoved pre existujuci email trvala
        # citelne dlhsie (odosielanie) a z casu by sa dalo zistit, kto ma ucet.
        background_tasks.add_task(send_email, user.email, subject, text_body, html_body)
    else:
        send_email(user.email, subject, text_body, html_body)  # len zaloguje

    result = dict(generic_response)
    # V dev rezime (bez SMTP) vratime kod priamo v odpovedi, aby sa dal tok
    # realne otestovat bez emailoveho servera. V PRODUKCII sa kod NIKDY
    # nevracia v odpovedi, aj keby administrator zabudol nastavit SMTP —
    # inak by ktokolvek, kto pozna existujuci email, mohol cez tento
    # endpoint ziskat funkcny reset kod priamo z API odpovede.
    if not is_email_configured() and APP_ENV != "production":
        result["dev_reset_code"] = code
    return result


def _find_valid_reset_token(db: Session, user_id: int, code: str) -> PasswordResetToken | None:
    """Najde najnovsi nepouzity kod pre pouzivatela a overi, ci sedi so
    zadanym kodom a ci este neexpiroval. Hlada podla user_id (nie len podla
    hashu kodu) - 6-ciferny kod ma oveľa mensi priestor nez povodny dlhy
    nahodny token, takze bez filtra na konkretneho pouzivatela by teoreticky
    mohla (velmi zriedkavo) nastat zhoda hashu naprieč dvoma rôznymi uctami."""
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
    if row.token_hash != hash_reset_token(code):
        return None
    return row


@router.post("/verify-reset-code", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_RESET_CODE))])
def verify_reset_code(payload: VerifyResetCodeRequest, db: Session = Depends(get_db)) -> dict:
    """Overi kod BEZ toho, aby ho spotreboval (nemeni 'used') - appka tym
    padom vie hned ukazat 'kod je spravny' a prejst na formular noveho
    hesla, este predtym, nez si pouzivatel heslo skutocne zvoli."""
    email = sanitize_text(payload.email, max_length=255).lower()
    check_rate_limit(f"reset-code:{email}", 5, 900)
    user = db.query(User).filter(User.email == email).first()
    if user is None or _find_valid_reset_token(db, user.id, payload.code) is None:
        raise HTTPException(status_code=400, detail="Kód je nesprávny alebo expirovaný.")
    return {"valid": True}


@router.post("/reset-password", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_RESET_CODE))])
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    email = sanitize_text(payload.email, max_length=255).lower()
    # Spolocny limit s /verify-reset-code: 6-ciferny kod ma len 1 000 000
    # moznosti - bez limitu per-email (nielen per-IP) by sa dal uhadnut
    # distribuovanym utokom z mnohych IP adries pocas 15 minut platnosti.
    check_rate_limit(f"reset-code:{email}", 5, 900)
    user = db.query(User).filter(User.email == email).first()
    row = _find_valid_reset_token(db, user.id, payload.code) if user else None

    if user is None or row is None:
        raise HTTPException(status_code=400, detail="Kód je nesprávny alebo expirovaný.")

    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1  # invaliduje vsetky doteraz vydane JWT
    user.failed_login_attempts = 0
    user.locked_until = None
    row.used = True
    db.commit()

    return {"success": True, "message": "Heslo bolo zmenené. Prihlás sa novým heslom."}



def _register_failed_attempt(db: Session, user: User, now, background_tasks: BackgroundTasks) -> None:
    """Zapocita neuspesny pokus; pri uzamknuti uctu posle majitelovi upozornenie."""
    user.failed_login_attempts += 1
    locked = False
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = now + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
        user.failed_login_attempts = 0
        locked = True
    db.commit()
    if locked and user.email and is_email_configured():
        text_body, html_body = render_lockout_email(user.username, ACCOUNT_LOCKOUT_MINUTES)
        # Samostatne vlakno, NIE background_tasks: neuspesne prihlasenie vzdy konci
        # chybou 401 a pri chybovej odpovedi FastAPI ulohy na pozadi zahodi -
        # upozornenie by sa tak nikdy neodoslalo.
        threading.Thread(target=send_email, daemon=True, args=(
            user.email, "Upozornenie: pokusy o prihlásenie — AI Crypto Analytics", text_body, html_body)).start()


@router.post("/verify-email", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_RESET_CODE))])
def verify_email(payload: VerifyEmailRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if user.email_verified is not False:
        return {"success": True, "email_verified": True}
    check_rate_limit(f"verify-email:{user.id}", 5, 900)
    row = (db.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id)
           .order_by(EmailVerificationCode.created_at.desc()).first())
    if (row is None or row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
            or row.code_hash != hash_reset_token(payload.code.strip())):
        raise HTTPException(status_code=400, detail="Kód je nesprávny alebo expirovaný.")
    user.email_verified = True
    db.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == user.id).delete(synchronize_session=False)
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
