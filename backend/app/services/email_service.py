"""app/services/email_service.py — odosielanie emailov (napr. reset hesla).

Ak su nastavene SMTP_* premenne (viz app/config.py), posiela realny email
(HTML aj plain-text verziu naraz — multipart/alternative, standardna prax,
aby ho spravne zobrazili aj emailovi klienti, ktori HTML nerendruju). Ak nie
(typicky lokalny vyvoj), sprava sa iba zaloguje na server - appka tym padom
funguje aj bez emailovej infrastruktury (viz routers/auth.py — v development
rezime sa odkaz vrati aj priamo v API odpovedi)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger("aca.email")


def is_smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to_address: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    """Posle email. Ak je zadany `html_body`, posle multipart/alternative
    (HTML + plain-text fallback pre klientov, ktori HTML nerendruju alebo
    ho pouzivatel ma vypnuty) - standardny format pre transakcne emaily."""
    if not is_smtp_configured():
        logger.info("SMTP nie je nakonfigurovany — email pre %s sa iba loguje:\n%s", to_address, text_body)
        return False
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
        logger.error("Odoslanie emailu na %s zlyhalo: %s", to_address, exc)
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
