"""Keep the free Render instance awake.

Render's free plan stops a service after ~15 minutes without inbound requests; the first request afterwards
takes ~50 s, longer than the Netlify /api proxy waits, and scheduled forecasts do not run while it sleeps.
GitHub's scheduled "keep warm" workflow is throttled to a run every few hours, so the backend pings its own
public URL instead. Render sets RENDER_EXTERNAL_URL automatically; elsewhere this does nothing.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

import requests

logger = logging.getLogger("aca.keep_awake")

INTERVAL_SECONDS = 10 * 60
_stop = threading.Event()


def ping_url() -> Optional[str]:
    if os.environ.get("KEEP_AWAKE", "1") == "0":
        return None
    base = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    return f"{base}/api/health" if base.startswith("https://") else None


def ping(url: str) -> bool:
    try:
        return requests.get(url, timeout=30).status_code < 500
    except requests.RequestException as exc:
        logger.warning("Keep-awake ping zlyhal: %s", exc)
        return False


def _loop(url: str) -> None:
    while not _stop.wait(INTERVAL_SECONDS):
        ping(url)


def start() -> bool:
    url = ping_url()
    if not url:
        return False
    _stop.clear()
    threading.Thread(target=_loop, args=(url,), name="keep-awake", daemon=True).start()
    logger.info("Keep-awake: ping %s kazdych %s min.", url, INTERVAL_SECONDS // 60)
    return True


def stop() -> None:
    _stop.set()
