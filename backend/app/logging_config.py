"""app/logging_config.py — jednoduche strukturovane logovanie (JSON-lines).

Zamerne bez externych zavislosti (ziadny python-json-logger a pod.) - jeden
Formatter, ktory kazdy log zaznam vypise ako jeden riadok JSON na stdout.
V produkcii sa da presmerovat do log agregatora (napr. cez docker logs)
bez dalsej konfiguracie.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Nikdy nelogovat citlive polia, aj keby ich niekto omylom pridal
        # cez `extra=` (API kluce, hesla, JWT).
        for sensitive in ("api_key", "password", "token", "authorization"):
            payload.pop(sensitive, None)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    # Odstran predvolene handlery (napr. z uvicorn), aby sme nelogovali 2x.
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # uvicorn.access je dost hlucny (kazdy request) - necháme ho na WARNING,
    # nase vlastne aca.* loggery zostavaju na `level`.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
