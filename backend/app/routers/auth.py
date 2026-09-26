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
    AUTH_COOKIE_SECURE, MAX_FAILED_LOGIN_ATTEMPTS, PASSWORD_RESET_TOKEN_MINUTES,
    RATE_LIMIT_LOGIN, RATE_LIMIT_RESET_CODE,
)
from app.deps import get_current_user, get_db
from app.models import PasswordResetToken, User
from app.rate_limit import check_rate_limit, rate_limit_by_ip
from app.schemas import (
    ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, TokenResponse,
    VerifyResetCodeRequest,
)
from app.security import (
    create_access_token, generate_reset_code, hash_password, hash_reset_token,
    sanitize_text, verify_password,
)
from app.services.email_service import is_email_configured, render_reset_password_email, send_email

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

    email = sanitize_text(payload.email, max_length=255).lower()
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
    sent = send_email(user.email, "Kód na obnovenie hesla — AI Crypto Analytics", text_body, html_body)

    result = dict(generic_response)
    # V dev rezime (bez SMTP) vratime kod priamo v odpovedi, aby sa dal tok
    # realne otestovat bez emailoveho servera. V PRODUKCII sa kod NIKDY
    # nevracia v odpovedi, aj keby administrator zabudol nastavit SMTP —
    # inak by ktokolvek, kto pozna existujuci email, mohol cez tento
    # endpoint ziskat funkcny reset kod priamo z API odpovede.
    if not sent and not is_email_configured() and APP_ENV != "production":
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
