"""
app/routers/account.py
========================
Sprava API klucov (Gemini/OpenAI/Anthropic/DeepSeek/Grok). Kluce sa
sifruju cez AES-256 (Fernet) PRED zapisom do DB (app/security.py) a
API nikdy nevracia plny plain-text kluc spat do UI - iba maskovany
nahlad (napr. "sk-a...4a2b").
"""

from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import (
    AUTH_COOKIE_MAX_AGE_SECONDS, AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE,
    PROVIDER_KEY_LINKS, PROVIDERS, RATE_LIMIT_ACCOUNT_SENSITIVE, RATE_LIMIT_API_KEY_TEST,
)
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import (
    ApiKey, CommunityVote, EmailVerificationCode, ForecastEvaluation, ForecastHistory, PasswordResetToken, PortfolioHistory, PriceTip, User,
)
from app.rate_limit import rate_limit_by_user
from app.schemas import (
    ApiKeyIn, ApiKeyStatus, ChangePasswordRequest, DeleteAccountRequest, TotpCodeRequest, TotpDisableRequest, UpdateEmailRequest,
)
from app.security import (
    create_access_token, decrypt_secret, encrypt_secret, generate_totp_secret, hash_password, mask_key, sanitize_text,
    totp_uri, verify_password, verify_totp,
)
from app.services.email_service import is_email_configured
from app.services.verification import send_verification_code
from app.services.ai_engine import test_api_key, validate_custom_base_url

router = APIRouter(prefix="/api/account", tags=["account"])


def _reissue_cookie(response: Response, user: User) -> None:
    token = create_access_token(user.id, user.username, user.token_version)
    response.set_cookie(
        key=AUTH_COOKIE_NAME, value=token, max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True, secure=AUTH_COOKIE_SECURE, samesite=AUTH_COOKIE_SAMESITE, path="/",
    )


@router.get("/api-keys", response_model=List[ApiKeyStatus])
def list_api_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> List[ApiKeyStatus]:
    existing = {row.provider: row for row in db.query(ApiKey).filter(ApiKey.user_id == user.id).all()}
    result: List[ApiKeyStatus] = []
    for label, provider_key in PROVIDERS.items():
        row = existing.get(provider_key)
        result.append(ApiKeyStatus(
            provider=provider_key, label=label, connected=row is not None,
            masked_preview=(f"••••...{row.key_suffix}" if row else None),
        ))
    return result


@router.get("/api-keys/links")
def api_key_links() -> dict:
    """Priame odkazy na vyvojarske portaly jednotlivych AI providerov,
    pre tlacidlo 'Získať API kľúč' na Account stranke."""
    return PROVIDER_KEY_LINKS


@router.post("/api-keys/{provider}/test", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_API_KEY_TEST))])
def test_api_key_endpoint(provider: str, user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)) -> dict:
    api_key = get_decrypted_api_key(db, user.id, provider)
    if not api_key:
        return {"valid": False, "message": "Najprv ulož API kľúč pre tohto providera."}
    ok, error = test_api_key(provider, api_key)
    return {"valid": ok, "message": "Kľúč je platný a funkčný." if ok else (error or "Kľúč sa nepodarilo overiť.")}


@router.put("/email", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def update_email(payload: UpdateEmailRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict:
    """Email sa pouziva na prihlasenie/reset hesla - musi byt jedinecny naprieč
    vsetkymi uctami (inak by "zabudnute heslo" nevedelo spolahlivo najst
    spravny ucet). Odkedy je email povinny pri registracii, tento endpoint
    uz nedovoluje email VYMAZAT (poslat prazdny/null) - inak by si tym
    pouzivatel sam zablokoval "Zabudnuté heslo" bez akehokolvek varovania."""
    email = sanitize_text(payload.email, max_length=255).lower() if payload.email else ""
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Zadaj platnú emailovú adresu.")
    existing = db.query(User).filter(User.email == email, User.id != user.id).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Tento email už používa iný účet.")
    changed = user.email != email
    user.email = email
    if changed and is_email_configured():
        user.email_verified = False  # novy email treba overit
    db.commit()
    if changed and user.email_verified is False:
        send_verification_code(db, user, background_tasks)
    return {"success": True, "email": user.email, "email_verified": user.email_verified}


@router.post("/change-password", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def change_password(payload: ChangePasswordRequest, response: Response, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Aktuálne heslo nie je správne.")
    user.password_hash = hash_password(payload.new_password)
    # Zmena hesla invaliduje vsetky doteraz vydane JWT (viz app/deps.py);
    # aktualnemu zariadeniu hned vystavime novy cookie, aby ostalo prihlasene.
    user.token_version += 1
    db.commit()
    _reissue_cookie(response, user)
    return {"success": True, "message": "Heslo bolo úspešne zmenené."}


@router.post("/logout-all-devices", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def logout_all_devices(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    user.token_version += 1
    db.commit()
    _reissue_cookie(response, user)
    return {"success": True, "message": "Odhlásené zo všetkých ostatných zariadení."}


@router.put("/api-keys", response_model=ApiKeyStatus, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def upsert_api_key(payload: ApiKeyIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> ApiKeyStatus:
    if payload.provider not in PROVIDERS.values():
        raise HTTPException(status_code=400, detail="Neznamy AI provider.")

    if not payload.api_key.strip():
        db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == payload.provider).delete()
        db.commit()
        label = next(k for k, v in PROVIDERS.items() if v == payload.provider)
        return ApiKeyStatus(provider=payload.provider, label=label, connected=False, masked_preview=None)

    key_value = payload.api_key.strip()
    secret_value = key_value
    if payload.provider == "custom":
        # Okrem kluca aj adresa a model. Adresa sa overuje (https + verejny
        # internet), inak by cez appku slo volat interne servery (SSRF).
        model = (payload.model or "").strip()
        if not model:
            raise HTTPException(status_code=400, detail="Zadaj názov modelu vlastného providera.")
        problem = validate_custom_base_url(payload.base_url or "")
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        secret_value = json.dumps({"base_url": (payload.base_url or "").strip(), "model": model, "key": key_value})
    row = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == payload.provider).first()
    encrypted = encrypt_secret(secret_value, user.id)
    suffix = key_value[-4:] if len(key_value) >= 4 else key_value

    if row is None:
        row = ApiKey(user_id=user.id, provider=payload.provider, encrypted_key=encrypted, key_suffix=suffix)
        db.add(row)
    else:
        row.encrypted_key = encrypted
        row.key_suffix = suffix
    db.commit()

    label = next(k for k, v in PROVIDERS.items() if v == payload.provider)
    return ApiKeyStatus(provider=payload.provider, label=label, connected=True,
                         masked_preview=mask_key(key_value))


@router.delete("/api-keys/{provider}", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def delete_api_key(provider: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == provider).delete()
    db.commit()
    return {"success": True}


@router.post("/delete", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def delete_account(payload: DeleteAccountRequest, response: Response, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    """GDPR - pravo na vymazanie: pouzivatel si zmaze ucet A VSETKY svoje data
    sam, bez nutnosti niekoho kontaktovat. Vyzaduje heslo (ochrana pred
    zneuzitim otvorenej relacie na cudzom pocitaci). Data sa mazu explicitne
    po tabulkach - SQLite bez PRAGMA foreign_keys by kaskadu v DB nevykonal."""
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Aktuálne heslo nie je správne.")
    for model in (ApiKey, ForecastHistory, PortfolioHistory, CommunityVote, PasswordResetToken, ForecastEvaluation, PriceTip, EmailVerificationCode):
        db.query(model).filter(model.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    from app.config import AUTH_COOKIE_NAME
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}



# ---------------------------------------------------------------------------
# 2FA (TOTP)
# ---------------------------------------------------------------------------
@router.post("/2fa/setup", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def totp_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Vygeneruje tajomstvo (zatial len "cakajuce") - 2FA sa zapne az po
    overeni prveho kodu, aby sa pouzivatel omylom nezamkol."""
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA už máš zapnuté.")
    secret = generate_totp_secret()
    user.totp_pending_secret = encrypt_secret(secret, user.id)
    db.commit()
    return {"secret": secret, "otpauth_uri": totp_uri(secret, user.username)}


@router.post("/2fa/enable", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def totp_enable(payload: TotpCodeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    secret = decrypt_secret(user.totp_pending_secret or "", user.id)
    if not secret:
        raise HTTPException(status_code=400, detail="Najprv spusti nastavenie 2FA.")
    if not verify_totp(secret, payload.code):
        raise HTTPException(status_code=400, detail="Nesprávny kód z overovacej aplikácie (2FA).")
    user.totp_secret, user.totp_pending_secret, user.totp_enabled = user.totp_pending_secret, None, True
    db.commit()
    return {"success": True, "totp_enabled": True}


@router.post("/2fa/disable", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def totp_disable(payload: TotpDisableRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not user.totp_enabled:
        return {"success": True, "totp_enabled": False}
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Aktuálne heslo nie je správne.")
    secret = decrypt_secret(user.totp_secret or "", user.id)
    if not secret or not verify_totp(secret, payload.code):
        raise HTTPException(status_code=400, detail="Nesprávny kód z overovacej aplikácie (2FA).")
    user.totp_secret, user.totp_pending_secret, user.totp_enabled = None, None, False
    db.commit()
    return {"success": True, "totp_enabled": False}
