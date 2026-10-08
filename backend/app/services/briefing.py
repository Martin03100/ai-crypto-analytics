"""Premium morning briefing: a 24h statistical forecast for every coin on the user's watchlist."""

from __future__ import annotations

import html
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL
from app.models import User
from app.services import quant_engine, signals, telegram
from app.services.alerts import fmt_price
from app.services.email_service import email_lang, email_shell, is_email_configured, send_email
from app.services.premium import is_premium

logger = logging.getLogger("aca.briefing")

DEFAULT_WATCHLIST = ["BTC", "ETH", "SOL"]

_T = {
    "en": {"subject": "Your morning crypto briefing", "title": "Good morning! Next 24 hours for your coins",
           "row": "{coin}: {price} → {target} ({change}), 80% range {low} – {high}",
           "cta": "Open your dashboard", "note": "Statistical model on real market data. Not financial advice.",
           "off": "Turn the briefing off in Settings.", "signals": "Market signals"},
    "sk": {"subject": "Tvoj ranný krypto prehľad", "title": "Dobré ráno! Najbližších 24 hodín pre tvoje mince",
           "row": "{coin}: {price} → {target} ({change}), 80 % rozsah {low} – {high}",
           "cta": "Otvoriť dashboard", "note": "Štatistický model na reálnych trhových dátach. Nejde o investičné poradenstvo.",
           "off": "Prehľad vypneš v Nastaveniach.", "signals": "Trhové signály"},
    "cs": {"subject": "Tvůj ranní krypto přehled", "title": "Dobré ráno! Nejbližších 24 hodin pro tvé mince",
           "row": "{coin}: {price} → {target} ({change}), 80% rozsah {low} – {high}",
           "cta": "Otevřít dashboard", "note": "Statistický model na reálných tržních datech. Nejde o investiční poradenství.",
           "off": "Přehled vypneš v Nastavení.", "signals": "Tržní signály"},
    "de": {"subject": "Dein morgendlicher Krypto-Überblick", "title": "Guten Morgen! Die nächsten 24 Stunden für deine Coins",
           "row": "{coin}: {price} → {target} ({change}), 80-%-Spanne {low} – {high}",
           "cta": "Dashboard öffnen", "note": "Statistisches Modell auf echten Marktdaten. Keine Anlageberatung.",
           "off": "Den Überblick kannst du in den Einstellungen abschalten.", "signals": "Marktsignale"},
    "pl": {"subject": "Twój poranny przegląd krypto", "title": "Dzień dobry! Najbliższe 24 godziny dla twoich monet",
           "row": "{coin}: {price} → {target} ({change}), zakres 80% {low} – {high}",
           "cta": "Otwórz dashboard", "note": "Model statystyczny na prawdziwych danych rynkowych. To nie jest porada inwestycyjna.",
           "off": "Przegląd wyłączysz w Ustawieniach.", "signals": "Sygnały rynkowe"},
}


def _watchlist(user: User) -> list[str]:
    try:
        coins = json.loads(user.watchlist_json) if user.watchlist_json else DEFAULT_WATCHLIST
    except json.JSONDecodeError:
        coins = DEFAULT_WATCHLIST
    return [c for c in coins if isinstance(c, str)][:8] or DEFAULT_WATCHLIST


def coin_outlook(coin: str, cache: dict) -> Optional[dict]:
    if coin not in cache:
        ok, data, _err = quant_engine.build_quant_forecast(coin, "24h", "en")
        cache[coin] = None
        if ok and data and data.get("ceny"):
            spot, target = data.get("aktualna_cena"), data["ceny"][-1]
            band = data.get("pasmo") or {}
            lows, highs = band.get("dolne") or [], band.get("horne") or []
            if isinstance(spot, (int, float)) and spot > 0:
                cache[coin] = {"coin": coin, "price": spot, "target": target, "change": (target - spot) / spot * 100,
                               "low": lows[-1] if lows else target, "high": highs[-1] if highs else target}
    return cache[coin]


def render_briefing(user: User, rows: list[dict], market: Optional[list[dict]] = None) -> tuple[str, str, str]:
    lang = email_lang(user.lang)
    t = _T[lang]
    extra = signals.headline(market or [], lang)
    lines = [t["row"].format(coin=r["coin"], price=fmt_price(r["price"]), target=fmt_price(r["target"]),
                             change=f"{r['change']:+.1f}%", low=fmt_price(r["low"]), high=fmt_price(r["high"])) for r in rows]
    link = f"{APP_PUBLIC_URL}/dashboard?utm_source=briefing&utm_medium=email"
    signals_html = (f'<p style="margin:0 0 6px; font-size:13px; font-weight:600; color:#0f172a;">{t["signals"]}</p>'
                    f'<p style="margin:0 0 18px; font-size:13px; line-height:1.6; color:#334155;">'
                    f'{"<br>".join(html.escape(x) for x in extra)}</p>') if extra else ""
    items = "".join(f'<li style="margin:0 0 8px;">{html.escape(line)}</li>' for line in lines)
    body = email_shell(lang=user.lang, preheader=t["title"], inner_html=f"""
        <h1 style="margin:0 0 14px; font-size:19px; color:#0f172a;">{t["title"]}</h1>
        <ul style="margin:0 0 18px; padding-left:18px; font-size:14px; line-height:1.5; color:#334155;">{items}</ul>
        {signals_html}
        <p style="margin:0 0 16px;"><a href="{link}" style="display:inline-block; background:#0f172a; color:#ffffff;
           padding:11px 18px; border-radius:10px; font-size:14px; font-weight:600; text-decoration:none;">{t["cta"]}</a></p>
        <p style="margin:0; font-size:12px; color:#94a3b8;">{t["note"]} {t["off"]}</p>""")
    text_signals = [f"{t['signals']}:", *extra] if extra else []
    return t["subject"], "\n".join([t["title"], *lines, *text_signals, link, t["note"]]), body


def send_morning_briefings(db: Session) -> int:
    if not is_email_configured():
        return 0
    cache: dict = {}
    market: Optional[list] = None
    sent = 0
    for user in db.query(User).filter(User.briefing_opt_in.is_(True), User.email.isnot(None),
                                      User.email_verified.isnot(False), User.disabled.isnot(True)).all():
        if not is_premium(user):
            continue
        rows = [r for r in (coin_outlook(c, cache) for c in _watchlist(user)) if r]
        if not rows:
            continue
        if market is None:
            try:
                market = signals.collect("BTC")["items"]
            except Exception:  # noqa: BLE001
                market = []
        subject, text, body = render_briefing(user, rows, market)
        delivered = send_email(user.email, subject, text, body)
        if user.telegram_chat_id:
            delivered = telegram.send(user.telegram_chat_id, f"☀️ {text}") or delivered
        sent += bool(delivered)
    logger.info("Ranny prehlad odoslany %s pouzivatelom.", sent)
    return sent
