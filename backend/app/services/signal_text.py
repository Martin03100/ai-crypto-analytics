"""Market signal names and display values in the app's languages, for e-mails and Telegram
(the web app has its own translations)."""

from __future__ import annotations

import re
from typing import Any, Dict, List


# Short names for e-mails and Telegram (the web app has its own translations).
LABELS = {
    "funding": ("Funding", "Funding", "Funding", "Funding", "Funding"),
    "open_interest": ("Open interest", "Open interest", "Open interest", "Open Interest", "Open interest"),
    "long_short": ("Long/short ratio", "Pomer long/short", "Poměr long/short", "Long/Short-Verhältnis", "Stosunek long/short"),
    "liquidations": ("Liquidations", "Likvidácie", "Likvidace", "Liquidationen", "Likwidacje"),
    "put_call": ("Options put/call", "Opcie put/call", "Opce put/call", "Optionen Put/Call", "Opcje put/call"),
    "dvol": ("Implied volatility", "Implikovaná volatilita", "Implikovaná volatilita", "Implizite Volatilität",
             "Zmienność implikowana"),
    "stablecoins": ("Stablecoin supply", "Zásoba stablecoinov", "Zásoba stablecoinů", "Stablecoin-Angebot",
                    "Podaż stablecoinów"),
    "coinbase_premium": ("Coinbase premium", "Coinbase prémia", "Coinbase prémie", "Coinbase-Prämie", "Premia Coinbase"),
    "btc_dominance": ("BTC dominance", "Dominancia BTC", "Dominance BTC", "BTC-Dominanz", "Dominacja BTC"),
    "total_cap": ("Crypto market cap", "Kapitalizácia trhu", "Kapitalizace trhu", "Krypto-Marktkapitalisierung",
                  "Kapitalizacja rynku"),
    "btc_fees": ("BTC fees", "Poplatky BTC", "Poplatky BTC", "BTC-Gebühren", "Opłaty BTC"),
    "hashrate": ("Hashrate", "Hashrate", "Hashrate", "Hashrate", "Hashrate"),
    "vix": ("VIX", "VIX", "VIX", "VIX", "VIX"), "nasdaq": ("Nasdaq", "Nasdaq", "Nasdaq", "Nasdaq", "Nasdaq"),
    "sp500": ("S&P 500", "S&P 500", "S&P 500", "S&P 500", "S&P 500"),
    "dollar": ("US dollar", "Americký dolár", "Americký dolar", "US-Dollar", "Dolar amerykański"),
    "us10y": ("US 10y yield", "Výnos 10r dlhopisu USA", "Výnos 10l dluhopisu USA", "Rendite 10-j. US-Anleihe",
              "Rentowność 10-l. obligacji USA"),
    "oil": ("Oil", "Ropa", "Ropa", "Öl", "Ropa"), "fed_rate": ("Fed rate", "Sadzba Fedu", "Sazba Fedu", "Fed-Zins", "Stopa Fed"),
    "inflation": ("US inflation", "Inflácia USA", "Inflace USA", "US-Inflation", "Inflacja w USA"),
    "gold": ("Gold", "Zlato", "Zlato", "Gold", "Złoto"),
    "event": ("Calendar", "Kalendár", "Kalendář", "Kalender", "Kalendarz"),
    "regulator_news": ("Regulators", "Regulátori", "Regulátoři", "Regulierer", "Regulatorzy"),
    "polymarket": ("Polymarket", "Polymarket", "Polymarket", "Polymarket", "Polymarket"),
}
_LABEL_INDEX = {"en": 0, "sk": 1, "cs": 2, "de": 3, "pl": 4}


def _label(key: str, idx: int) -> str:
    names = LABELS.get(key)
    if not names:
        return key
    return names[idx] if idx < len(names) else names[0]


# Period marks in the display values ("+2.5% 1w") in each language: en, sk, cs, de, pl (the web app has the same).
_UNITS = {
    "24h": ("24h", "24 h", "24 h", "24 Std.", "24 h"), "7d": ("7d", "7 dní", "7 dní", "7 T.", "7 dni"),
    "30d": ("30d", "30 dní", "30 dní", "30 T.", "30 dni"), "1w": ("1w", "1 týž.", "1 týd.", "1 Wo.", "1 tydz."),
    "1m": ("1m", "1 mes.", "1 měs.", "1 Mon.", "1 mies."), "8h": ("8h", "8 h", "8 h", "8 Std.", "8 h"),
    "y/y": ("y/y", "medziročne", "meziročně", "ggü. Vorjahr", "r/r"),
}
_LONGS = ("{n}% longs", "{n} % longov", "{n} % longů", "{n} % Longs", "{n}% longów")


def localize_display(display: str, lang: str) -> str:
    idx = _LABEL_INDEX.get(lang, 0)
    liquidations = re.fullmatch(r"(\d+)% long", display)
    if liquidations:
        return _LONGS[idx].format(n=liquidations.group(1))
    text = re.sub(r"(\s)(24h|7d|30d|1w|1m)(?=\)|$)", lambda m: m.group(1) + _UNITS[m.group(2)][idx], display)
    text = re.sub(r"/ 8h$", "/ " + _UNITS["8h"][idx], text)
    return re.sub(r" y/y$", " " + _UNITS["y/y"][idx], text)


def headline(items: List[Dict[str, Any]], lang: str, limit: int = 4) -> List[str]:
    """The strongest non-neutral signals as short lines, e.g. "Funding: +0.0450% / 8h ▼"."""
    idx = _LABEL_INDEX.get(lang, 0)
    picked = [s for s in items if s["tone"] != "neutral"][:limit]
    return [f"{_label(s['key'], idx)}: {localize_display(s['display'], lang)} {'▲' if s['tone'] == 'bullish' else '▼'}"
            for s in picked]
