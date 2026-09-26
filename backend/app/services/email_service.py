"""app/services/email_service.py — odosielanie emailov (napr. reset hesla).

Dva mozne sposoby odoslania, v tomto poradi priority:

1. Brevo HTTPS API (BREVO_API_KEY) — bezi cez port 443, ktory ziadny hosting
   neblokuje. POUZIVAT TOTO na Render/Railway/Fly a inych bezplatnych PaaS
   platformach: tie od konca roka 2025 na bezplatnom pláne blokuju VSETKY
   odchadzajuce spojenia na klasicke SMTP porty (25/465/587) kvoli ochrane
   pred spamom, takze priame SMTP z takehoto hostingu proste nikdy neprejde
   (spojenie padne na timeout), bez ohladu na to, aky spravny je login/heslo.
2. Klasicke SMTP (SMTP_* premenne) — funguje lokalne alebo na hostingu bez
   tohto obmedzenia (platene instancie, VPS...).

Ak nie je nastavene ani jedno (typicky lokalny vyvoj), sprava sa iba zaloguje
na server - appka tym padom funguje aj bez emailovej infrastruktury (viz
routers/auth.py — v development rezime sa kod vrati aj priamo v API odpovedi).
"""

from __future__ import annotations

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
    """True ak je nastaveny ASPON jeden zo sposobov odoslania (Brevo alebo SMTP)."""
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
    except Exception as exc:  # noqa: BLE001 - odoslanie emailu nikdy nesmie zhodit request
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
    except Exception as exc:  # noqa: BLE001 - odoslanie emailu nikdy nesmie zhodit request
        logger.error("Odoslanie emailu cez SMTP na %s zlyhalo: %s", to_address, exc)
        return False


def send_email(to_address: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    """Posle email cez Brevo API (ak je nastaveny BREVO_API_KEY), inak cez
    klasicke SMTP (ak je nastavene), inak sa sprava iba zaloguje."""
    if BREVO_API_KEY:
        return _send_via_brevo(to_address, subject, text_body, html_body)
    if is_smtp_configured():
        return _send_via_smtp(to_address, subject, text_body, html_body)
    logger.info("Email nie je nakonfigurovany (BREVO_API_KEY ani SMTP_*) — email pre %s sa iba loguje:\n%s", to_address, text_body)
    return False


def _email_shell(inner_html: str, preheader: str = "") -> str:
    """Spolocna, jednoducha HTML kostra pre vsetky transakcne emaily appky —
    svetle pozadie (nie tmavy 'obsidian glass' vzhlad appky samotnej), lebo
    tmave emaily sa naprieč emailovymi klientmi (najma Outlook) renderuju
    nespolahlivo. Cyan akcentova farba drzi konzistenciu s brandom appky."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f1f5f9; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <span style="display:none; max-height:0; overflow:hidden;">{preheader}</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9; padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:480px; background:#ffffff; border-radius:14px; overflow:hidden; box-shadow:0 4px 24px rgba(15,23,42,0.08);">
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
            <p style="margin:0; font-size:11.5px; color:#94a3b8;">AI Crypto Analytics — automaticka sprava, neodpovedaj na tento email.</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def render_reset_password_email(username: str, code: str, expires_minutes: int) -> tuple[str, str]:
    """Vrati (text_body, html_body) pre email s kodom na reset hesla."""
    text_body = (
        f"Ahoj {username},\n\nO obnovenie hesla si poziadal(a) ty? Ak ano, "
        f"zadaj tento kod v appke (platny {expires_minutes} minut):\n\n{code}\n\n"
        f"Ak si o reset nepoziadal(a), tento email jednoducho ignoruj — tvoj ucet je v poriadku."
    )
    html_body = _email_shell(
        preheader=f"Tvoj kod na obnovenie hesla, platny {expires_minutes} minut.",
        inner_html=f"""
        <h1 style="margin:0 0 14px; font-size:19px; color:#0f172a;">Obnovenie hesla</h1>
        <p style="margin:0 0 22px; font-size:14px; line-height:1.6; color:#334155;">
          Ahoj <strong>{username}</strong>, dostali sme žiadosť o obnovenie hesla k tvojmu účtu.
          Zadaj tento kód v aplikácii:
        </p>
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 22px; width:100%;">
          <tr><td align="center" style="background:#f1f5f9; border-radius:12px; padding:20px;">
            <span style="font-family:'SF Mono',Consolas,monospace; font-size:34px; font-weight:800; letter-spacing:8px; color:#0f172a;">
              {code}
            </span>
          </td></tr>
        </table>
        <p style="margin:0 0 20px; font-size:12.5px; color:#94a3b8;">
          Tento kód je platný {expires_minutes} minút a dá sa použiť len raz.
        </p>
        <p style="margin:0; font-size:12.5px; color:#94a3b8;">
          Ak si o reset hesla nepožiadal(a) ty, tento email jednoducho ignoruj — tvoj účet zostáva v bezpečí.
        </p>
        """,
    )
    return text_body, html_body



def render_verification_email(username: str, code: str, expires_minutes: int) -> tuple[str, str]:
    text_body = (f"Ahoj {username},\n\nvitaj v AI Crypto Analytics! Na overenie emailu zadaj v appke tento kod "
                 f"(platny {expires_minutes} minut):\n\n{code}\n\nAk si sa neregistroval(a), tento email ignoruj.")
    html_body = _email_shell(preheader=f"Tvoj overovaci kod, platny {expires_minutes} minut.", inner_html=f"""
        <h1 style="margin:0 0 14px; font-size:19px; color:#0f172a;">Over si email</h1>
        <p style="margin:0 0 22px; font-size:14px; line-height:1.6; color:#334155;">
          Ahoj <strong>{username}</strong>, vitaj v AI Crypto Analytics! Na dokončenie registrácie zadaj v aplikácii tento kód:
        </p>
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 22px; width:100%;">
          <tr><td align="center" style="background:#f1f5f9; border-radius:12px; padding:20px;">
            <span style="font-family:'SF Mono',Consolas,monospace; font-size:34px; font-weight:800; letter-spacing:8px; color:#0f172a;">{code}</span>
          </td></tr>
        </table>
        <p style="margin:0; font-size:12.5px; color:#94a3b8;">Kód platí {expires_minutes} minút. Ak si sa neregistroval(a) ty, tento email ignoruj.</p>
        """)
    return text_body, html_body


def render_lockout_email(username: str, minutes: int) -> tuple[str, str]:
    text_body = (f"Ahoj {username},\n\ntvoj ucet bol docasne uzamknuty na {minutes} minut po niekolkych "
                 f"neuspesnych pokusoch o prihlasenie. Ak si to nebol(a) ty, odporucame zmenit heslo a zapnut 2FA.")
    html_body = _email_shell(preheader="Viacero neúspešných pokusov o prihlásenie.", inner_html=f"""
        <h1 style="margin:0 0 14px; font-size:19px; color:#0f172a;">Upozornenie na pokusy o prihlásenie</h1>
        <p style="margin:0 0 14px; font-size:14px; line-height:1.6; color:#334155;">
          Ahoj <strong>{username}</strong>, tvoj účet bol dočasne uzamknutý na <strong>{minutes} minút</strong>
          po niekoľkých neúspešných pokusoch o prihlásenie.
        </p>
        <p style="margin:0; font-size:14px; line-height:1.6; color:#334155;">
          Ak si to nebol(a) ty, odporúčame zmeniť heslo a v Nastaveniach zapnúť dvojfaktorové overenie (2FA).
        </p>
        """)
    return text_body, html_body
