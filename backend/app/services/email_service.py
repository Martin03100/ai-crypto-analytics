"""Email service."""

from __future__ import annotations

import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from app.config import BREVO_API_KEY, EMAIL_FROM, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger("aca.email")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def is_smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def is_email_configured() -> bool:
    return bool(BREVO_API_KEY) or is_smtp_configured()


def _send_via_brevo(to_address: str, subject: str, text_body: str, html_body: str | None) -> bool:
    try:
        resp = requests.post(
            BREVO_API_URL,
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"},
            json={
                "sender": {"email": EMAIL_FROM},
                "to": [{"email": to_address}],
                "subject": subject,
                "textContent": text_body,
                "htmlContent": html_body or text_body,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Odoslanie emailu cez Brevo API na %s zlyhalo: %s", to_address, exc)
        return False


def _send_via_smtp(to_address: str, subject: str, text_body: str, html_body: str | None) -> bool:
    try:
        if html_body:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        else:
            msg = MIMEText(text_body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_address
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_address], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Odoslanie emailu cez SMTP na %s zlyhalo: %s", to_address, exc)
        return False


def send_email(to_address: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    if BREVO_API_KEY:
        return _send_via_brevo(to_address, subject, text_body, html_body)
    if is_smtp_configured():
        return _send_via_smtp(to_address, subject, text_body, html_body)
    logger.info("Email nie je nakonfigurovany (BREVO_API_KEY ani SMTP_*) — email pre %s sa iba loguje:\n%s", to_address, text_body)
    return False


_FOOTER = {
    "en": "AI Crypto Analytics — automated message, please do not reply.",
    "sk": "AI Crypto Analytics — automatická správa, neodpovedaj na ňu.",
    "cs": "AI Crypto Analytics — automatická zpráva, neodpovídej na ni.",
}

_T = {
    "en": {
        "hello": "Hi {u},",
        "verify_subject": "Verify your email — AI Crypto Analytics",
        "verify_title": "Verify your email",
        "verify_text": "Welcome to AI Crypto Analytics! To finish signing up, enter this code in the app:",
        "verify_note": "The code is valid for {m} minutes. If you didn't sign up, ignore this email.",
        "reset_subject": "Password reset code — AI Crypto Analytics",
        "reset_title": "Reset your password",
        "reset_text": "We received a request to reset the password for your account. Enter this code in the app:",
        "reset_note": "The code is valid for {m} minutes and can be used once. If you didn't ask for it, ignore this email; your account is safe.",
        "lock_subject": "Warning: sign-in attempts — AI Crypto Analytics",
        "lock_title": "Failed sign-in attempts",
        "lock_text": "Your account was locked for {m} minutes after several failed sign-in attempts.",
        "lock_note": "If this wasn't you, change your password and turn on two-factor authentication (2FA) in Settings.",
        "login_subject": "New sign-in to your account — AI Crypto Analytics",
        "login_title": "New sign-in to your account",
        "login_text": "Someone signed in to your account from a new device:",
        "login_when": "Time", "login_device": "Device", "login_ip": "IP address",
        "login_note": "If this was you, there is nothing to do. If not, change your password now, choose \"Log out of all other devices\" in Settings and turn on 2FA.",
    },
    "sk": {
        "hello": "Ahoj {u},",
        "verify_subject": "Over si e-mail — AI Crypto Analytics",
        "verify_title": "Over si e-mail",
        "verify_text": "Vitaj v AI Crypto Analytics! Na dokončenie registrácie zadaj v aplikácii tento kód:",
        "verify_note": "Kód platí {m} minút. Ak si sa neregistroval(a), tento e-mail ignoruj.",
        "reset_subject": "Kód na obnovenie hesla — AI Crypto Analytics",
        "reset_title": "Obnovenie hesla",
        "reset_text": "Dostali sme žiadosť o obnovenie hesla k tvojmu účtu. Zadaj tento kód v aplikácii:",
        "reset_note": "Kód platí {m} minút a dá sa použiť len raz. Ak si oň nežiadal(a), e-mail ignoruj — tvoj účet je v bezpečí.",
        "lock_subject": "Upozornenie: pokusy o prihlásenie — AI Crypto Analytics",
        "lock_title": "Neúspešné pokusy o prihlásenie",
        "lock_text": "Tvoj účet bol dočasne uzamknutý na {m} minút po niekoľkých neúspešných pokusoch o prihlásenie.",
        "lock_note": "Ak si to nebol(a) ty, zmeň si heslo a v Nastaveniach zapni dvojfaktorové overenie (2FA).",
        "login_subject": "Nové prihlásenie do účtu — AI Crypto Analytics",
        "login_title": "Nové prihlásenie do účtu",
        "login_text": "Do tvojho účtu sa niekto prihlásil z nového zariadenia:",
        "login_when": "Čas", "login_device": "Zariadenie", "login_ip": "IP adresa",
        "login_note": "Ak si to bol(a) ty, nemusíš nič robiť. Ak nie, okamžite si zmeň heslo, v Nastaveniach zvoľ „Odhlásiť zo všetkých ostatných zariadení“ a zapni 2FA.",
    },
    "cs": {
        "hello": "Ahoj {u},",
        "verify_subject": "Ověř si e-mail — AI Crypto Analytics",
        "verify_title": "Ověř si e-mail",
        "verify_text": "Vítej v AI Crypto Analytics! K dokončení registrace zadej v aplikaci tento kód:",
        "verify_note": "Kód platí {m} minut. Pokud ses neregistroval(a), tento e-mail ignoruj.",
        "reset_subject": "Kód pro obnovení hesla — AI Crypto Analytics",
        "reset_title": "Obnovení hesla",
        "reset_text": "Obdrželi jsme žádost o obnovení hesla k tvému účtu. Zadej tento kód v aplikaci:",
        "reset_note": "Kód platí {m} minut a lze ho použít jen jednou. Pokud jsi o něj nežádal(a), e-mail ignoruj — tvůj účet je v bezpečí.",
        "lock_subject": "Upozornění: pokusy o přihlášení — AI Crypto Analytics",
        "lock_title": "Neúspěšné pokusy o přihlášení",
        "lock_text": "Tvůj účet byl dočasně uzamčen na {m} minut po několika neúspěšných pokusech o přihlášení.",
        "lock_note": "Pokud jsi to nebyl(a) ty, změň si heslo a v Nastavení zapni dvoufázové ověření (2FA).",
        "login_subject": "Nové přihlášení do účtu — AI Crypto Analytics",
        "login_title": "Nové přihlášení do účtu",
        "login_text": "Do tvého účtu se někdo přihlásil z nového zařízení:",
        "login_when": "Čas", "login_device": "Zařízení", "login_ip": "IP adresa",
        "login_note": "Pokud jsi to byl(a) ty, nemusíš nic dělat. Pokud ne, ihned si změň heslo, v Nastavení zvol „Odhlásit ze všech ostatních zařízení“ a zapni 2FA.",
    },
}


def email_lang(lang: str | None) -> str:
    return lang if lang in _T else "en"


def tr(key: str, lang: str | None, **params) -> str:
    return _T[email_lang(lang)][key].format(**params)


def subject(kind: str, lang: str | None) -> str:
    return tr(f"{kind}_subject", lang)


def email_shell(inner_html: str, preheader: str = "", lang: str | None = "en", footer_extra: str = "") -> str:
    return f"""\
<!DOCTYPE html>
<html lang="{email_lang(lang)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f1f5f9; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <span style="display:none; max-height:0; overflow:hidden;">{html.escape(preheader)}</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9; padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:520px; background:#ffffff; border-radius:14px; overflow:hidden; box-shadow:0 4px 24px rgba(15,23,42,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#22d3ee,#34d399); padding:22px 28px;">
            <span style="font-size:17px; font-weight:800; color:#04141a; letter-spacing:-0.01em;">AI Crypto Analytics</span>
          </td>
        </tr>
        <tr><td style="padding:32px 28px;">
          {inner_html}
        </td></tr>
        <tr>
          <td style="padding:18px 28px; background:#f8fafc; border-top:1px solid #e2e8f0;">
            <p style="margin:0; font-size:11.5px; color:#94a3b8;">{_FOOTER[email_lang(lang)]}{footer_extra}</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


_H1 = 'style="margin:0 0 14px; font-size:19px; color:#0f172a;"'
_P = 'style="margin:0 0 16px; font-size:14px; line-height:1.6; color:#334155;"'
_NOTE = 'style="margin:0; font-size:12.5px; line-height:1.6; color:#94a3b8;"'


def _code_block(code: str) -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 22px; width:100%;">
          <tr><td align="center" style="background:#f1f5f9; border-radius:12px; padding:20px;">
            <span style="font-family:'SF Mono',Consolas,monospace; font-size:34px; font-weight:800; letter-spacing:8px; color:#0f172a;">{html.escape(code)}</span>
          </td></tr>
        </table>"""


def _code_email(prefix: str, username: str, code: str, minutes: int, lang: str | None) -> tuple[str, str]:
    hello = tr("hello", lang, u=username)
    text_body = f"{hello}\n\n{tr(prefix + '_text', lang)}\n\n{code}\n\n{tr(prefix + '_note', lang, m=minutes)}"
    html_body = email_shell(lang=lang, preheader=tr(prefix + "_title", lang), inner_html=f"""
        <h1 {_H1}>{tr(prefix + "_title", lang)}</h1>
        <p {_P}>{html.escape(hello)} {tr(prefix + "_text", lang)}</p>
        {_code_block(code)}
        <p {_NOTE}>{tr(prefix + "_note", lang, m=minutes)}</p>""")
    return text_body, html_body


def render_reset_password_email(username: str, code: str, expires_minutes: int, lang: str | None = "en") -> tuple[str, str]:
    return _code_email("reset", username, code, expires_minutes, lang)


def render_verification_email(username: str, code: str, expires_minutes: int, lang: str | None = "en") -> tuple[str, str]:
    return _code_email("verify", username, code, expires_minutes, lang)


def render_lockout_email(username: str, minutes: int, lang: str | None = "en") -> tuple[str, str]:
    hello = tr("hello", lang, u=username)
    text_body = f"{hello}\n\n{tr('lock_text', lang, m=minutes)} {tr('lock_note', lang)}"
    html_body = email_shell(lang=lang, preheader=tr("lock_title", lang), inner_html=f"""
        <h1 {_H1}>{tr("lock_title", lang)}</h1>
        <p {_P}>{html.escape(hello)} {tr("lock_text", lang, m=minutes)}</p>
        <p {_NOTE}>{tr("lock_note", lang)}</p>""")
    return text_body, html_body


def render_new_login_email(username: str, when: str, device: str, ip: str, lang: str | None = "en") -> tuple[str, str]:
    hello = tr("hello", lang, u=username)
    rows = [(tr("login_when", lang), when), (tr("login_device", lang), device), (tr("login_ip", lang), ip)]
    text_body = (f"{hello}\n\n{tr('login_text', lang)}\n" + "".join(f"- {k}: {v}\n" for k, v in rows)
                 + f"\n{tr('login_note', lang)}")
    table = "".join(f'<tr><td style="padding:3px 14px 3px 0; color:#94a3b8;">{k}</td><td><strong>{html.escape(v)}</strong></td></tr>'
                    for k, v in rows)
    html_body = email_shell(lang=lang, preheader=tr("login_title", lang), inner_html=f"""
        <h1 {_H1}>{tr("login_title", lang)}</h1>
        <p {_P}>{html.escape(hello)} {tr("login_text", lang)}</p>
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 18px; font-size:13.5px; color:#334155;">{table}</table>
        <p {_NOTE}>{tr("login_note", lang)}</p>""")
    return text_body, html_body
