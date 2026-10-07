"""Admin panel API: overview, users, Premium, waitlist and app settings. Admins only (see services.roles)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.deps import get_admin_user, get_db
from app.models import ForecastEvaluation, ForecastHistory, PriceTip, User, WaitlistEntry
from app.schemas import MAX_DB_ID
from app.config import RATE_LIMIT_ACCOUNT_SENSITIVE
from app.rate_limit import rate_limit_by_user
from app.services import app_settings, audit, billing, stripe_connect
from app.services.premium import extend_premium, is_premium
from app.services.roles import is_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_admin_user)])

_PAGE_SIZE = 25


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    now = _now()
    week = now - timedelta(days=7)
    real_forecast = ForecastHistory.model_used != "mock"
    return {
        "users": db.query(User).count(),
        "users_7d": db.query(User).filter(User.created_at >= week).count(),
        "premium": db.query(User).filter(User.premium_until > now).count(),
        "paying": db.query(User).filter(User.premium_until > now, User.stripe_customer_id.isnot(None)).count(),
        "disabled": db.query(User).filter(User.disabled.is_(True)).count(),
        "digest_subscribers": db.query(User).filter(User.digest_opt_in.is_(True)).count(),
        "referred": db.query(User).filter(User.referral_rewarded.is_(True)).count(),
        "waitlist": db.query(WaitlistEntry).count(),
        "waitlist_by_source": {src or "direct": n for src, n in db.query(WaitlistEntry.source, func.count())
                               .group_by(WaitlistEntry.source).order_by(func.count().desc()).limit(8).all()},
        "forecasts": db.query(ForecastHistory).filter(real_forecast).count(),
        "forecasts_7d": db.query(ForecastHistory).filter(real_forecast, ForecastHistory.created_at >= week).count(),
        "evaluated": db.query(ForecastEvaluation).filter(ForecastEvaluation.is_demo.isnot(True)).count(),
        "duels": db.query(PriceTip).filter(PriceTip.outcome.isnot(None), PriceTip.is_demo.isnot(True)).count(),
        "billing_enabled": billing.billing_enabled(),
    }


def _user_row(u: User) -> dict:
    return {"id": u.id, "username": u.username, "email": u.email, "created_at": _iso(u.created_at),
            "email_verified": u.email_verified, "premium": is_premium(u), "premium_until": _iso(u.premium_until),
            "paying": bool(u.stripe_customer_id), "nickname": u.nickname, "disabled": bool(u.disabled),
            "admin": is_admin(u), "totp": bool(u.totp_enabled)}


@router.get("/users")
def list_users(q: str = Query(default="", max_length=64), page: int = Query(default=1, ge=1, le=10_000),
               db: Session = Depends(get_db)) -> dict:
    query = db.query(User)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.filter(or_(func.lower(User.username).like(like), func.lower(User.email).like(like),
                                 func.lower(User.nickname).like(like)))
    total = query.count()
    rows = query.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * _PAGE_SIZE).limit(_PAGE_SIZE).all()
    return {"items": [_user_row(u) for u in rows], "total": total, "page": page, "page_size": _PAGE_SIZE}


class UserChange(BaseModel):
    add_premium_days: Optional[int] = Field(default=None, ge=1, le=3650)
    remove_premium: Optional[bool] = None
    disabled: Optional[bool] = None
    clear_nickname: Optional[bool] = None


@router.patch("/users/{user_id}")
def change_user(payload: UserChange, request: Request, user_id: int = Path(ge=1, le=MAX_DB_ID),
                admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Používateľ nebol nájdený.")
    done = []
    if payload.add_premium_days:
        extend_premium(user, payload.add_premium_days)
        done.append(f"premium+{payload.add_premium_days}d")
    if payload.remove_premium:
        user.premium_until = None
        done.append("premium-removed")
    if payload.disabled is not None:
        if user.id == admin.id or is_admin(user):
            raise HTTPException(status_code=400, detail="Administrátora nie je možné zablokovať.")
        user.disabled = payload.disabled or None
        if payload.disabled:
            user.token_version += 1   # signs the user out everywhere
        done.append("disabled" if payload.disabled else "enabled")
    if payload.clear_nickname:
        user.nickname = None
        done.append("nickname-cleared")
    if done:
        audit.record(db, admin.id, "admin_user_changed", request, f"user {user.id}: {', '.join(done)}")
    db.commit()
    return _user_row(user)


@router.get("/waitlist")
def waitlist(db: Session = Depends(get_db)) -> dict:
    rows = db.query(WaitlistEntry).order_by(WaitlistEntry.created_at.desc()).limit(500).all()
    return {"items": [{"email": r.email, "lang": r.lang, "source": r.source, "created_at": _iso(r.created_at)} for r in rows],
            "total": db.query(WaitlistEntry).count()}


@router.get("/waitlist.csv")
def waitlist_csv(db: Session = Depends(get_db)) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "lang", "source", "created_at"])
    for r in db.query(WaitlistEntry).order_by(WaitlistEntry.created_at).all():
        writer.writerow([r.email, r.lang, r.source or "", _iso(r.created_at)])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="waitlist.csv"'})


@router.get("/settings")
def get_settings() -> dict:
    return {"values": app_settings.all_settings(),
            "schema": {k: {"kind": kind, "limits": list(limits)} for k, (_d, kind, limits) in app_settings.SCHEMA.items()}}


class SettingsChange(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


@router.put("/settings")
def put_settings(payload: SettingsChange, request: Request, admin: User = Depends(get_admin_user),
                 db: Session = Depends(get_db)) -> dict:
    if not payload.values:
        return {"values": app_settings.all_settings()}
    try:
        values = app_settings.update(db, payload.values)
    except app_settings.SettingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    audit.record(db, admin.id, "admin_settings_changed", request, ", ".join(sorted(payload.values))[:255])
    db.commit()
    return {"values": values}


# ---------- payments (Stripe connected from the browser) ----------

def _payments_status() -> dict:
    creds = billing.credentials()
    s = app_settings.all_settings()
    out: dict[str, Any] = {"connected": bool(creds.get("secret_key")), "source": creds.get("source"),
                           "webhook_url": stripe_connect.webhook_url(), "account": None, "account_error": None,
                           "currency": creds.get("currency", "eur"), "monthly_cents": creds.get("monthly_cents"),
                           "yearly_cents": creds.get("yearly_cents"), "yearly": bool(creds.get("price_yearly")),
                           "key_hint": stripe_connect.key_hint(creds["secret_key"]) if creds.get("secret_key") else None}
    if creds.get("secret_key"):
        try:
            out["account"] = stripe_connect.account_status(creds["secret_key"])
        except stripe_connect.StripeSetupError as exc:
            out["account_error"] = str(exc)
    account = out["account"] or {}
    out["checklist"] = {
        "seller": bool(s["operator_name"] and s["operator_address"]),
        "stripe": out["connected"],
        "payouts": bool(account.get("charges_enabled") and account.get("payouts_enabled")),
        "live": account.get("mode") == "live",
        "premium_mode": bool(s["premium_mode"]),
    }
    out["selling"] = billing.checkout_ready()
    return out


@router.get("/payments")
def payments_status() -> dict:
    return _payments_status()


class PaymentsConnect(BaseModel):
    secret_key: str = Field(default="", max_length=255)
    currency: str = Field(default="eur", pattern="^(eur|czk|usd)$")
    monthly_cents: int = Field(ge=50, le=100_000_00)
    yearly_cents: Optional[int] = Field(default=None, ge=50, le=1_000_000_00)


@router.put("/payments", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def payments_connect(payload: PaymentsConnect, request: Request, admin: User = Depends(get_admin_user),
                     db: Session = Depends(get_db)) -> dict:
    if billing.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=409, detail="Stripe je nastavený v premenných prostredia na serveri.")
    try:
        stripe_connect.connect(db, payload.secret_key, payload.monthly_cents, payload.yearly_cents, payload.currency)
    except stripe_connect.StripeSetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    audit.record(db, admin.id, "admin_payments_connected", request, payload.currency)
    db.commit()
    return _payments_status()


@router.delete("/payments")
def payments_disconnect(request: Request, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    stripe_connect.disconnect(db)
    audit.record(db, admin.id, "admin_payments_disconnected", request, "")
    db.commit()
    return _payments_status()



# ---------- backup ----------

@router.get("/backup", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_ACCOUNT_SENSITIVE))])
def download_backup(request: Request, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> Response:
    """Every table as JSON, gzipped. Secrets stay as stored (hashed or encrypted), so keep the file private."""
    import gzip
    import json as _json

    from app.database import Base

    data = {"created_at": _now().isoformat(), "format": 1, "tables": {}}
    for table in Base.metadata.sorted_tables:
        rows = db.execute(table.select()).mappings().all()
        data["tables"][table.name] = [dict(r) for r in rows]
    audit.record(db, admin.id, "admin_backup_downloaded", request, f"{len(data['tables'])} tables")
    db.commit()
    body = gzip.compress(_json.dumps(data, default=str, ensure_ascii=False).encode("utf-8"))
    name = f"ai-crypto-analytics-backup-{_now():%Y-%m-%d}.json.gz"
    return Response(body, media_type="application/gzip", headers={"Content-Disposition": f'attachment; filename="{name}"'})
