"""Helpers for the CSV downloads (forecast history, account data, the admin's waitlist)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

UTF8_BOM = chr(0xFEFF)  # lets Excel detect UTF-8 (diacritics in model names)
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def safe_cell(value: Any) -> Any:
    """Spreadsheet-safe cell: text that starts like a formula (= + - @) is prefixed with ' so Excel never runs it.
    Numbers (also negative ones written as text) stay as they are; None becomes empty, datetimes ISO in UTC."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat() + "Z" if value.tzinfo is None else value.isoformat()
    if isinstance(value, str) and value[:1] in _FORMULA_START and not _is_number(value):
        return "'" + value
    return value


def price_error(accuracy_pct: Optional[float]) -> Optional[float]:
    """Exports show how far the forecast was from the real price (as the app does), not a flattering "accuracy"."""
    return None if accuracy_pct is None else round(max(0.0, 100 - accuracy_pct), 2)
