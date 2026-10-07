"""Alerts: price levels, 24h moves, RSI and the Fear & Greed index. Delivered in the app, by email and on Telegram."""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL, DEFAULT_COIN_IDS
from app.models import PriceAlert, User
from app.services import app_settings, market_data, telegram
from app.services.email_service import email_lang, email_shell, is_email_configured, send_email
from app.services.notifications import notify
from app.services.premium import is_premium

logger = logging.getLogger("aca.alerts")

KINDS = ("price", "move", "rsi", "fear_greed")
PREMIUM_KINDS = ("fear_greed",)
LIMITS = {"price": (0, 1e9), "move": (0.5, 100), "rsi": (1, 99), "fear_greed": (1, 99)}

_SUBJECT = {
    "en": {"price": "{coin} is {dir} {target}", "move": "{coin} moved {value} in 24 hours",
           "rsi": "{coin} RSI is {value}", "fear_greed": "Fear & Greed index is {value}"},
    "sk": {"price": "{coin} je {dir} {target}", "move": "{coin} sa za 24 hodín pohol o {value}",
           "rsi": "RSI {coin} je {value}", "fear_greed": "Index Fear & Greed je {value}"},
    "cs": {"price": "{coin} je {dir} {target}", "move": "{coin} se za 24 hodin pohnul o {value}",
           "rsi": "RSI {coin} je {value}", "fear_greed": "Index Fear & Greed je {value}"},
}
_WORDS = {"en": ("above", "below", "Alert", "Open AI Crypto Analytics"),
          "sk": ("nad", "pod", "Alarm", "Otvoriť AI Crypto Analytics"),
          "cs": ("nad", "pod", "Alarm", "Otevřít AI Crypto Analytics")}


def fmt_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.8g}"


def alert_limit(user: User) -> int:
    return app_settings.get("premium_alerts" if is_premium(user) else "free_alerts")


def crossed(alert: PriceAlert, value: float) -> bool:
    if alert.kind == "move" and alert.direction == "above":
        return value >= alert.target_price
    if alert.kind == "move":
        return value <= -alert.target_price
    return value >= alert.target_price if alert.direction == "above" else value <= alert.target_price


def describe(alert: PriceAlert, value: float, lang: Optional[str]) -> str:
    lang = email_lang(lang)
    above, below, label, _cta = _WORDS[lang]
    params = {"coin": alert.coin, "dir": above if alert.direction == "above" else below,
              "target": fmt_price(alert.target_price),
              "value": f"{value:+.1f}%" if alert.kind == "move" else f"{value:.0f}" if alert.kind != "price" else fmt_price(value)}
    return f"{label}: " + _SUBJECT[lang][alert.kind].format(**params)


def _email(user: User, text: str) -> tuple[str, str, str]:
    cta = _WORDS[email_lang(user.lang)][3]
    link = f"{APP_PUBLIC_URL}/dashboard?utm_source=alert&utm_medium=email"
    body = email_shell(lang=user.lang, preheader=text, inner_html=f"""
        <h1 style="margin:0 0 18px; font-size:19px; color:#0f172a;">{html.escape(text)}</h1>
        <p style="margin:0;"><a href="{link}" style="display:inline-block; background:#0f172a; color:#ffffff;
           padding:11px 18px; border-radius:10px; font-size:14px; font-weight:600; text-decoration:none;">{cta}</a></p>""")
    return text, f"{text}\n\n{link}", body


def _current_values(alerts: list[PriceAlert]) -> Dict[tuple, float]:
    from app.services.insights import daily_rsi
    values: Dict[tuple, float] = {}
    coins = sorted({a.coin for a in alerts if a.kind in ("price", "move") and a.coin in DEFAULT_COIN_IDS})
    if coins:
        ok, prices, _err = market_data.get_live_prices([DEFAULT_COIN_IDS[c] for c in coins])
        for coin in coins if ok and prices else []:
            quote = prices.get(DEFAULT_COIN_IDS[coin]) or {}
            if isinstance(quote.get("usd"), (int, float)):
                values[("price", coin)] = float(quote["usd"])
            if isinstance(quote.get("usd_24h_change"), (int, float)):
                values[("move", coin)] = float(quote["usd_24h_change"])
    for coin in sorted({a.coin for a in alerts if a.kind == "rsi" and a.coin in DEFAULT_COIN_IDS}):
        ok, history, _err = market_data.get_market_history(DEFAULT_COIN_IDS[coin], 30)
        rsi = daily_rsi(history.get("prices", [])) if ok else None
        if rsi is not None:
            values[("rsi", coin)] = rsi
    if any(a.kind == "fear_greed" for a in alerts):
        ok, data, _err = market_data.get_fear_greed_index()
        if ok and data:
            values[("fear_greed", "ALL")] = float(data["value"])
    return values


def check_alerts(db: Session) -> int:
    alerts = db.query(PriceAlert).filter(PriceAlert.active.is_(True)).all()
    if not alerts:
        return 0
    values = _current_values(alerts)
    deliveries = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for alert in alerts:
        value = values.get((alert.kind, alert.coin))
        if value is None or not crossed(alert, value):
            continue
        user = db.get(User, alert.user_id)
        if user is None:
            continue
        if alert.kind in PREMIUM_KINDS and not is_premium(user):
            continue                      # Premium ended: the alert waits until it is renewed
        alert.active, alert.triggered_at, alert.triggered_price = False, now, value
        notify(db, alert.user_id, "price_alert", alert_kind=alert.kind, coin=alert.coin, direction=alert.direction,
               target=alert.target_price, price=value)
        deliveries.append((user, describe(alert, value, user.lang)))
    db.commit()
    for user, text in deliveries:
        if user.email and user.email_verified is not False and is_email_configured():
            send_email(user.email, *_email(user, text))
        if user.telegram_chat_id and is_premium(user):
            telegram.send(user.telegram_chat_id, f"🔔 {text}")
    return len(deliveries)
