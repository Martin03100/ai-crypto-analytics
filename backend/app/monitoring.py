"""Optional error monitoring with Sentry. Disabled unless SENTRY_DSN is set."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

from app.config import APP_ENV

logger = logging.getLogger("aca.monitoring")

SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
_enabled = False

# Never send secrets that might appear in error messages (API keys, bearer tokens, codes).
_SECRET_PATTERNS = [
    re.compile(r"(sk-|pplx-|AIza|xai-|gsk_)[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)((api[_-]?key|token|password|secret)[\"']?\s*[:=]\s*[\"']?)[^\s\"',&]+"),
]
_SENSITIVE_HEADERS = {"cookie", "authorization", "x-csrf-token", "set-cookie"}


def scrub(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "[redacted]", text)
    return text


def _before_send(event: Dict[str, Any], _hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    for name in list(headers):
        if name.lower() in _SENSITIVE_HEADERS:
            headers[name] = "[redacted]"
    request.pop("data", None)  # request bodies may contain passwords or API keys
    request.pop("cookies", None)
    for exc in (event.get("exception") or {}).get("values") or []:
        if isinstance(exc.get("value"), str):
            exc["value"] = scrub(exc["value"])
    if isinstance(event.get("message"), str):
        event["message"] = scrub(event["message"])
    return event


def init_monitoring() -> bool:
    global _enabled
    if not SENTRY_DSN:
        return False
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=SENTRY_DSN, environment=APP_ENV, send_default_pii=False, before_send=_before_send,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0") or 0),
        )
        _enabled = True
        logger.info("Sentry monitoring zapnuty (%s).", APP_ENV)
    except Exception as exc:  # noqa: BLE001 - monitoring must never break the app
        logger.warning("Sentry sa nepodarilo zapnut: %s", exc)
    return _enabled


def capture_exception(exc: BaseException) -> None:
    if not _enabled:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001
        pass
