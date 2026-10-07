"""Price alerts: checked by the background job, delivered in the app and by email."""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL, DEFAULT_COIN_IDS
from app.models import PriceAlert, User
from app.services import app_settings, market_data
from app.services.email_service import email_lang, email_shell, is_email_configured, send_email
from app.services.notifications import notify
from app.services.premium import is_premium

logger = logging.getLogger("aca.alerts")

_T = {
    "en": ("Price alert: {coin} is {dir} {target}", "{coin} just went {dir} your target of {target}. Current price: {price}.",
           "above", "below", "Open AI Crypto Analytics"),
    "sk": ("Cenový alarm: {coin} je {dir} {target}", "{coin} sa práve dostal {dir} tvoj cieľ {target}. Aktuálna cena: {price}.",
           "nad", "pod", "Otvoriť AI Crypto Analytics"),
    "cs": ("Cenový alarm: {coin} je {dir} {target}", "{coin} se právě dostal {dir} tvůj cíl {target}. Aktuální cena: {price}.",
           "nad", "pod", "Otevřít AI Crypto Analytics"),
}


def fmt_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.8g}"


def alert_limit(user: User) -> int:
    return app_settings.get("premium_alerts" if is_premium(user) else "free_alerts")


def crossed(alert: PriceAlert, price: float) -> bool:
    return price >= alert.target_price if alert.direction == "above" else price <= alert.target_price


def _email(user: User, alert: PriceAlert, price: float) -> tuple[str, str, str]:
    subject_t, body_t, above, below, cta = _T[email_lang(user.lang)]
    params = {"coin": alert.coin, "dir": above if alert.direction == "above" else below,
              "target": fmt_price(alert.target_price), "price": fmt_price(price)}
    subject, body = subject_t.format(**params), body_t.format(**params)
    link = f"{APP_PUBLIC_URL}/dashboard?utm_source=alert&utm_medium=email"
    html_body = email_shell(lang=user.lang, preheader=subject, inner_html=f"""
        <h1 style="margin:0 0 14px; font-size:19px; color:#0f172a;">{html.escape(subject)}</h1>
        <p style="margin:0 0 18px; font-size:14px; line-height:1.6; color:#334155;">{html.escape(body)}</p>
        <p style="margin:0;"><a href="{link}" style="display:inline-block; background:#0f172a; color:#ffffff;
           padding:11px 18px; border-radius:10px; font-size:14px; font-weight:600; text-decoration:none;">{cta}</a></p>""")
    return subject, f"{body}\n\n{link}", html_body


def check_alerts(db: Session) -> int:
    alerts = db.query(PriceAlert).filter(PriceAlert.active.is_(True)).all()
    coins = sorted({a.coin for a in alerts if a.coin in DEFAULT_COIN_IDS})
    if not coins:
        return 0
    ok, prices, _err = market_data.get_live_prices([DEFAULT_COIN_IDS[c] for c in coins])
    if not ok or not prices:
        return 0
    fired = 0
    emails = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for alert in alerts:
        price = (prices.get(DEFAULT_COIN_IDS.get(alert.coin, "")) or {}).get("usd")
        if not isinstance(price, (int, float)) or not crossed(alert, price):
            continue
        alert.active, alert.triggered_at, alert.triggered_price = False, now, float(price)
        notify(db, alert.user_id, "price_alert", coin=alert.coin, direction=alert.direction,
               target=alert.target_price, price=float(price))
        user = db.get(User, alert.user_id)
        if user is not None and user.email and user.email_verified is not False:
            emails.append((user.email, *_email(user, alert, float(price))))
        fired += 1
    db.commit()
    if is_email_configured():
        for to, subject, text, body in emails:
            send_email(to, subject, text, body)
    return fired
