"""Calls to the AI providers (Gemini, OpenAI, Anthropic, DeepSeek, xAI and any OpenAI-compatible API) with
retries, plus the guard that keeps a user's custom API address off private networks."""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
import urllib3.exceptions
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool

from app.config import (
    ANTHROPIC_API_URL, ANTHROPIC_API_VERSION, ANTHROPIC_MODEL,
    DEEPSEEK_API_URL, DEEPSEEK_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_MODEL, GROK_API_URL, GROK_MODEL, OPENAI_API_URL, OPENAI_MODEL,
    AI_REQUEST_TIMEOUT_SECONDS,
)

logger = logging.getLogger("aca.ai")


_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


_MAX_RETRIES = 1


_BACKOFF_BASE_SECONDS = 1.5


def _post_with_retry(url: str, headers: Dict[str, str], payload: Dict[str, Any],
                      timeout: int) -> requests.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** attempt))
                continue
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** attempt))
                continue
            raise
    if last_exc:
        raise last_exc
    raise requests.exceptions.RequestException("Neznama chyba pri volani API.")


_MAX_OUTPUT_TOKENS = 1024


_TEMPERATURE = 0.4


_GEMINI_MAX_OUTPUT_TOKENS = 4096


# Gemini (above all on free keys) regularly answers 500 INTERNAL, 503 UNAVAILABLE ("model is overloaded") or
# 429 RESOURCE_EXHAUSTED. AI calls run as background jobs, so there is time to retry with back-off, honour the
# retry delay Google suggests, and finally switch to a lighter model, which has its own capacity and quota.
_GEMINI_TRANSIENT_MARKERS = ("500", "internal", "503", "overloaded", "unavailable", "timeout", "timed out", "deadline")


_GEMINI_RATE_MARKERS = ("429", "resource_exhausted", "rate limit", "quota")


_GEMINI_BACKOFF_SECONDS = (2, 5, 10)


_GEMINI_BUDGET_SECONDS = 110          # all attempts and models together


_GEMINI_MAX_RATE_WAIT_SECONDS = 30


def _gemini_error_kind(message: str) -> Optional[str]:
    text = message.lower()
    if "404" in text or "not_found" in text or "is not found" in text:
        return "model"          # retired or misspelled model name: retrying is pointless, another model may work
    if any(m in text for m in _GEMINI_RATE_MARKERS):
        return "rate"
    if any(m in text for m in _GEMINI_TRANSIENT_MARKERS):
        return "transient"
    return None


def _gemini_retry_delay(message: str) -> Optional[float]:
    """Seconds Google asks to wait (RetryInfo.retryDelay, e.g. '37s'), if present."""
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s", message)
    return float(match.group(1)) if match else None


def _call_gemini_model(model: str, prompt: str, api_key: str, deadline: float) -> tuple[bool, str, Optional[str]]:
    from google import genai
    from google.genai import types

    use_thinking_config = True
    transient_retries = 0
    waited_for_rate = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            return False, "", "timeout: casovy limit na odpoved AI vyprsal"
        try:
            timeout_ms = int(min(AI_REQUEST_TIMEOUT_SECONDS, remaining) * 1000)
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))
            config_kwargs: Dict[str, Any] = {"max_output_tokens": _GEMINI_MAX_OUTPUT_TOKENS}
            if use_thinking_config:
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
            response = client.models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig(**config_kwargs),
            )
            text = response.text or ""
            if not text.strip():
                return False, "", "Gemini vratil prazdnu odpoved (limit vystupu bol vycerpany premyslanim modelu)."
            return True, text, None
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if use_thinking_config and "thinking" in message.lower():
                # Models without thinking-level support reject the option; retry once without it.
                use_thinking_config = False
                continue
            kind = _gemini_error_kind(message)
            if kind == "rate":
                delay = _gemini_retry_delay(message)
                per_day = "perday" in message.lower().replace("_", "").replace(" ", "")
                if (not waited_for_rate and not per_day and delay is not None
                        and delay <= _GEMINI_MAX_RATE_WAIT_SECONDS and time.monotonic() + delay + 5 < deadline):
                    waited_for_rate = True
                    time.sleep(delay)
                    continue
                return False, "", message
            if kind == "transient" and transient_retries < len(_GEMINI_BACKOFF_SECONDS):
                pause = _GEMINI_BACKOFF_SECONDS[transient_retries]
                if time.monotonic() + pause + 5 < deadline:
                    transient_retries += 1
                    time.sleep(pause)
                    continue
            return False, "", message


def _call_gemini(prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    deadline = time.monotonic() + _GEMINI_BUDGET_SECONDS
    last_error = ""
    for model in dict.fromkeys([GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]):
        ok, text, error = _call_gemini_model(model, prompt, api_key, deadline)
        if ok:
            if model != GEMINI_MODEL:
                logger.info("Gemini: odpoved od zalozneho modelu %s", model)
            return True, text, None
        last_error = error or ""
        if last_error.startswith("Gemini vratil"):
            return False, "", last_error
        if _gemini_error_kind(last_error) is None or time.monotonic() >= deadline - 5:
            break                      # e.g. an invalid key: another model would fail the same way
    return False, "", f"Gemini API chyba: {last_error}"


def _call_openai_compatible(url: str, model: str, prompt: str, api_key: str,
                             extra_headers: Optional[Dict[str, str]] = None,
                             extra_body: Optional[Dict[str, Any]] = None) -> tuple[bool, str, Optional[str]]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    payload = {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": _TEMPERATURE, "max_tokens": _MAX_OUTPUT_TOKENS,
    }
    if extra_body:
        payload.update(extra_body)
    try:
        response = _post_with_retry(url, headers, payload, AI_REQUEST_TIMEOUT_SECONDS)
        body = response.json()
        text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        return True, text, None
    except requests.exceptions.RequestException as exc:
        return False, "", f"API chyba ({url}): {exc}"
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        return False, "", f"Neocakavany format odpovede ({url}): {exc}"


def _call_anthropic(prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_API_VERSION, "Content-Type": "application/json"}
    payload = {"model": ANTHROPIC_MODEL, "max_tokens": _MAX_OUTPUT_TOKENS, "temperature": _TEMPERATURE,
               "messages": [{"role": "user", "content": prompt}]}
    try:
        response = _post_with_retry(ANTHROPIC_API_URL, headers, payload, AI_REQUEST_TIMEOUT_SECONDS)
        body = response.json()
        blocks = body.get("content", [])
        text = blocks[0].get("text", "") if blocks else ""
        return True, text, None
    except requests.exceptions.RequestException as exc:
        return False, "", f"Anthropic API chyba: {exc}"
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        return False, "", f"Neocakavany format odpovede Anthropic: {exc}"


def _call_ai_provider_raw(provider: str, prompt: str, api_key: str) -> tuple[bool, str, Optional[str]]:
    if provider == "gemini":
        return _call_gemini(prompt, api_key)
    if provider == "openai":
        return _call_openai_compatible(OPENAI_API_URL, OPENAI_MODEL, prompt, api_key)
    if provider == "anthropic":
        return _call_anthropic(prompt, api_key)
    if provider == "deepseek":
        return _call_openai_compatible(DEEPSEEK_API_URL, DEEPSEEK_MODEL, prompt, api_key,
                                       extra_body={"thinking": {"type": "disabled"}})
    if provider == "grok":
        return _call_openai_compatible(GROK_API_URL, GROK_MODEL, prompt, api_key)
    if provider == "custom":
        return _call_custom_provider(prompt, api_key)
    return False, "", f"Neznamy AI provider: {provider}"


def validate_custom_base_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return "Neplatná adresa API vlastného providera."
    if parsed.scheme != "https" or not parsed.hostname:
        return "Adresa API vlastného providera musí začínať https:// a obsahovať doménu."
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return "Doménu adresy API vlastného providera sa nepodarilo nájsť."
    for info in infos:
        try:
            is_public = ipaddress.ip_address(str(info[4][0]).split("%")[0]).is_global
        except ValueError:
            is_public = False
        if not is_public:
            return "Adresa API vlastného providera musí smerovať na verejný internet, nie na internú sieť."
    return None


def _is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(str(value).split("%")[0]).is_global
    except ValueError:
        return False


class _PublicOnlyHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        sock = super()._new_conn()
        try:
            peer = sock.getpeername()[0]
        except OSError:
            peer = ""
        if not _is_public_ip(peer):
            sock.close()
            raise urllib3.exceptions.NewConnectionError(
                self, "Adresa vlastného providera smeruje na internú sieť - spojenie bolo zrušené.")
        return sock


class _PublicOnlyPool(HTTPSConnectionPool):
    ConnectionCls = _PublicOnlyHTTPSConnection


class _PublicOnlyAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {**self.poolmanager.pool_classes_by_scheme, "https": _PublicOnlyPool}


def _call_custom_provider(prompt: str, secret: str) -> tuple[bool, str, Optional[str]]:
    try:
        config = json.loads(secret)
        base_url, model, key = config["base_url"], config["model"], config["key"]
    except (ValueError, KeyError, TypeError):
        return False, "", "Vlastný provider nie je správne nastavený (adresa, model, kľúč)."
    problem = validate_custom_base_url(base_url)
    if problem:
        return False, "", problem
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", _PublicOnlyAdapter())
    try:
        response = session.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": _TEMPERATURE, "max_tokens": _MAX_OUTPUT_TOKENS},
            timeout=AI_REQUEST_TIMEOUT_SECONDS, allow_redirects=False,
        )
        if response.is_redirect:
            return False, "", "Vlastný provider vrátil presmerovanie - zadaj priamu adresu API."
        response.raise_for_status()
        text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        if not text.strip():
            return False, "", "Vlastný provider vrátil prázdnu odpoveď."
        return True, text, None
    except Exception as exc:  # noqa: BLE001
        return False, "", f"Vlastny provider chyba: {exc}"
    finally:
        session.close()
