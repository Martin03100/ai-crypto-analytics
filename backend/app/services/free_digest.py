"""Morning overview without an AI key: plain sentences built from live public data, nothing invented."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.i18n_content import normalize_lang
from app.services import market_data, signals

_MOOD = {
    "en": {"Extreme Fear": "extreme fear", "Fear": "fear", "Neutral": "neutral", "Greed": "greed", "Extreme Greed": "extreme greed"},
    "sk": {"Extreme Fear": "extrémny strach", "Fear": "strach", "Neutral": "neutrálne", "Greed": "chamtivosť",
           "Extreme Greed": "extrémna chamtivosť"},
    "cs": {"Extreme Fear": "extrémní strach", "Fear": "strach", "Neutral": "neutrální", "Greed": "chamtivost",
           "Extreme Greed": "extrémní chamtivost"},
    "de": {"Extreme Fear": "extreme Angst", "Fear": "Angst", "Neutral": "neutral", "Greed": "Gier", "Extreme Greed": "extreme Gier"},
    "pl": {"Extreme Fear": "skrajny strach", "Fear": "strach", "Neutral": "neutralnie", "Greed": "chciwość",
           "Extreme Greed": "skrajna chciwość"},
}

_TEXT = {
    "en": {"fg": "Fear & Greed Index today: {v}/100 ({mood}).", "moves": "In the last 24 h: {moves}.",
           "event": "Next on the calendar: {name} ({date}).", "signals": "Strongest market signals: {items}.",
           "none": "Live market data is not available right now."},
    "sk": {"fg": "Fear & Greed Index dnes: {v}/100 ({mood}).", "moves": "Za posledných 24 h: {moves}.",
           "event": "Najbližšie v kalendári: {name} ({date}).", "signals": "Najsilnejšie trhové signály: {items}.",
           "none": "Živé trhové dáta momentálne nie sú dostupné."},
    "cs": {"fg": "Fear & Greed Index dnes: {v}/100 ({mood}).", "moves": "Za posledních 24 h: {moves}.",
           "event": "Nejbližší v kalendáři: {name} ({date}).", "signals": "Nejsilnější tržní signály: {items}.",
           "none": "Živá tržní data momentálně nejsou dostupná."},
    "de": {"fg": "Fear & Greed Index heute: {v}/100 ({mood}).", "moves": "In den letzten 24 h: {moves}.",
           "event": "Als Nächstes im Kalender: {name} ({date}).", "signals": "Stärkste Marktsignale: {items}.",
           "none": "Live-Marktdaten sind gerade nicht verfügbar."},
    "pl": {"fg": "Fear & Greed Index dziś: {v}/100 ({mood}).", "moves": "W ostatnich 24 h: {moves}.",
           "event": "Najbliżej w kalendarzu: {name} ({date}).", "signals": "Najsilniejsze sygnały rynkowe: {items}.",
           "none": "Dane rynkowe na żywo są teraz niedostępne."},
}

_COINS = (("BTC", "bitcoin"), ("ETH", "ethereum"), ("SOL", "solana"))


def _moves() -> Optional[str]:
    ok, rows, _err = market_data.get_coin_markets([cid for _, cid in _COINS])
    if not ok or not rows:
        return None
    parts = []
    for symbol, cid in _COINS:
        change = (rows.get(cid) or {}).get("price_change_percentage_24h_in_currency")
        if isinstance(change, (int, float)):
            parts.append(f"{symbol} {change:+.1f} %")
    return ", ".join(parts) or None


def _signal_lines(lang: str) -> List[str]:
    try:
        bundle = signals.latest("BTC") or signals.collect("BTC")
    except Exception:  # noqa: BLE001 - the overview works without signals
        return []
    return signals.headline(bundle.get("items", []), lang, limit=3)


def build(fg_value: Optional[int], fg_classification: Optional[str], lang: str = "en") -> Dict[str, Any]:
    """{"zhrnutie": summary, "kluceve_body": [points]} in the shape of the AI digest."""
    lang = normalize_lang(lang)
    text = _TEXT[lang]
    summary: List[str] = []
    if isinstance(fg_value, int):
        mood = _MOOD[lang].get(fg_classification or "", fg_classification or "")
        summary.append(text["fg"].format(v=fg_value, mood=mood))
    moves = _moves()
    if moves:
        summary.append(text["moves"].format(moves=moves))
    points: List[str] = []
    lines = _signal_lines(lang)
    if lines:
        points.append(text["signals"].format(items="; ".join(lines)))
    events = market_data.get_upcoming_market_events(lang, limit=1)
    if events:
        points.append(text["event"].format(name=events[0]["udalost"], date=events[0]["datum"]))
    return {"zhrnutie": " ".join(summary) or text["none"], "kluceve_body": points}
