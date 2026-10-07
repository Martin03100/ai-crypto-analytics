"""Account API."""

from __future__ import annotations

import json
from datetime import timezone
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import (
    AUTH_COOKIE_MAX_AGE_SECONDS, AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE,
    DEFAULT_COIN_IDS, PROVIDER_KEY_LINKS, PROVIDERS, RATE_LIMIT_ACCOUNT_SENSITIVE, RATE_LIMIT_API_KEY_TEST,
)
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import ApiKey, AuditEvent, User
from app.rate_limit import rate_limit_by_user
from app.schemas import (
    ApiKeyIn, ApiKeyStatus, ChangePasswordRequest, DeleteAccountRequest, TotpCodeRequest, TotpDisableRequest, UpdateEmailRequest,
    WatchlistIn,
)
from app.security import (
    create_access_token, decrypt_secret, encrypt_secret, generate_totp_secret, hash_password, mask_key, sanitize_text,
    totp_uri, verify_password,
)
from app.services import audit, jobs
from app.services.demo_data import create_demo_data, remove_demo_data
from app.services.totp import OK, consume_totp_code
from app.services.account_cleanup import delete_user_data, release_email_if_unverified
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
    return PROVIDER_KEY_LINKS


@router.post("/api-keys/{provider}/test", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_API_KEY_TEST))])
def test_api_key_endpoint(provider: str, request: Request, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if provider not in PROVIDERS.values():
        raise HTTPException(status_code=400, detail="Neznamy AI provider.")
    api_key = get_decrypted_api_key(db, user.id, provider)
    if not api_key:
        return {"valid": False, "message": "Najprv ulož API kľúč pre tohto providera."}

    def compute() -> dict:
        ok, error = test_api_key(provider, api_key)
        return {"valid": ok, "message": "Kľúč je platný a funkčný." if ok else (error or "Kľúč sa nepodarilo overiť.")}

    return jobs.respond(request, user.id, compute)


@router.put("/email", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def update_email(payload: UpdateEmailRequest, request: Request, background_tasks: BackgroundTasks,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    email = sanitize_text(payload.email, max_length=255).lower() if payload.email else ""
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Zadaj platnú emailovú adresu.")
    existing = db.query(User).filter(User.email == email, User.id != user.id).first()
    if existing is not None:
        if not (is_email_configured() and release_email_if_unverified(db, email, requester_id=user.id)):
            raise HTTPException(status_code=400, detail="Tento email už používa iný účet.")
    changed = user.email != email
    user.email = email
    if changed and is_email_configured():
        user.email_verified = False
    if changed:
        audit.record(db, user.id, "email_changed", request)
    db.commit()
    if changed and user.email_verified is False:
        send_verification_code(db, user, background_tasks)
    return {"success": True, "email": user.email, "email_verified": user.email_verified}


@router.post("/change-password", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def change_password(payload: ChangePasswordRequest, response: Response, request: Request,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Aktuálne heslo nie je správne.")
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    audit.record(db, user.id, "password_changed", request)
    db.commit()
    _reissue_cookie(response, user)
    return {"success": True, "message": "Heslo bolo úspešne zmenené."}


@router.post("/logout-all-devices", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def logout_all_devices(response: Response, request: Request, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> dict:
    user.token_version += 1
    audit.record(db, user.id, "logout_all", request)
    db.commit()
    _reissue_cookie(response, user)
    return {"success": True, "message": "Odhlásené zo všetkých ostatných zariadení."}


@router.put("/api-keys", response_model=ApiKeyStatus, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def upsert_api_key(payload: ApiKeyIn, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> ApiKeyStatus:
    if payload.provider not in PROVIDERS.values():
        raise HTTPException(status_code=400, detail="Neznamy AI provider.")

    if not payload.api_key.strip():
        deleted = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == payload.provider).delete()
        if deleted:
            audit.record(db, user.id, "api_key_deleted", request, payload.provider)
        db.commit()
        label = next(k for k, v in PROVIDERS.items() if v == payload.provider)
        return ApiKeyStatus(provider=payload.provider, label=label, connected=False, masked_preview=None)

    key_value = payload.api_key.strip()
    secret_value = key_value
    if payload.provider == "custom":
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
    audit.record(db, user.id, "api_key_saved", request, payload.provider)
    db.commit()

    label = next(k for k, v in PROVIDERS.items() if v == payload.provider)
    return ApiKeyStatus(provider=payload.provider, label=label, connected=True,
                         masked_preview=mask_key(key_value))


@router.delete("/api-keys/{provider}", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def delete_api_key(provider: str, request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    deleted = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == provider).delete()
    if deleted:
        audit.record(db, user.id, "api_key_deleted", request, provider[:32])
    db.commit()
    return {"success": True}


@router.post("/delete", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def delete_account(payload: DeleteAccountRequest, response: Response, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Aktuálne heslo nie je správne.")
    from app.services import billing
    try:
        billing.cancel_subscriptions(user)
    except billing.BillingError:
        raise HTTPException(status_code=409, detail="Predplatné sa nepodarilo zrušiť. Zruš ho v Nastavenia → Spravovať "
                                                    "predplatné a potom zmaž účet.") from None
    delete_user_data(db, user)
    db.commit()
    from app.config import AUTH_COOKIE_NAME
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"success": True}



@router.post("/2fa/setup", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def totp_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA už máš zapnuté.")
    secret = generate_totp_secret()
    user.totp_pending_secret = encrypt_secret(secret, user.id)
    db.commit()
    return {"secret": secret, "otpauth_uri": totp_uri(secret, user.username)}


@router.post("/2fa/enable", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def totp_enable(payload: TotpCodeRequest, request: Request, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> dict:
    secret = decrypt_secret(user.totp_pending_secret or "", user.id)
    if not secret:
        raise HTTPException(status_code=400, detail="Najprv spusti nastavenie 2FA.")
    if consume_totp_code(db, user, secret, payload.code) != OK:
        raise HTTPException(status_code=400, detail="Nesprávny kód z overovacej aplikácie (2FA).")
    user.totp_secret, user.totp_pending_secret, user.totp_enabled = user.totp_pending_secret, None, True
    audit.record(db, user.id, "twofa_enabled", request)
    db.commit()
    return {"success": True, "totp_enabled": True}


@router.post("/2fa/disable", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def totp_disable(payload: TotpDisableRequest, request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> dict:
    if not user.totp_enabled:
        return {"success": True, "totp_enabled": False}
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Aktuálne heslo nie je správne.")
    secret = decrypt_secret(user.totp_secret or "", user.id)
    if consume_totp_code(db, user, secret, payload.code) != OK:
        raise HTTPException(status_code=400, detail="Nesprávny kód z overovacej aplikácie (2FA).")
    user.totp_secret, user.totp_pending_secret, user.totp_enabled = None, None, False
    audit.record(db, user.id, "twofa_disabled", request)
    db.commit()
    return {"success": True, "totp_enabled": False}


@router.get("/activity")
def account_activity(limit: int = Query(default=50, ge=1, le=200), user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> dict:
    rows = (db.query(AuditEvent).filter(AuditEvent.user_id == user.id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit).all())
    return {"events": [{
        "action": row.action, "ip": row.ip, "device": audit.describe_user_agent(row.user_agent),
        "details": row.details, "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat() if row.created_at else None,
    } for row in rows]}


@router.post("/demo-data", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def load_demo_data(request: Request, lang: str = Query(default="en", max_length=5),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    created = create_demo_data(db, user.id, lang)
    audit.record(db, user.id, "demo_data_loaded", request,
                 f"{created['forecasts']} forecasts, {created['portfolios']} portfolios")
    db.commit()
    return {"created": created["forecasts"], **{k: v for k, v in created.items() if k != "forecasts"}}


@router.delete("/demo-data")
def delete_demo_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    removed = remove_demo_data(db, user.id)
    db.commit()
    return {"removed": removed["forecasts"] + removed["portfolios"], **removed}


DEFAULT_WATCHLIST = ["BTC", "ETH", "SOL"]
MAX_WATCHLIST = 12


def _watchlist(user: User) -> List[str]:
    try:
        coins = json.loads(user.watchlist_json) if user.watchlist_json else DEFAULT_WATCHLIST
    except json.JSONDecodeError:
        coins = DEFAULT_WATCHLIST
    return [c for c in coins if isinstance(c, str) and c in DEFAULT_COIN_IDS]


@router.get("/watchlist")
def get_watchlist(user: User = Depends(get_current_user)) -> dict:
    return {"coins": _watchlist(user), "available": list(DEFAULT_COIN_IDS), "max": MAX_WATCHLIST}


@router.put("/watchlist", dependencies=[Depends(rate_limit_by_user(30, 60))])
def set_watchlist(payload: WatchlistIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    coins = list(dict.fromkeys(c.upper() for c in payload.coins))[:MAX_WATCHLIST]
    if any(c not in DEFAULT_COIN_IDS for c in coins):
        raise HTTPException(status_code=400, detail="Watchlist podporuje len základné mince.")
    user.watchlist_json = json.dumps(coins)
    db.commit()
    return {"coins": coins, "available": list(DEFAULT_COIN_IDS), "max": MAX_WATCHLIST}
