"""Telegram delivery for Premium users: link the account with /start <code>, then alerts and briefings arrive there."""

from __future__ import annotations

import logging
import secrets
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME
from app.models import AppSetting, User

logger = logging.getLogger("aca.telegram")

_OFFSET_KEY = "telegram_update_offset"
_REPLIES = {
    "linked": "✅ Connected to AI Crypto Analytics. Your alerts and morning briefing will arrive here.",
    "unknown": "This link has expired. Open Settings in AI Crypto Analytics and press \"Connect Telegram\" again.",
    "stopped": "Telegram notifications are off. You can connect again from Settings.",
}


def enabled() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME)


def _api(method: str, payload: dict) -> Optional[dict]:
    try:
        res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}", json=payload, timeout=15)
        body = res.json()
        return body if body.get("ok") else None
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Telegram %s zlyhal: %s", method, type(exc).__name__)   # the message would contain the bot token
        return None


def send(chat_id: str, text: str) -> bool:
    if not enabled() or not chat_id:
        return False
    return _api("sendMessage", {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True}) is not None


def link_url(db: Session, user: User) -> str:
    user.telegram_link_code = secrets.token_hex(6)
    db.commit()
    return f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={user.telegram_link_code}"


def handle_message(db: Session, chat_id: str, text: str) -> str:
    parts = (text or "").strip().split()
    if parts[:1] == ["/stop"]:
        for user in db.query(User).filter(User.telegram_chat_id == chat_id).all():
            user.telegram_chat_id = None
        db.commit()
        return "stopped"
    code = parts[1] if len(parts) == 2 and parts[0] == "/start" else ""
    user = db.query(User).filter(User.telegram_link_code == code).first() if code else None
    if user is None:
        return "unknown"
    user.telegram_chat_id, user.telegram_link_code = chat_id, None
    db.commit()
    return "linked"


def poll_updates(db: Session) -> int:
    """Called by the background job; long polling needs no public webhook URL."""
    if not enabled():
        return 0
    row = db.get(AppSetting, _OFFSET_KEY)
    offset = int(row.value_json) if row and row.value_json.isdigit() else 0
    body = _api("getUpdates", {"offset": offset, "timeout": 0, "allowed_updates": ["message"]})
    handled = 0
    for update in (body or {}).get("result", []):
        offset = max(offset, int(update.get("update_id", 0)) + 1)
        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id") or "")
        if chat_id and isinstance(message.get("text"), str):
            send(chat_id, _REPLIES[handle_message(db, chat_id, message["text"])])
            handled += 1
    if row is None:
        db.add(AppSetting(key=_OFFSET_KEY, value_json=str(offset)))
    else:
        row.value_json = str(offset)
    db.commit()
    return handled
