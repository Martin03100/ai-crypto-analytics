"""app/services/email_service.py — odosielanie emailov (napr. reset hesla).

Ak su nastavene SMTP_* premenne (viz app/config.py), posiela realny email.
Ak nie (typicky lokalny vyvoj), spravu iba zaloguje na server - appka tym
padom funguje aj bez emailovej infrastruktury, len prijemca dostane odkaz
inou cestou (viz routers/auth.py — v development rezime sa odkaz vrati aj
priamo v API odpovedi)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger("aca.email")


def is_smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to_address: str, subject: str, body: str) -> bool:
    if not is_smtp_configured():
        logger.info("SMTP nie je nakonfigurovany — email pre %s sa iba loguje:\n%s", to_address, body)
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
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
