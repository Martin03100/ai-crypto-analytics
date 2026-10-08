"""Weekly "AI vs reality" email for users who opted in."""

from __future__ import annotations

import hashlib
import hmac
import html
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import APP_PUBLIC_URL, JWT_SECRET_KEY, QUANT_LABEL
from app.models import ForecastEvaluation, PriceTip, User
from app.services import app_settings
from app.services.email_service import email_lang, email_shell, is_email_configured, send_email

logger = logging.getLogger("aca.digest")

_MIN_FOR_BEST = 3

_T = {
    "en": {
        "subject": "This week: which AI called crypto best?",
        "title": "AI vs reality — your weekly recap",
        "global": "Across all users, {n} forecasts were checked this week. The direction was right {hit}% of the time.",
        "best": "Best model this week: {model} ({hit}% direction hit, {n} forecasts).",
        "duels": "People vs AI: humans won {w} of {t} price-tip duels.",
        "you": "Your week: {n} of your forecasts were checked, {hits} got the direction right.",
        "you_duels": "Your duels: {w} won, {l} lost.",
        "cta": "See the full track record",
        "unsub": "Unsubscribe from the weekly recap",
        "note": "Not financial advice.",
    },
    "sk": {
        "subject": "Tento týždeň: ktorá AI predpovedala krypto najlepšie?",
        "title": "AI vs realita — tvoj týždenný prehľad",
        "global": "U všetkých používateľov sa tento týždeň overilo {n} predikcií. Smer bol správny v {hit} % prípadov.",
        "best": "Najlepší model týždňa: {model} ({hit} % trafený smer, {n} predikcií).",
        "duels": "Ľudia vs AI: ľudia vyhrali {w} z {t} duelov v tipovaní ceny.",
        "you": "Tvoj týždeň: overilo sa {n} tvojich predikcií, {hits} trafilo smer.",
        "you_duels": "Tvoje duely: {w} výhry, {l} prehry.",
        "cta": "Pozri celú úspešnosť AI",
        "unsub": "Odhlásiť týždenný prehľad",
        "note": "Nejde o investičné poradenstvo.",
    },
    "cs": {
        "subject": "Tento týden: která AI předpověděla krypto nejlépe?",
        "title": "AI vs realita — tvůj týdenní přehled",
        "global": "U všech uživatelů se tento týden ověřilo {n} predikcí. Směr byl správný v {hit} % případů.",
        "best": "Nejlepší model týdne: {model} ({hit} % trefený směr, {n} predikcí).",
        "duels": "Lidé vs AI: lidé vyhráli {w} z {t} duelů v tipování ceny.",
        "you": "Tvůj týden: ověřilo se {n} tvých predikcí, {hits} trefilo směr.",
        "you_duels": "Tvé duely: {w} výhry, {l} prohry.",
        "cta": "Podívej se na celou úspěšnost AI",
        "unsub": "Odhlásit týdenní přehled",
        "note": "Nejde o investiční poradenství.",
    },
    "de": {
        "subject": "Diese Woche: Welche KI hat Krypto am besten vorhergesagt?",
        "title": "KI vs. Realität — dein Wochenrückblick",
        "global": "Bei allen Nutzern wurden diese Woche {n} Prognosen überprüft. Die Richtung stimmte in {hit} % der Fälle.",
        "best": "Bestes Modell der Woche: {model} ({hit} % Richtung getroffen, {n} Prognosen).",
        "duels": "Menschen vs. KI: Menschen haben {w} von {t} Preistipp-Duellen gewonnen.",
        "you": "Deine Woche: {n} deiner Prognosen wurden überprüft, {hits} lagen bei der Richtung richtig.",
        "you_duels": "Deine Duelle: {w} gewonnen, {l} verloren.",
        "cta": "Sieh dir die ganze Trefferquote der KI an",
        "unsub": "Wochenrückblick abbestellen",
        "note": "Keine Anlageberatung.",
    },
    "pl": {
        "subject": "W tym tygodniu: które AI najlepiej przewidziało krypto?",
        "title": "AI kontra rzeczywistość — twoje tygodniowe podsumowanie",
        "global": "U wszystkich użytkowników sprawdzono w tym tygodniu {n} prognoz. Kierunek był trafny w {hit}% przypadków.",
        "best": "Najlepszy model tygodnia: {model} ({hit}% trafionego kierunku, {n} prognoz).",
        "duels": "Ludzie kontra AI: ludzie wygrali {w} z {t} pojedynków w typowaniu ceny.",
        "you": "Twój tydzień: sprawdzono {n} twoich prognoz, {hits} trafiło kierunek.",
        "you_duels": "Twoje pojedynki: {w} wygrane, {l} przegrane.",
        "cta": "Zobacz pełną skuteczność AI",
        "unsub": "Wypisz się z tygodniowego podsumowania",
        "note": "To nie jest porada inwestycyjna.",
    },
}


def unsubscribe_token(user_id: int) -> str:
    return hmac.new(JWT_SECRET_KEY.encode(), f"digest-unsubscribe:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def check_unsubscribe_token(user_id: int, token: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(user_id), token or "")


def _week_stats(db: Session, since: datetime) -> dict:
    real = (ForecastEvaluation.is_demo.isnot(True)) & (ForecastEvaluation.evaluated_at >= since)
    hit = func.sum(case((ForecastEvaluation.direction_correct == True, 1), else_=0))  # noqa: E712
    total, hits = db.query(func.count(), hit).filter(real).one()
    best = None
    rows = db.query(ForecastEvaluation.provider, func.count(), hit).filter(real).group_by(ForecastEvaluation.provider).all()
    ranked = sorted(((p, n, (h or 0) / n) for p, n, h in rows if n >= _MIN_FOR_BEST), key=lambda r: (r[2], r[1]), reverse=True)
    if ranked:
        model = "Free statistical model" if ranked[0][0] == QUANT_LABEL else ranked[0][0]
        best = {"model": model, "n": ranked[0][1], "hit": round(ranked[0][2] * 100)}
    tips = dict(db.query(PriceTip.outcome, func.count()).filter(
        PriceTip.outcome.isnot(None), PriceTip.is_demo.isnot(True), PriceTip.created_at >= since).group_by(PriceTip.outcome).all())
    return {"total": total or 0, "hit": round((hits or 0) / total * 100) if total else 0, "best": best,
            "tips_won": tips.get("win", 0), "tips_total": sum(tips.values())}


def _user_stats(db: Session, user_id: int, since: datetime) -> dict:
    mine = (ForecastEvaluation.user_id == user_id) & (ForecastEvaluation.is_demo.isnot(True)) & (ForecastEvaluation.evaluated_at >= since)
    n, hits = db.query(func.count(), func.sum(case((ForecastEvaluation.direction_correct == True, 1), else_=0))).filter(mine).one()  # noqa: E712
    tips = dict(db.query(PriceTip.outcome, func.count()).filter(
        PriceTip.user_id == user_id, PriceTip.outcome.isnot(None), PriceTip.created_at >= since).group_by(PriceTip.outcome).all())
    return {"n": n or 0, "hits": hits or 0, "won": tips.get("win", 0), "lost": tips.get("loss", 0)}


def render_digest(user: User, week: dict, mine: dict) -> Optional[tuple[str, str, str]]:
    if not week["total"] and not mine["n"] and not (mine["won"] + mine["lost"]):
        return None
    lang = email_lang(user.lang)
    t = _T[lang]
    lines = []
    if week["total"]:
        lines.append(t["global"].format(n=week["total"], hit=week["hit"]))
    if week["best"]:
        lines.append(t["best"].format(**week["best"]))
    if week["tips_total"]:
        lines.append(t["duels"].format(w=week["tips_won"], t=week["tips_total"]))
    if mine["n"]:
        lines.append(t["you"].format(n=mine["n"], hits=mine["hits"]))
    if mine["won"] + mine["lost"]:
        lines.append(t["you_duels"].format(w=mine["won"], l=mine["lost"]))
    link = f"{APP_PUBLIC_URL}/track-record?utm_source=digest&utm_medium=email&utm_campaign=weekly"
    unsub = f"{APP_PUBLIC_URL}/unsubscribe?u={user.id}&t={unsubscribe_token(user.id)}"
    text = "\n\n".join([t["title"], *lines, f"{t['cta']}: {link}", t["note"], f"{t['unsub']}: {unsub}"])
    body = "".join(f'<p style="margin:0 0 12px; font-size:14px; line-height:1.6; color:#334155;">{html.escape(line)}</p>'
                   for line in lines)
    html_body = email_shell(lang=lang, preheader=t["subject"], footer_extra=f' <a href="{unsub}" style="color:#94a3b8;">{t["unsub"]}</a>',
                            inner_html=f"""
        <h1 style="margin:0 0 16px; font-size:19px; color:#0f172a;">{t["title"]}</h1>
        {body}
        <p style="margin:20px 0;"><a href="{link}" style="display:inline-block; background:#0f172a; color:#ffffff;
           padding:11px 18px; border-radius:10px; font-size:14px; font-weight:600; text-decoration:none;">{t["cta"]}</a></p>
        <p style="margin:0; font-size:12px; color:#94a3b8;">{t["note"]}</p>""")
    return t["subject"], text, html_body


def send_weekly_digests(db: Session, now: Optional[datetime] = None) -> int:
    if not is_email_configured() or not app_settings.get("digest_enabled"):
        return 0
    since = (now or datetime.now(timezone.utc)).replace(tzinfo=None) - timedelta(days=7)
    week = _week_stats(db, since)
    sent = 0
    for user in db.query(User).filter(User.digest_opt_in.is_(True), User.email.isnot(None),
                                      User.email_verified.isnot(False), User.disabled.isnot(True)).all():
        rendered = render_digest(user, week, _user_stats(db, user.id, since))
        if rendered and send_email(user.email, *rendered):
            sent += 1
    logger.info("Tyzdenny prehlad odoslany %s pouzivatelom.", sent)
    return sent
