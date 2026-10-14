"""Admin "system check": which services are configured and whether the background jobs run.

It answers questions an operator cannot see from the app itself: where the database lives, whether errors are
reported, and whether the scheduler is alive. Values that could help an attacker (connection strings, keys) are
never returned, only the host's provider and yes/no states.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app import config, monitoring
from app.models import JobRun

# Hostname fragment -> provider shown in the admin panel.
_PROVIDERS = (("render.com", "Render"), ("neon.tech", "Neon"), ("supabase", "Supabase"), ("aiven", "Aiven"),
              ("railway", "Railway"), ("amazonaws.com", "Amazon RDS"), ("azure", "Azure"))
# Jobs that should have run within this time while the scheduler works (price alerts run every 5 minutes).
_SCHEDULER_STALE = timedelta(minutes=30)


def database_info(url: str = config.DATABASE_URL) -> dict:
    if url.startswith("sqlite"):
        return {"engine": "sqlite", "provider": "local file", "render": False}
    host = (urlparse(url).hostname or "").lower()
    provider = next((name for fragment, name in _PROVIDERS if fragment in host), "other")
    return {"engine": "postgresql" if url.startswith("postgres") else url.split(":", 1)[0],
            "provider": provider, "render": provider == "Render"}


def _last_runs(db: Session) -> dict[str, str]:
    return {row.name: row.last_run_at.isoformat() + "Z" for row in db.query(JobRun).all()}


def report(db: Session) -> dict:
    from app.services.captcha import is_captcha_enabled
    from app.services.email_service import is_email_configured
    from app.services.telegram import enabled as telegram_enabled

    runs = _last_runs(db)
    alerts_run = runs.get("price_alerts")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    scheduler_ok = bool(alerts_run) and now - datetime.fromisoformat(alerts_run[:-1]) < _SCHEDULER_STALE
    return {
        "database": database_info(),
        "checks": {
            "email": is_email_configured(),
            "captcha": is_captcha_enabled(),
            "sentry_backend": monitoring.is_enabled(),
            "proxy_signature": bool(config.PROXY_SIGNATURE_SECRET),
            "trusted_proxy_hops": config.TRUSTED_PROXY_HOPS > 0,
            "scheduler": config.SCHEDULER_ENABLED and scheduler_ok,
            "telegram": telegram_enabled(),
            "google_login": bool(config.GOOGLE_CLIENT_ID),
        },
        "job_runs": runs,
        "environment": config.APP_ENV,
    }
