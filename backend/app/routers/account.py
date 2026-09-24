"""
app/routers/account.py
========================
Sprava API klucov (Gemini/OpenAI/Anthropic/DeepSeek/Grok). Kluce sa
sifruju cez AES-256 (Fernet) PRED zapisom do DB (app/security.py) a
API nikdy nevracia plny plain-text kluc spat do UI - iba maskovany
nahlad (napr. "sk-a...4a2b").
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import (
    AUTH_COOKIE_MAX_AGE_SECONDS, AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE,
    PROVIDER_KEY_LINKS, PROVIDERS, RATE_LIMIT_ACCOUNT_SENSITIVE, RATE_LIMIT_API_KEY_TEST,
)
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import ApiKey, User
from app.rate_limit import rate_limit_by_user
from app.schemas import ApiKeyIn, ApiKeyStatus, ChangePasswordRequest, UpdateEmailRequest
from app.security import create_access_token, encrypt_secret, hash_password, mask_key, sanitize_text, verify_password
from app.services.ai_engine import test_api_key

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
def update_email(payload: UpdateEmailRequest, user: User = Depends(get_current_user),
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
    user.email = email
    db.commit()
    return {"success": True, "email": user.email}


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
    row = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == payload.provider).first()
    encrypted = encrypt_secret(key_value)
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
